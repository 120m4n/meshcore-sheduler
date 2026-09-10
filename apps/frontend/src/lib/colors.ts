// Reads the --pin-N custom properties defined once in style.css (:root) —
// that's the single source of truth for pin colors, editable there without
// touching this file or any of its callers (week-grid blocks, month-view
// markers, the event list's echo badge).
const PIN_COUNT = 8;

function readPinColorVars(): string[] {
  const styles = getComputedStyle(document.documentElement);
  return Array.from({ length: PIN_COUNT }, (_, i) => styles.getPropertyValue(`--pin-${i}`).trim());
}

let cached: string[] | null = null;

export function colorForPin(pin: number): string {
  if (!cached) cached = readPinColorVars();
  return cached[pin % cached.length];
}
