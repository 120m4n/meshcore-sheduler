import { colorForPin } from "../lib/colors";
import { durationSeconds, MIN_DURATION_SECONDS } from "../lib/duration";
import type { EventDTO } from "../types";

const WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HOUR_PX = 64;
const MIN_BLOCK_PX = 18;
const SNAP_MINUTES = 5;

function toISODate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function startOfWeek(d: Date): Date {
  const day = (d.getDay() + 6) % 7; // Monday-first
  const monday = new Date(d.getFullYear(), d.getMonth(), d.getDate() - day);
  return monday;
}

function addDays(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
}

function toSeconds(hhmmss: string): number {
  const [h, m, s] = hhmmss.split(":").map(Number);
  return h * 3600 + m * 60 + (s || 0);
}

function secondsToHHMMSS(total: number): string {
  const wrapped = ((total % 86400) + 86400) % 86400;
  const h = Math.floor(wrapped / 3600);
  const m = Math.floor((wrapped % 3600) / 60);
  const s = wrapped % 60;
  return [h, m, s].map((n) => String(n).padStart(2, "0")).join(":");
}

function occursOnceOn(ev: EventDTO, iso: string): boolean {
  return ev.recurrence === "once" && ev.start_date === iso;
}

// Mirrors the backend's event_repo._occurs_on() for recurrence == "daily".
function occursDailyOn(ev: EventDTO, iso: string): boolean {
  if (ev.recurrence !== "daily") return false;
  if (iso < ev.start_date) return false;
  if (ev.end_date && iso > ev.end_date) return false;
  return true;
}

interface WeekGridOptions {
  weekStart: Date; // any date within the target week; normalized internally
  events: EventDTO[];
  onPrevWeek: () => void;
  onNextWeek: () => void;
  onToday: () => void;
  onSlotClick: (dateISO: string, timeHHMMSS: string) => void;
  onEventClick: (ev: EventDTO) => void;
  // Called on drop; resolves/rejects — rejection (backend 400, network
  // error, or a client-side duration check) snaps the block back.
  onMove: (ev: EventDTO, patch: { start_date: string; end_date: string | null; on_time: string; off_time: string }) => Promise<void>;
}

