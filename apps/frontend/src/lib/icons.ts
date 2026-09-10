// A small curated set of stroke icons (Lucide-style: 24x24 viewBox, 2px
// stroke, round caps/joins) — inlined rather than pulled from a CDN so the
// app has zero runtime dependencies, matching the rest of this project.
// Each returns ready-to-insert SVG markup sized via CSS (currentColor
// stroke, so it inherits the button's text color automatically).

function icon(paths: string): string {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;
}

export const ICON_CHEVRON_LEFT = icon('<polyline points="15 18 9 12 15 6"/>');
export const ICON_CHEVRON_RIGHT = icon('<polyline points="9 18 15 12 9 6"/>');
export const ICON_REFRESH = icon(
  '<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>',
);
export const ICON_CLOSE = icon('<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>');
