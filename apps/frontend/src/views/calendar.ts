import { ApiError, createEvent, deleteEvent, fetchEvents, fetchHealth, logout, updateEvent } from "../api";
import { renderCalendarGrid } from "../components/calendar-grid";
import { renderEventDrawer } from "../components/event-drawer";
import { renderWeekGrid } from "../components/week-grid";
import { addSecondsClamped, DEFAULT_GAP_SECONDS } from "../lib/duration";
import { getLang, Lang, setLang, t } from "../lib/i18n";
import { FLAG_CO, FLAG_US, ICON_MENU, ICON_SIGNAL } from "../lib/icons";
import { formatRelative, nextOnOccurrence } from "../lib/next-occurrence";
import type { ActuatorPinState, EventDTO, EventInput } from "../types";

const HEALTH_POLL_MS = 30_000;
const RELATIVE_TIME_REFRESH_MS = 30_000;
// An echo older than this is likely from before the actuator's last power
// cycle or a missed message, not a reliable "current" reading — flagged
// visually rather than hidden, since a stale echo is still better than none.
const STALE_ECHO_SECONDS = 10 * 60;
type CalTab = "week" | "month";

function formatAge(ageSeconds: number): string {
  const suffix = getLang() === "es" ? "hace" : "ago";
  if (ageSeconds < 60) return getLang() === "es" ? `${suffix} ${Math.round(ageSeconds)}s` : `${Math.round(ageSeconds)}s ${suffix}`;
  const minutes = Math.round(ageSeconds / 60);
  if (minutes < 60) return getLang() === "es" ? `${suffix} ${minutes}m` : `${minutes}m ${suffix}`;
  const hours = Math.round(minutes / 60);
  return getLang() === "es" ? `${suffix} ${hours}h` : `${hours}h ${suffix}`;
}

interface CalendarViewOptions {
  user: string;
  onLoggedOut: () => void;
}