export function renderWeekGrid(root: HTMLElement, opts: WeekGridOptions): void {
  root.innerHTML = "";

  const monday = startOfWeek(opts.weekStart);
  const days = Array.from({ length: 7 }, (_, i) => addDays(monday, i));
  const dayISOs = days.map(toISODate);
  const todayISO = toISODate(new Date());

  const onceEvents = opts.events.filter((ev) => ev.recurrence === "once" && dayISOs.includes(ev.start_date));
  const dailyEvents = opts.events.filter((ev) => {
    if (ev.recurrence !== "daily") return false;
    // Any overlap between [start_date, end_date] and this week counts.
    const weekEnd = dayISOs[6];
    if (ev.start_date > weekEnd) return false;
    if (ev.end_date && ev.end_date < dayISOs[0]) return false;
    return true;
  });

  const wrap = document.createElement("div");
  wrap.className = "week-grid-wrap";

  const nav = document.createElement("div");
  nav.className = "cal-nav";
  const label = `${days[0].toLocaleDateString("en-US", { month: "short", day: "numeric" })} – ${days[6].toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}`;
  nav.innerHTML = `
    <button type="button" class="btn btn-ghost week-prev" aria-label="Previous week">&larr;</button>
    <div class="week-nav-center">
      <h2 class="cal-month-label">${label}</h2>
      <button type="button" class="btn btn-ghost btn-sm week-today">Today</button>
    </div>
    <button type="button" class="btn btn-ghost week-next" aria-label="Next week">&rarr;</button>
  `;
  nav.querySelector(".week-prev")!.addEventListener("click", opts.onPrevWeek);
  nav.querySelector(".week-next")!.addEventListener("click", opts.onNextWeek);
  nav.querySelector(".week-today")!.addEventListener("click", opts.onToday);

  const errorBanner = document.createElement("div");
  errorBanner.className = "week-error-banner";
  errorBanner.hidden = true;
  let errorTimeoutId: ReturnType<typeof setTimeout> | null = null;
  function showTransientError(message: string): void {
    errorBanner.textContent = message;
    errorBanner.hidden = false;
    if (errorTimeoutId) clearTimeout(errorTimeoutId);
    errorTimeoutId = setTimeout(() => {
      errorBanner.hidden = true;
    }, 4000);
  }

  // ---------- daily recurring lane (horizontal-drag-only) ----------
  // The lane is one strip spanning the week, not a per-day time axis, so
  // there's no sensible vertical-drag-to-time mapping inside it — dragging
  // a daily block only ever changes which day it starts on. Time-of-day for
  // daily events is edited exclusively through the drawer.
  const dailyLane = document.createElement("div");
  dailyLane.className = "week-daily-lane";
  if (dailyEvents.length === 0) {
    dailyLane.classList.add("week-daily-lane-empty");
  }
  dailyEvents.forEach((ev) => {
    const block = document.createElement("div");
    block.className = "week-daily-block";
    block.style.background = colorForPin(ev.pin);
    if (!ev.enabled) block.classList.add("week-block-disabled");
    block.textContent = `${ev.label ?? `Pin ${ev.pin}`} · daily · ${ev.on_time}–${ev.off_time}`;
    block.title = `${ev.label ?? `Pin ${ev.pin}`} · daily from ${ev.start_date}${ev.end_date ? ` to ${ev.end_date}` : ""}`;

    let dragged = false;
    block.addEventListener("pointerdown", (downEv) => {
      downEv.preventDefault();
      const startX = downEv.clientX;
      dragged = false;
      let dayDelta = 0;
      const dayWidth = block.parentElement!.clientWidth / 7 || 100;

      function onMove(moveEv: PointerEvent): void {
        const dx = moveEv.clientX - startX;
        const newDelta = Math.round(dx / dayWidth);
        if (newDelta !== dayDelta) {
          dayDelta = newDelta;
          dragged = true;
        }
        block.style.transform = `translateX(${dayDelta * dayWidth}px)`;
        block.classList.toggle("week-block-dragging", dragged);
      }

      async function onUp(): Promise<void> {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
        block.style.transform = "";
        block.classList.remove("week-block-dragging");

        if (!dragged || dayDelta === 0) {
          if (!dragged) opts.onEventClick(ev);
          return;
        }

        const newStart = addDays(new Date(`${ev.start_date}T00:00:00`), dayDelta);
        const newEnd = ev.end_date ? addDays(new Date(`${ev.end_date}T00:00:00`), dayDelta) : null;
        try {
          await opts.onMove(ev, {
            start_date: toISODate(newStart),
            end_date: newEnd ? toISODate(newEnd) : null,
            on_time: ev.on_time,
            off_time: ev.off_time,
          });
        } catch (err) {
          showTransientError(err instanceof Error ? err.message : "Could not move the event.");
        }
      }

      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp, { once: true });
    });

    dailyLane.appendChild(block);
  });

  // ---------- single-grid hour rail + day columns (one shared scroll area) ----------
  // A single CSS Grid owns both scroll axes, with the hour rail sticky on
  // the left and the day header sticky on top — see app.css .week-grid.
  // That's what keeps the rail from drifting out of sync with the day
  // columns (or getting clipped) the way the old rail+columns-in-a-flex
  // layout with a hand-synced header row did.
  const grid = document.createElement("div");
  grid.className = "week-grid";

  const corner = document.createElement("div");
  corner.className = "week-corner";
  corner.style.gridColumn = "1";
  corner.style.gridRow = "1";
  grid.appendChild(corner);

  days.forEach((day, dayIdx) => {
    const iso = dayISOs[dayIdx];
    const header = document.createElement("div");
    header.className = "week-day-header";
    if (iso === todayISO) header.classList.add("week-day-header-today");
    if (dayIdx === 6) header.classList.add("week-day-header-last");
    header.style.gridColumn = `${dayIdx + 2}`;
    header.style.gridRow = "1";
    header.innerHTML = `<span class="week-day-name">${WEEKDAY_LABELS[dayIdx]}</span><span class="week-day-num">${day.getDate()}</span>`;
    grid.appendChild(header);
  });

  const tracks: HTMLDivElement[] = [];
  for (let h = 0; h < 24; h++) {
    const hourCell = document.createElement("div");
    hourCell.className = "week-hour-cell";
    hourCell.textContent = `${String(h).padStart(2, "0")}:00`;
    hourCell.style.gridColumn = "1";
    hourCell.style.gridRow = `${h + 2}`;
    grid.appendChild(hourCell);

    days.forEach((_day, dayIdx) => {
      const iso = dayISOs[dayIdx];
      let track = tracks[dayIdx];
      if (h === 0) {
        track = document.createElement("div");
        track.className = "week-day-track";
        if (iso === todayISO) track.classList.add("week-day-col-today");
        if (dayIdx === 6) track.classList.add("week-day-track-last");
        track.style.gridColumn = `${dayIdx + 2}`;
        track.style.gridRow = "2 / span 24";
        tracks[dayIdx] = track;
      }

      const hourSlot = document.createElement("div");
      hourSlot.className = "week-hour-slot";
      hourSlot.style.height = `${HOUR_PX}px`;
      hourSlot.addEventListener("click", () => opts.onSlotClick(iso, `${String(h).padStart(2, "0")}:00:00`));
      tracks[dayIdx].appendChild(hourSlot);
    });
  }
  tracks.forEach((track) => grid.appendChild(track));

  days.forEach((_day, dayIdx) => {
    const iso = dayISOs[dayIdx];
    const track = tracks[dayIdx];

    onceEvents
      .filter((ev) => occursOnceOn(ev, iso))
      .forEach((ev) => {
        const onS = toSeconds(ev.on_time);
        const durS = durationSeconds(ev.on_time, ev.off_time);
        const top = (onS / 3600) * HOUR_PX;
        const height = Math.max((durS / 3600) * HOUR_PX, MIN_BLOCK_PX);

        const block = document.createElement("div");
        block.className = "week-block";
        if (!ev.enabled) block.classList.add("week-block-disabled");
        block.style.top = `${top}px`;
        block.style.height = `${height}px`;
        block.style.background = colorForPin(ev.pin);
        block.textContent = ev.label ?? `Pin ${ev.pin}`;
        block.title = `${ev.label ?? `Pin ${ev.pin}`} · ${ev.on_time}–${ev.off_time}`;

        attachOnceDrag(block, ev, dayIdx, top, track, grid, dayISOs, durS, opts, showTransientError);

        track.appendChild(block);
      });

    // Daily events get the same at-time-of-day block as "once" events, so
    // their schedule is visible in the hourly grid on every day they occur
    // — not just in the daily lane's day-range strip above the grid. They
    // are click-to-edit only, not draggable here: dragging one instance
    // would only make sense as "move just this day", but a daily event's
    // time is the same every day it recurs, so there's no single day to
    // drag — dayISOs and the recurrence range are edited in the drawer, and
    // dragging within the day-range strip already covers "move which days".
    dailyEvents
      .filter((ev) => occursDailyOn(ev, iso))
      .forEach((ev) => {
        const onS = toSeconds(ev.on_time);
        const durS = durationSeconds(ev.on_time, ev.off_time);
        const top = (onS / 3600) * HOUR_PX;
        const height = Math.max((durS / 3600) * HOUR_PX, MIN_BLOCK_PX);

        const block = document.createElement("div");
        block.className = "week-block week-block-daily";
        if (!ev.enabled) block.classList.add("week-block-disabled");
        block.style.top = `${top}px`;
        block.style.height = `${height}px`;
        block.style.background = colorForPin(ev.pin);
        block.textContent = ev.label ?? `Pin ${ev.pin}`;
        block.title = `${ev.label ?? `Pin ${ev.pin}`} · daily · ${ev.on_time}–${ev.off_time}`;
        block.addEventListener("click", () => opts.onEventClick(ev));

        track.appendChild(block);
      });
  });

  // ---------- current-time line ----------
  // Shown whenever today is in the visible week, regardless of whether
  // there are any events — it's the user's reference point for "when is
  // now" so they can eyeball how far off the next scheduled event is.
  if (dayISOs.includes(todayISO)) {
    const todayTrack = tracks[dayISOs.indexOf(todayISO)];
    const nowLine = document.createElement("div");
    nowLine.className = "week-now-line";
    const nowLabel = document.createElement("span");
    nowLabel.className = "week-now-label";
    nowLine.appendChild(nowLabel);
    todayTrack.appendChild(nowLine);

    function positionNowLine(): void {
      const now = new Date();
      const nowSeconds = now.getHours() * 3600 + now.getMinutes() * 60 + now.getSeconds();
      nowLine.style.top = `${(nowSeconds / 3600) * HOUR_PX}px`;
      nowLabel.textContent = now.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
    }
    positionNowLine();

    // Stops itself once this grid instance is no longer in the document —
    // renderWeekGrid rebuilds the whole subtree on every re-render, so each
    // call's interval must not keep ticking against detached nodes.
    const nowLineIntervalId = setInterval(() => {
      if (!nowLine.isConnected) {
        clearInterval(nowLineIntervalId);
        return;
      }
      positionNowLine();
    }, 30_000);
  }

  // First-time-user hint: renderList() already has an explicit empty
  // message ("No events scheduled yet…"), but the hourly grid gave no clue
  // beyond a hover cursor that clicking an hour creates an event there.
  if (onceEvents.length === 0 && dailyEvents.length === 0) {
    const emptyHint = document.createElement("div");
    emptyHint.className = "week-empty-hint";
    emptyHint.textContent = "No events this week — click any hour to add one.";
    grid.appendChild(emptyHint);
  }

  wrap.append(nav, errorBanner, dailyLane, grid);
  root.appendChild(wrap);

  // Scroll to a sensible starting hour rather than midnight.
  const initialHour = dayISOs.includes(todayISO) ? new Date().getHours() : 7;
  grid.scrollTop = Math.max(0, initialHour - 1) * HOUR_PX;
}

