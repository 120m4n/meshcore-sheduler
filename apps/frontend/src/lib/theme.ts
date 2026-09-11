// Manual light/dark toggle, dark by default (see style.css: :root holds the
// dark values unconditionally, :root[data-theme="light"] overrides them).
// No system-preference auto-switching — an explicit choice, stored in
// localStorage so it sticks across reloads, same pattern as lib/i18n.ts.

export type Theme = "dark" | "light";

const STORAGE_KEY = "mesh-scheduler-theme";

let currentTheme: Theme = readStoredTheme();

function readStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "dark" || stored === "light") return stored;
  } catch {
    // localStorage unavailable (private mode etc.) — fall through to default.
  }
  return "dark";
}

function apply(theme: Theme): void {
  if (theme === "light") {
    document.documentElement.dataset.theme = "light";
  } else {
    delete document.documentElement.dataset.theme;
  }
}

// Applies the stored/default theme to <html>. Call once at boot, before the
// first view renders, so there's no flash of the wrong theme.
export function initTheme(): void {
  apply(currentTheme);
}

export function getTheme(): Theme {
  return currentTheme;
}

export function setTheme(theme: Theme): void {
  currentTheme = theme;
  apply(theme);
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Non-fatal — the choice just won't survive a reload.
  }
}