export function renderCalendarView(root: HTMLElement, opts: CalendarViewOptions): void {
  root.innerHTML = "";

  let monthCursor = new Date();
  monthCursor = new Date(monthCursor.getFullYear(), monthCursor.getMonth(), 1);
  let weekCursor = new Date();
  let tab: CalTab = "week";
  let events: EventDTO[] = [];
  let actuatorState: Record<string, ActuatorPinState> = {};
  let healthPollId: ReturnType<typeof setInterval> | null = null;
  let relativeTimeRefreshId: ReturnType<typeof setInterval> | null = null;

  const shell = document.createElement("div");
  shell.className = "app-shell";
  shell.innerHTML = `
    <header class="app-header">
      <div class="app-header-title">
        <h1>${t("appName")}</h1>
      </div>
      <div class="app-header-status">
        <button type="button" class="mesh-status mesh-status-unknown" role="status" aria-live="polite" aria-label="${t("checkingMesh")}" title="${t("checkingMesh")} — ${t("checkNow")}">
          ${ICON_SIGNAL}
          <span class="mesh-status-label">${t("checkingMesh")}</span>
        </button>
        <button type="button" class="btn btn-ghost nav-arrow lang-toggle lang-toggle-desktop" aria-label="${t("language")}" title="${getLang() === "es" ? "English" : "Español"}">
          <span class="app-menu-item-flag">${getLang() === "es" ? FLAG_US : FLAG_CO}</span>
        </button>
        <span class="app-header-user">${opts.user}</span>
        <button type="button" class="btn btn-secondary app-logout app-logout-desktop">${t("logOut")}</button>
        <!-- Mobile only (see app.css @media 640px): the row above gets
             cramped on a phone, so language + logout collapse into one
             overflow menu there instead of standing controls. -->
        <div class="app-menu">
          <button type="button" class="btn btn-ghost nav-arrow app-menu-toggle" aria-label="${t("language")}" aria-haspopup="true" aria-expanded="false">${ICON_MENU}</button>
          <div class="app-menu-panel" hidden>
            <div class="app-menu-user">${opts.user}</div>
            <button type="button" class="app-menu-item lang-toggle">
              <span class="app-menu-item-flag">${getLang() === "es" ? FLAG_US : FLAG_CO}</span>
              <span>${getLang() === "es" ? "English" : "Español"}</span>
            </button>
            <button type="button" class="app-menu-item app-logout">${t("logOut")}</button>
          </div>
        </div>
      </div>
    </header>
    <main class="app-main">
      <section class="cal-section">
        <div class="cal-tabs">
          <button type="button" class="cal-tab cal-tab-active" data-tab="week">${t("week")}</button>
          <button type="button" class="cal-tab" data-tab="month">${t("month")}</button>
        </div>
        <div class="cal-tab-body"></div>
      </section>
      <aside class="list-section">
        <h2 class="list-heading">${t("allEvents")}</h2>
        <div class="event-list"></div>
      </aside>
    </main>
  `;
  root.appendChild(shell);

  const calSection = shell.querySelector<HTMLElement>(".cal-tab-body")!;
  const tabButtons = shell.querySelectorAll<HTMLButtonElement>(".cal-tab");
  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      tab = btn.dataset.tab as CalTab;
      tabButtons.forEach((b) => b.classList.toggle("cal-tab-active", b === btn));
      renderGrid();
    });
  });
  const listEl = shell.querySelector<HTMLElement>(".event-list")!;
  const statusEl = shell.querySelector<HTMLButtonElement>(".mesh-status")!;
  // Desktop shows language/logout as standing controls; mobile collapses
  // them into the overflow menu instead (see app.css @media 640px) — both
  // markups exist in the DOM at once, CSS picks which is visible, so both
  // sets of buttons need the same handlers wired up.
  const logoutBtns = shell.querySelectorAll<HTMLButtonElement>(".app-logout");
  const langToggles = shell.querySelectorAll<HTMLButtonElement>(".lang-toggle");
  const menuToggle = shell.querySelector<HTMLButtonElement>(".app-menu-toggle")!;
  const menuPanel = shell.querySelector<HTMLDivElement>(".app-menu-panel")!;
  const drawerRoot = document.createElement("div");
  root.appendChild(drawerRoot);

  // Simple click-outside-to-close dropdown — no need for anything fancier
  // with just two actions (language, logout) behind it.
  menuToggle.addEventListener("click", (e) => {
    e.stopPropagation();
    const willOpen = menuPanel.hidden;
    menuPanel.hidden = !willOpen;
    menuToggle.setAttribute("aria-expanded", String(willOpen));
  });
  document.addEventListener("click", (e) => {
    if (!menuPanel.hidden && !menuPanel.contains(e.target as Node) && e.target !== menuToggle) {
      menuPanel.hidden = true;
      menuToggle.setAttribute("aria-expanded", "false");
    }
  });

  // Simplest correct approach for a plain key->string dict with no
  // framework reactivity: switching language just re-renders the whole
  // view from scratch, rather than hunting down and updating every string
  // node individually. Existing intervals are cleared first so switching
  // languages repeatedly can't leak timers.
  langToggles.forEach((toggle) => {
    toggle.addEventListener("click", () => {
      const next: Lang = getLang() === "es" ? "en" : "es";
      setLang(next);
      if (healthPollId) clearInterval(healthPollId);
      if (relativeTimeRefreshId) clearInterval(relativeTimeRefreshId);
      renderCalendarView(root, opts);
    });
  });

  const toastRoot = document.createElement("div");
  toastRoot.className = "toast-root";
  toastRoot.setAttribute("aria-live", "polite");
  toastRoot.setAttribute("role", "status");
  root.appendChild(toastRoot);

  let toastTimeoutId: ReturnType<typeof setTimeout> | null = null;
  function showToast(message: string): void {
    toastRoot.textContent = message;
    toastRoot.classList.add("toast-visible");
    if (toastTimeoutId) clearTimeout(toastTimeoutId);
    toastTimeoutId = setTimeout(() => {
      toastRoot.classList.remove("toast-visible");
    }, 2800);
  }

  logoutBtns.forEach((btn) => {
    btn.addEventListener("click", async () => {
      logoutBtns.forEach((b) => (b.disabled = true));
      try {
        await logout();
      } finally {
        if (healthPollId) clearInterval(healthPollId);
        if (relativeTimeRefreshId) clearInterval(relativeTimeRefreshId);
        opts.onLoggedOut();
      }
    });
  });

  async function handleMove(
    ev: EventDTO,
    patch: { start_date: string; end_date: string | null; on_time: string; off_time: string },
  ): Promise<void> {
    const input: EventInput = {
      label: ev.label,
      pin: ev.pin,
      recurrence: ev.recurrence,
      start_date: patch.start_date,
      end_date: patch.end_date,
      on_time: patch.on_time,
      off_time: patch.off_time,
      enabled: ev.enabled,
    };
    let updated: EventDTO;
    try {
      updated = await updateEvent(ev.id, input);
    } catch (err) {
      throw new Error(err instanceof ApiError ? err.detail ?? t("couldNotMoveEvent") : t("couldNotMoveEvent"));
    }
    events = events.map((e) => (e.id === updated.id ? updated : e));
    renderGrid();
    renderList();
  }

  function renderGrid(): void {
    if (tab === "month") {
      renderCalendarGrid(calSection, {
        year: monthCursor.getFullYear(),
        month: monthCursor.getMonth(),
        events,
        onDayClick: (iso) => {
          // Jumping into the week containing the clicked day, per the
          // approved UX proposal ("clicking a day from month still jumps
          // into that day's week").
          weekCursor = new Date(`${iso}T00:00:00`);
          tab = "week";
          shell.querySelectorAll<HTMLButtonElement>(".cal-tab").forEach((b) => {
            b.classList.toggle("cal-tab-active", b.dataset.tab === "week");
          });
          renderGrid();
        },
        onPrevMonth: () => {
          monthCursor = new Date(monthCursor.getFullYear(), monthCursor.getMonth() - 1, 1);
          renderGrid();
        },
        onNextMonth: () => {
          monthCursor = new Date(monthCursor.getFullYear(), monthCursor.getMonth() + 1, 1);
          renderGrid();
        },
      });
      return;
    }

    renderWeekGrid(calSection, {
      weekStart: weekCursor,
      events,
      onPrevWeek: () => {
        weekCursor = new Date(weekCursor.getFullYear(), weekCursor.getMonth(), weekCursor.getDate() - 7);
        renderGrid();
      },
      onNextWeek: () => {
        weekCursor = new Date(weekCursor.getFullYear(), weekCursor.getMonth(), weekCursor.getDate() + 7);
        renderGrid();
      },
      onToday: () => {
        weekCursor = new Date();
        renderGrid();
      },
      onSlotClick: (iso, hhmmss) => openDrawer(iso, null, hhmmss, addSecondsClamped(hhmmss, DEFAULT_GAP_SECONDS)),
      onEventClick: (ev) => openDrawer(ev.start_date, ev),
      onMove: handleMove,
    });
  }

  function renderList(): void {
    listEl.innerHTML = "";
    if (events.length === 0) {
      const empty = document.createElement("p");
      empty.className = "hint-text";
      empty.textContent = t("noEventsYet");
      listEl.appendChild(empty);
      return;
    }

    const now = new Date();
    const nextOccurrences = new Map(events.map((ev) => [ev.id, nextOnOccurrence(ev, now)]));

    // The single soonest-upcoming event gets the relative-time badge — the
    // one an operator most needs to notice at a glance, not every future
    // event (which would be noisy and stale within minutes).
    let soonestId: string | null = null;
    let soonestAt: Date | null = null;
    for (const [id, at] of nextOccurrences) {
      if (at && (!soonestAt || at < soonestAt)) {
        soonestId = id;
        soonestAt = at;
      }
    }

    const sorted = [...events].sort((a, b) => a.start_date.localeCompare(b.start_date));
    sorted.forEach((ev) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "event-row";
      if (!ev.enabled) row.classList.add("event-row-disabled");
      if (ev.id === soonestId) row.classList.add("event-row-next");

      const badge =
        ev.id === soonestId && soonestAt
          ? `<span class="event-row-badge">${escapeHtml(formatRelative(soonestAt, now))}</span>`
          : "";

      const echo = actuatorState[String(ev.pin)];
      const echoBadge = echo
        ? `<span class="event-row-echo event-row-echo-${echo.state === "ON" ? "on" : "off"}${
            echo.age_seconds > STALE_ECHO_SECONDS ? " event-row-echo-stale" : ""
          }" title="${t("lastEchoTitle")}">${echo.state} · ${formatAge(echo.age_seconds)}</span>`
        : "";

      row.innerHTML = `
        <div class="event-row-main">
          <span class="event-row-label">${ev.label ? escapeHtml(ev.label) : `${t("pin")} ${ev.pin}`}</span>
          <span class="event-row-meta">${t("pin")} ${ev.pin} · ${ev.on_time}–${ev.off_time} · ${
            ev.recurrence === "daily" ? t("daily") : t("once")
          }${echoBadge}</span>
        </div>
        <div class="event-row-date">${badge}${ev.start_date}${ev.end_date ? ` → ${ev.end_date}` : ""}</div>
      `;
      row.addEventListener("click", () => openDrawer(ev.start_date, ev));
      listEl.appendChild(row);
    });
  }

  function openDrawer(
    dateISO: string,
    existing: EventDTO | null,
    prefillOn?: string,
    prefillOff?: string,
  ): void {
    renderEventDrawer(drawerRoot, {
      date: dateISO,
      existing,
      existingEvents: events,
      prefillOn,
      prefillOff,
      onSave: async (input) => {
        if (existing) {
          const updated = await updateEvent(existing.id, input);
          events = events.map((e) => (e.id === updated.id ? updated : e));
          showToast(t("saved", { name: updated.label || `${t("pin")} ${updated.pin}` }));
        } else {
          const created = await createEvent(input);
          events = [...events, created];
          showToast(t("created", { name: created.label || `${t("pin")} ${created.pin}` }));
        }
        renderGrid();
        renderList();
      },
      onDelete: existing
        ? async () => {
            await deleteEvent(existing.id);
            events = events.filter((e) => e.id !== existing.id);
            showToast(t("deleted", { name: existing.label || `${t("pin")} ${existing.pin}` }));
            renderGrid();
            renderList();
          }
        : null,
      onClose: () => {},
    });
  }

  async function loadEvents(): Promise<void> {
    calSection.innerHTML = `<div class="loading-block">${t("loadingCalendar")}</div>`;
    try {
      events = await fetchEvents();
      renderGrid();
      renderList();
    } catch (err) {
      calSection.innerHTML = "";
      const errBox = document.createElement("div");
      errBox.className = "error-text";
      errBox.textContent = err instanceof ApiError ? err.detail ?? t("couldNotLoadEvents") : t("couldNotLoadEvents");
      calSection.appendChild(errBox);
    }
  }

  function setMeshStatus(state: "ok" | "offline" | "unknown"): void {
    statusEl.className = `mesh-status mesh-status-${state}`;
    const label = state === "ok" ? t("meshConnected") : state === "offline" ? t("meshOffline") : t("checkingMesh");
    statusEl.setAttribute("aria-label", label);
    statusEl.title = `${label} — ${t("checkNow")}`;
    const labelEl = statusEl.querySelector<HTMLSpanElement>(".mesh-status-label");
    if (labelEl) labelEl.textContent = label;
  }

  async function pollHealth(): Promise<void> {
    try {
      const health = await fetchHealth();
      setMeshStatus(health.mesh_connected ? "ok" : "offline");
      actuatorState = health.actuator_state;
      renderList();
    } catch {
      setMeshStatus("offline");
    }
  }

  // Lets an operator force a check instead of waiting up to HEALTH_POLL_MS
  // — useful right after power-cycling the actuator or the mesh radio. The
  // pill itself is the button now (no separate refresh icon next to it —
  // see the header-decluttering pass that collapsed the label away too).
  statusEl.addEventListener("click", async () => {
    statusEl.disabled = true;
    statusEl.classList.add("mesh-status-refreshing");
    await pollHealth();
    statusEl.disabled = false;
    statusEl.classList.remove("mesh-status-refreshing");
  });

  pollHealth();
  healthPollId = setInterval(pollHealth, HEALTH_POLL_MS);

  // Keeps the "in N min" badge on the list from going stale — renderList()
  // alone (no data fetch) is cheap enough to run on a timer.
  relativeTimeRefreshId = setInterval(renderList, RELATIVE_TIME_REFRESH_MS);

  loadEvents();
}

function escapeHtml(s: string): string {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}
