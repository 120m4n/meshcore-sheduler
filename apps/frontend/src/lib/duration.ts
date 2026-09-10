// Mirrors the backend's event_repo.duration_seconds()/validate_duration()
// (apps/backend/app/repositories/event_repo.py) so the drawer and the week
// grid's drag-drop can reject an invalid duration instantly, client-side,
// instead of waiting on a round trip. The backend re-checks on every
// create/update regardless — this is the fast path, not the guarantee.
export const MIN_DURATION_SECONDS = 15;
// Above this, still valid but flagged as a warning (not blocked) — mirrors
// the backend's WARN_DURATION_SECONDS, which is informational only there too.
export const WARN_DURATION_SECONDS = 60 * 60;
// Mirrors the backend's DEFAULT_GAP_SECONDS.
export const DEFAULT_GAP_SECONDS = 15;

function toSeconds(hhmmss: string): number {
  const [h, m, s] = hhmmss.split(":").map(Number);
  return h * 3600 + m * 60 + (s || 0);
}

// Events no longer cross midnight — off_time must be strictly after on_time,
// same day (see event_repo.validate_duration). A non-positive result means
// the caller should treat it as invalid, not as a wrap to the next day.
export function durationSeconds(onTime: string, offTime: string): number {
  return toSeconds(offTime) - toSeconds(onTime);
}

// Clamped to 23:59:59 instead of wrapping past midnight — events can no
// longer cross midnight, so a prefilled OFF time (e.g. from clicking a slot
// near end-of-day) must stay on the same day.
export function addSecondsClamped(hhmmss: string, delta: number): string {
  const total = Math.min(toSeconds(hhmmss) + delta, 86399);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return [h, m, s].map((n) => String(n).padStart(2, "0")).join(":");
}
