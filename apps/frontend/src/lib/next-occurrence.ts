import { getLang } from "./i18n";
import type { EventDTO } from "../types";

function toISODate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function addDaysISO(iso: string, days: number): string {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + days);
  return toISODate(d);
}

// Next instant (Date) this event's ON time will fire, at or after `now`, or
// null if it never will again (a "once" event whose ON time has already
// passed, or a "daily" event whose end_date is in the past). Disabled
// events return null too — they won't actually fire.
export function nextOnOccurrence(ev: EventDTO, now: Date): Date | null {
  if (!ev.enabled) return null;

  const nowISO = toISODate(now);
  const nowTime = now.toTimeString().slice(0, 8);

  if (ev.recurrence === "once") {
    if (ev.start_date < nowISO) return null;
    if (ev.start_date === nowISO && ev.on_time < nowTime) return null;
    return new Date(`${ev.start_date}T${ev.on_time}`);
  }

  // daily: first day >= today (within [start_date, end_date]) whose ON
  // time hasn't already passed today.
  let day = ev.start_date > nowISO ? ev.start_date : nowISO;
  if (day === nowISO && ev.on_time < nowTime) {
    day = addDaysISO(day, 1);
  }
  if (ev.end_date && day > ev.end_date) return null;
  return new Date(`${day}T${ev.on_time}`);
}

// Short, rounded relative-time label: "in 12 min", "in 2h", "tomorrow",
// "in 5 days" — precise enough to eyeball urgency without being noisy with
// seconds-level updates.
export function formatRelative(target: Date, now: Date): string {
  const es = getLang() === "es";
  const diffMs = target.getTime() - now.getTime();
  const diffMin = Math.round(diffMs / 60000);
  if (diffMin < 1) return es ? "empezando ahora" : "starting now";
  if (diffMin < 60) return es ? `en ${diffMin} min` : `in ${diffMin} min`;
  const diffH = Math.round(diffMin / 60);
  if (diffH < 24) return es ? `en ${diffH}h` : `in ${diffH}h`;
  const diffDays = Math.round(diffH / 24);
  if (diffDays === 1) return es ? "mañana" : "tomorrow";
  return es ? `en ${diffDays} días` : `in ${diffDays} days`;
}
