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
export const ICON_MENU = icon('<line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>');
// Signal bars — a shape that reads as "connectivity" on its own, not just
// a colored dot with no inherent meaning. Same currentColor/stroke pattern
// as the rest of this set, so mesh-status-ok/offline/unknown's existing
// color classes apply to it automatically.
export const ICON_SIGNAL = icon(
  '<line x1="4" y1="20" x2="4" y2="16"/><line x1="9" y1="20" x2="9" y2="12"/><line x1="14" y1="20" x2="14" y2="8"/><line x1="19" y1="20" x2="19" y2="4"/>',
);
// Theme toggle: sun shown while dark (click switches to light), moon shown
// while light (click switches to dark) — the icon names the mode you'll get.
export const ICON_SUN = icon(
  '<circle cx="12" cy="12" r="4"/><line x1="12" y1="2" x2="12" y2="4"/><line x1="12" y1="20" x2="12" y2="22"/><line x1="4.93" y1="4.93" x2="6.34" y2="6.34"/><line x1="17.66" y1="17.66" x2="19.07" y2="19.07"/><line x1="2" y1="12" x2="4" y2="12"/><line x1="20" y1="12" x2="22" y2="12"/><line x1="4.93" y1="19.07" x2="6.34" y2="17.66"/><line x1="17.66" y1="6.34" x2="19.07" y2="4.93"/>',
);
export const ICON_MOON = icon('<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>');

// Flat-color flag illustrations (not stroke icons like the set above) for
// the language toggle — plain geometric renderings of each country's flag,
// inlined as SVG so they render identically everywhere instead of
// depending on the OS having regional-indicator emoji font support (it
// often doesn't on Windows, where 🇨🇴/🇺🇸 fall back to literal "CO"/"US"
// text). Simplified proportions, not pixel-exact reproductions.
export const FLAG_CO =
  '<svg viewBox="0 0 24 16" width="20" height="14" aria-hidden="true"><rect width="24" height="16" fill="#FCD116"/><rect y="8" width="24" height="4" fill="#003893"/><rect y="12" width="24" height="4" fill="#CE1126"/></svg>';
export const FLAG_US =
  '<svg viewBox="0 0 24 16" width="20" height="14" aria-hidden="true"><rect width="24" height="16" fill="#B22234"/><rect y="1.23" width="24" height="1.23" fill="#fff"/><rect y="3.69" width="24" height="1.23" fill="#fff"/><rect y="6.15" width="24" height="1.23" fill="#fff"/><rect y="8.62" width="24" height="1.23" fill="#fff"/><rect y="11.08" width="24" height="1.23" fill="#fff"/><rect y="13.54" width="24" height="1.23" fill="#fff"/><rect width="10" height="8.62" fill="#3C3B6E"/></svg>';
