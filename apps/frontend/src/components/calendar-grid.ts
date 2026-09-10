import { colorForPin } from "../lib/colors";
import type { EventDTO } from "../types";

const WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function toISODate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function eventOccursOn(ev: EventDTO, iso: string): boolean {
  if (ev.recurrence === "once") {
    return ev.start_date === iso;
  }
  if (iso < ev.start_date) return false;
  if (ev.end_date && iso > ev.end_date) return false;
  return true;
}

interface CalendarGridOptions {
  year: number;
  month: number; // 0-11
  events: EventDTO[];
  onDayClick: (iso: string) => void;
  onPrevMonth: () => void;
  onNextMonth: () => void;
}

export function renderCalendarGrid(root: HTMLElement, opts: CalendarGridOptions): void {
  root.innerHTML = "";

  const { year, month, events, onDayClick, onPrevMonth, onNextMonth } = opts;

  const wrap = document.createElement("div");
  wrap.className = "cal-grid-wrap";

  const nav = document.createElement("div");
  nav.className = "cal-nav";
  const monthLabel = new Date(year, month, 1).toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
  });
  nav.innerHTML = `
    <button type="button" class="btn btn-ghost cal-prev" aria-label="Previous month">&larr;</button>
    <h2 class="cal-month-label">${monthLabel}</h2>
    <button type="button" class="btn btn-ghost cal-next" aria-label="Next month">&rarr;</button>
  `;
  nav.querySelector(".cal-prev")!.addEventListener("click", onPrevMonth);
  nav.querySelector(".cal-next")!.addEventListener("click", onNextMonth);

  const weekdaysRow = document.createElement("div");
  weekdaysRow.className = "cal-weekdays";
  WEEKDAY_LABELS.forEach((label) => {
    const el = document.createElement("div");
    el.className = "cal-weekday";
    el.textContent = label;
    weekdaysRow.appendChild(el);
  });

  const grid = document.createElement("div");
  grid.className = "cal-days";

  const firstOfMonth = new Date(year, month, 1);
  const startOffset = (firstOfMonth.getDay() + 6) % 7; // Monday-first
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const todayISO = toISODate(new Date());

  const totalCells = Math.ceil((startOffset + daysInMonth) / 7) * 7;

  for (let cell = 0; cell < totalCells; cell++) {
    const dayNum = cell - startOffset + 1;
    const cellDate = new Date(year, month, dayNum);
    const iso = toISODate(cellDate);
    const inMonth = dayNum >= 1 && dayNum <= daysInMonth;

    const dayEl = document.createElement("button");
    dayEl.type = "button";
    dayEl.className = "cal-day";
    if (!inMonth) dayEl.classList.add("cal-day-outside");
    if (iso === todayISO) dayEl.classList.add("cal-day-today");

    const dayEvents = inMonth ? events.filter((ev) => eventOccursOn(ev, iso)) : [];
    if (dayEvents.length > 0) dayEl.classList.add("cal-day-has-events");

    const numEl = document.createElement("span");
    numEl.className = "cal-day-num";
    numEl.textContent = String(cellDate.getDate());
    dayEl.appendChild(numEl);

    if (dayEvents.length > 0) {
      const markers = document.createElement("div");
      markers.className = "cal-day-markers";
      dayEvents.slice(0, 4).forEach((ev) => {
        const dot = document.createElement("span");
        dot.className = "cal-marker";
        dot.style.background = colorForPin(ev.pin);
        dot.title = `${ev.label ?? `Pin ${ev.pin}`} · ${ev.on_time}–${ev.off_time}${
          ev.recurrence === "daily" ? " · daily" : ""
        }`;
        if (ev.recurrence === "daily") dot.classList.add("cal-marker-recurring");
        if (!ev.enabled) dot.classList.add("cal-marker-disabled");
        markers.appendChild(dot);
      });
      if (dayEvents.length > 4) {
        const more = document.createElement("span");
        more.className = "cal-marker-more";
        more.textContent = `+${dayEvents.length - 4}`;
        markers.appendChild(more);
      }
      dayEl.appendChild(markers);
    }

    if (inMonth) {
      dayEl.addEventListener("click", () => onDayClick(iso));
    } else {
      dayEl.disabled = true;
    }

    grid.appendChild(dayEl);
  }

  wrap.append(nav, weekdaysRow, grid);
  root.appendChild(wrap);
}