const HOUR_RAIL_PX = 52;

function attachOnceDrag(
  block: HTMLDivElement,
  ev: EventDTO,
  dayIdx: number,
  originalTop: number,
  track: HTMLElement,
  grid: HTMLElement,
  dayISOs: string[],
  durationS: number,
  opts: WeekGridOptions,
  showTransientError: (msg: string) => void,
): void {
  block.addEventListener("pointerdown", (downEv) => {
    downEv.preventDefault();
    downEv.stopPropagation();
    const startX = downEv.clientX;
    const startY = downEv.clientY;
    let dragged = false;
    let dayDelta = 0;
    let pxDelta = 0;
    const dayWidth = (grid.clientWidth - HOUR_RAIL_PX) / 7 || 100;

    function onMove(moveEv: PointerEvent): void {
      const dx = moveEv.clientX - startX;
      const dy = moveEv.clientY - startY;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) dragged = true;
      dayDelta = Math.round(dx / dayWidth);
      const snapPx = (SNAP_MINUTES / 60) * HOUR_PX;
      pxDelta = Math.round(dy / snapPx) * snapPx;
      block.style.transform = `translate(${dayDelta * dayWidth}px, ${pxDelta}px)`;
      block.classList.toggle("week-block-dragging", dragged);
    }

    async function onUp(): Promise<void> {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      block.style.transform = "";
      block.classList.remove("week-block-dragging");

      if (!dragged) {
        opts.onEventClick(ev);
        return;
      }

      const newTargetDayIdx = Math.min(6, Math.max(0, dayIdx + dayDelta));
      const newTop = Math.max(0, originalTop + pxDelta);
      // Clamp so ON+duration can't cross midnight — events are same-day only.
      const maxOnSeconds = Math.max(0, 86400 - durationS);
      const newOnSeconds = Math.min(Math.round((newTop / HOUR_PX) * 3600), maxOnSeconds);
      const newOnTime = secondsToHHMMSS(newOnSeconds);
      const newOffTime = secondsToHHMMSS(newOnSeconds + durationS);

      if (newOffTime <= newOnTime || durationSeconds(newOnTime, newOffTime) < MIN_DURATION_SECONDS) {
        showTransientError(`ON/OFF must be at least ${MIN_DURATION_SECONDS} seconds apart, same day.`);
        return;
      }

      try {
        await opts.onMove(ev, {
          start_date: dayISOs[newTargetDayIdx],
          end_date: ev.end_date,
          on_time: newOnTime,
          off_time: newOffTime,
        });
      } catch (err) {
        showTransientError(err instanceof Error ? err.message : "Could not move the event.");
      }
    }

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp, { once: true });
  });

  void track; // track kept for future edge-resize (deferred, not in v1)
}
