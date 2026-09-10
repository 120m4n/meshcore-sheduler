import { ApiError, createEvent, deleteEvent, fetchEvents, fetchHealth, logout, updateEvent } from "../api";
import { renderCalendarGrid } from "../components/calendar-grid";
import { renderEventDrawer } from "../components/event-drawer";
import { renderWeekGrid } from "../components/week-grid";
import { addSecondsClamped, DEFAULT_GAP_SECONDS } from "../lib/duration";
import { formatRelative, nextOnOccurrence } from "../lib/next-occurrence";
import type { EventDTO, EventInput } from "../types";

const HEALTH_POLL_MS = 30_000;
const RELATIVE_TIME_REFRESH_MS = 30_000;
type CalTab = "week" | "month";

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
  let healthPollId: ReturnType<typeof setInterval> | null = null;
  let relativeTimeRefreshId: ReturnType<typeof setInterval> | null = null;

  const shell = document.createElement("div");
  shell.className = "app-shell";
  shell.innerHTML = `
    <header class="app-header">
      <div class="app-header-title">
        <span class="app-header-eyebrow">Mesh Event Scheduler</span>
        <h1>Calendar</h1>
      </div>
      <div class="app-header-status">
        <span class="mesh-status mesh-status-unknown">
          <span class="mesh-dot"></span>
          <span class="mesh-status-label">Checking mesh…</span>
        </span>
        <span class="app-header-user">${opts.user}</span>
        <button type="button" class="btn btn-secondary app-logout">Log out</button>
      </div>
    </header>
    <main class="app-main">
      <section class="cal-section">
        <div class="cal-tabs">
          <button type="button" class="cal-tab cal-tab-active" data-tab="week">Week</button>
          <button type="button" class="cal-tab" data-tab="month">Month</button>
        </div>
        <div class="cal-tab-body"></div>
      </section>
      <aside class="list-section">
        <h2 class="list-heading">All events</h2>
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
  const statusEl = shell.querySelector<HTMLSpanElement>(".mesh-status")!;
  const statusLabel = shell.querySelector<HTMLSpanElement>(".mesh-status-label")!;
  const logoutBtn = shell.querySelector<HTMLButtonElement>(".app-logout")!;
  const drawerRoot = document.createElement("div");
  root.appendChild(drawerRoot);

  logoutBtn.addEventListener("click", async () => {
    logoutBtn.disabled = true;
    try {
      await logout();
    } finally {
      if (healthPollId) clearInterval(healthPollId);
      if (relativeTimeRefreshId) clearInterval(relativeTimeRefreshId);
      opts.onLoggedOut();
    }
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
      throw new Error(err instanceof ApiError ? err.detail ?? "Could not move the event." : "Could not move the event.");
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
      empty.textContent = "No events scheduled yet. Click a day on the calendar to add one.";
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

      row.innerHTML = `
        <div class="event-row-main">
          <span class="event-row-label">${ev.label ? escapeHtml(ev.label) : `Pin ${ev.pin}`}</span>
          <span class="event-row-meta">Pin ${ev.pin} · ${ev.on_time}–${ev.off_time}${
            ev.recurrence === "daily" ? " · Daily" : " · Once"
          }</span>
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
        } else {
          const created = await createEvent(input);
          events = [...events, created];
        }
        renderGrid();
        renderList();
      },
      onDelete: existing
        ? async () => {
            await deleteEvent(existing.id);
            events = events.filter((e) => e.id !== existing.id);
            renderGrid();
            renderList();
          }
        : null,
      onClose: () => {},
    });
  }

  async function loadEvents(): Promise<void> {
    calSection.innerHTML = '<div class="loading-block">Loading calendar…</div>';
    try {
      events = await fetchEvents();
      renderGrid();
      renderList();
    } catch (err) {
      calSection.innerHTML = "";
      const errBox = document.createElement("div");
      errBox.className = "error-text";
      errBox.textContent =
        err instanceof ApiError ? err.detail ?? "Could not load events." : "Could not load events.";
      calSection.appendChild(errBox);
    }
  }

  function setMeshStatus(state: "ok" | "offline" | "unknown"): void {
    statusEl.className = `mesh-status mesh-status-${state}`;
    statusLabel.textContent =
      state === "ok" ? "Mesh connected" : state === "offline" ? "Mesh offline" : "Checking mesh…";
  }

  async function pollHealth(): Promise<void> {
    try {
      const health = await fetchHealth();
      setMeshStatus(health.mesh_connected ? "ok" : "offline");
    } catch {
      setMeshStatus("offline");
    }
  }

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
