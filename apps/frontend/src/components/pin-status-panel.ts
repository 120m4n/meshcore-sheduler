// New, additive alongside the per-event echo badge in the event list
// (views/calendar.ts): that badge only shows a pin's echo next to an event
// configured on it, so a pin with no event ever gets no visibility. This
// panel shows the gateway's last-known state for all 8 pins at once,
// regardless of whether any event references them — same data
// (ActuatorStateSnapshot, pushed in real time), just a second, complete
// view of it.
import { colorForPin } from "../lib/colors";
import { formatAge, STALE_ECHO_SECONDS } from "../lib/next-occurrence";
import { t } from "../lib/i18n";
import type { ActuatorStateSnapshot } from "../types";

const PIN_COUNT = 8;

interface PinStatusPanelOptions {
  actuatorState: ActuatorStateSnapshot;
}

export function renderPinStatusPanel(root: HTMLElement, opts: PinStatusPanelOptions): void {
  root.innerHTML = "";

  const wrap = document.createElement("div");
  wrap.className = "pin-status-panel";
  wrap.setAttribute("role", "status");
  wrap.setAttribute("aria-label", t("pinStatusTitle"));

  for (let pin = 0; pin < PIN_COUNT; pin++) {
    const echo = opts.actuatorState[String(pin)];
    const chip = document.createElement("div");
    chip.className = "pin-status-chip";
    if (echo) {
      chip.classList.add(echo.state === "ON" ? "pin-status-chip-on" : "pin-status-chip-off");
      if (echo.age_seconds > STALE_ECHO_SECONDS) chip.classList.add("pin-status-chip-stale");
      chip.title = `${t("pin")} ${pin} — ${echo.state} · ${formatAge(echo.age_seconds)}`;
    } else {
      chip.classList.add("pin-status-chip-unknown");
      chip.title = `${t("pin")} ${pin} — ${t("noData")}`;
    }
    chip.innerHTML = `
      <span class="pin-status-dot" style="background:${colorForPin(pin)}"></span>
      <span class="pin-status-pin">${pin}</span>
      <span class="pin-status-value">${echo ? echo.state : t("noData")}</span>
    `;
    wrap.appendChild(chip);
  }

  root.appendChild(wrap);
}
