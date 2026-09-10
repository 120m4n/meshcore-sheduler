export const PIN_COLORS = [
  "#a3591f", "#2f7d4f", "#3a6ea5", "#a3760a",
  "#7c4fa5", "#ab3a34", "#4f8a8b", "#8a5a3a",
];

export function colorForPin(pin: number): string {
  return PIN_COLORS[pin % PIN_COLORS.length];
}
