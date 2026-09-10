// Mirrors the backend's event_repo.find_overlap()/validate_no_overlap()
// (apps/backend/app/repositories/event_repo.py) so the drawer can reject an
// overlapping event instantly, client-side, instead of waiting on a round
// trip. The backend re-checks on every create/update regardless — this is
// the fast path, not the guarantee.
import type { EventDTO, EventInput } from "../types";

function dateRange(recurrence: string, startDate: string, endDate: string | null): [string, string | null] {
  if (recurrence === "once") return [startDate, startDate];
  return [startDate, endDate];
}

// None (null) as an end date means unbounded (recurs forever).
function dateRangesOverlap(
  aStart: string,
  aEnd: string | null,
  bStart: string,
  bEnd: string | null,
): boolean {
  if (aEnd !== null && bStart > aEnd) return false;
  if (bEnd !== null && aStart > bEnd) return false;
  return true;
}

// Same-pin only — different pins are independent physical channels, so
// overlapping schedules on different pins is not a conflict. Touching edges
// (one event's off_time == another's on_time) is allowed. Disabled events
// are still checked, same reasoning as the backend: enabling one later must
// not silently create an overlap.
export function findOverlap(
  candidate: EventInput,
  existingEvents: EventDTO[],
  excludeId: string | null,
): EventDTO | null {
  const [aStart, aEnd] = dateRange(candidate.recurrence, candidate.start_date, candidate.end_date);

  for (const other of existingEvents) {
    if (excludeId !== null && other.id === excludeId) continue;
    if (other.pin !== candidate.pin) continue;
    const [bStart, bEnd] = dateRange(other.recurrence, other.start_date, other.end_date);
    if (!dateRangesOverlap(aStart, aEnd, bStart, bEnd)) continue;
    if (candidate.on_time < other.off_time && other.on_time < candidate.off_time) {
      return other;
    }
  }
  return null;
}

export function describeEvent(ev: EventDTO): string {
  const label = ev.label || `pin ${ev.pin}`;
  return `${label} (${ev.on_time}–${ev.off_time})`;
}
