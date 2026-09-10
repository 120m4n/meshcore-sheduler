import { durationSeconds, MIN_DURATION_SECONDS } from "../lib/duration";
import type { EventDTO, EventInput, Recurrence } from "../types";

interface EventDrawerOptions {
  date: string;
  existing: EventDTO | null;
  // Prefilled ON/OFF, e.g. from clicking a slot in the week view — ignored
  // when editing an existing event.
  prefillOn?: string;
  prefillOff?: string;
  onSave: (input: EventInput) => Promise<void>;
  onDelete: (() => Promise<void>) | null;
  onClose: () => void;
}

export function renderEventDrawer(root: HTMLElement, opts: EventDrawerOptions): void {
  const { date, existing, prefillOn, prefillOff, onSave, onDelete, onClose } = opts;

  const overlay = document.createElement("div");
  overlay.className = "drawer-overlay";
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) onClose();
  });

  const drawer = document.createElement("div");
  drawer.className = "drawer";
  drawer.setAttribute("role", "dialog");
  drawer.setAttribute("aria-modal", "true");

  drawer.innerHTML = `
    <div class="drawer-header">
      <h2>${existing ? "Edit event" : "New event"}</h2>
      <button type="button" class="btn btn-ghost drawer-close" aria-label="Close">&times;</button>
    </div>
    <form class="drawer-form">
      <div class="field">
        <label for="ev-label">Label</label>
        <input id="ev-label" name="label" type="text" placeholder="Optional name for this event" />
      </div>

      <div class="field-row">
        <div class="field">
          <label for="ev-pin">Pin</label>
          <select id="ev-pin" name="pin"></select>
        </div>
        <div class="field">
          <label for="ev-recurrence">Recurrence</label>
          <select id="ev-recurrence" name="recurrence">
            <option value="once">Once</option>
            <option value="daily">Daily</option>
          </select>
        </div>
      </div>

      <div class="field-row">
        <div class="field">
          <label for="ev-start">Start date</label>
          <input id="ev-start" name="start_date" type="date" required />
        </div>
        <div class="field" id="ev-end-field">
          <label for="ev-end">End date</label>
          <input id="ev-end" name="end_date" type="date" />
        </div>
      </div>

      <div class="field-row">
        <div class="field">
          <label for="ev-on">ON time</label>
          <input id="ev-on" name="on_time" type="time" step="1" required />
        </div>
        <div class="field">
          <label for="ev-off">OFF time</label>
          <input id="ev-off" name="off_time" type="time" step="1" required />
        </div>
      </div>
      <p class="hint-text">If OFF is earlier than or equal to ON, the event is treated as crossing midnight. Minimum ${MIN_DURATION_SECONDS}s between ON and OFF.</p>

      <label class="toggle-row">
        <input id="ev-enabled" name="enabled" type="checkbox" />
        <span>Enabled</span>
      </label>

      <div class="drawer-error error-text" hidden></div>

      <div class="drawer-actions">
        ${existing ? '<button type="button" class="btn btn-danger drawer-delete">Delete</button>' : "<span></span>"}
        <div class="drawer-actions-right">
          <button type="button" class="btn btn-secondary drawer-cancel">Cancel</button>
          <button type="submit" class="btn btn-primary drawer-save">
            <span class="btn-label">${existing ? "Save changes" : "Create event"}</span>
          </button>
        </div>
      </div>
    </form>
  `;

  overlay.appendChild(drawer);
  root.appendChild(overlay);

  const pinSelect = drawer.querySelector<HTMLSelectElement>("#ev-pin")!;
  for (let i = 0; i <= 7; i++) {
    const option = document.createElement("option");
    option.value = String(i);
    option.textContent = `Pin ${i}`;
    pinSelect.appendChild(option);
  }

  const form = drawer.querySelector<HTMLFormElement>(".drawer-form")!;
  const labelInput = drawer.querySelector<HTMLInputElement>("#ev-label")!;
  const recurrenceSelect = drawer.querySelector<HTMLSelectElement>("#ev-recurrence")!;
  const startInput = drawer.querySelector<HTMLInputElement>("#ev-start")!;
  const endInput = drawer.querySelector<HTMLInputElement>("#ev-end")!;
  const endField = drawer.querySelector<HTMLDivElement>("#ev-end-field")!;
  const onInput = drawer.querySelector<HTMLInputElement>("#ev-on")!;
  const offInput = drawer.querySelector<HTMLInputElement>("#ev-off")!;
  const enabledInput = drawer.querySelector<HTMLInputElement>("#ev-enabled")!;
  const errorEl = drawer.querySelector<HTMLDivElement>(".drawer-error")!;
  const saveBtn = drawer.querySelector<HTMLButtonElement>(".drawer-save")!;
  const saveLabel = drawer.querySelector<HTMLSpanElement>(".btn-label")!;
  const deleteBtn = drawer.querySelector<HTMLButtonElement>(".drawer-delete");
  const closeBtn = drawer.querySelector<HTMLButtonElement>(".drawer-close")!;
  const cancelBtn = drawer.querySelector<HTMLButtonElement>(".drawer-cancel")!;

  if (existing) {
    labelInput.value = existing.label ?? "";
    pinSelect.value = String(existing.pin);
    recurrenceSelect.value = existing.recurrence;
    startInput.value = existing.start_date;
    endInput.value = existing.end_date ?? "";
    onInput.value = existing.on_time;
    offInput.value = existing.off_time;
    enabledInput.checked = existing.enabled;
  } else {
    pinSelect.value = "0";
    recurrenceSelect.value = "once";
    startInput.value = date;
    onInput.value = prefillOn ?? "08:00:00";
    offInput.value = prefillOff ?? "18:00:00";
    enabledInput.checked = true;
  }

  function syncEndFieldState(): void {
    const isDaily = recurrenceSelect.value === "daily";
    endInput.disabled = !isDaily;
    endField.style.opacity = isDaily ? "1" : "0.5";
    if (!isDaily) endInput.value = "";
  }
  syncEndFieldState();
  recurrenceSelect.addEventListener("change", syncEndFieldState);

  function close(): void {
    root.innerHTML = "";
    onClose();
  }
  closeBtn.addEventListener("click", close);
  cancelBtn.addEventListener("click", close);
  document.addEventListener("keydown", function onKey(e) {
    if (e.key === "Escape") {
      document.removeEventListener("keydown", onKey);
      close();
    }
  });

  function showError(message: string): void {
    errorEl.textContent = message;
    errorEl.hidden = false;
  }

  if (deleteBtn && onDelete) {
    deleteBtn.addEventListener("click", async () => {
      const confirmed = window.confirm(
        "Delete this event? This changes the actuator's schedule immediately.",
      );
      if (!confirmed) return;
      deleteBtn.disabled = true;
      try {
        await onDelete();
        close();
      } catch {
        showError("Could not delete the event. Please try again.");
        deleteBtn.disabled = false;
      }
    });
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorEl.hidden = true;

    const recurrence = recurrenceSelect.value as Recurrence;
    const input: EventInput = {
      label: labelInput.value.trim() || null,
      pin: Number(pinSelect.value),
      recurrence,
      start_date: startInput.value,
      end_date: recurrence === "daily" && endInput.value ? endInput.value : null,
      on_time: onInput.value,
      off_time: offInput.value,
      enabled: enabledInput.checked,
    };

    if (!input.start_date || !input.on_time || !input.off_time) {
      showError("Start date, ON time, and OFF time are required.");
      return;
    }
    if (input.recurrence === "daily" && input.end_date && input.end_date < input.start_date) {
      showError("End date cannot be before the start date.");
      return;
    }
    if (durationSeconds(input.on_time, input.off_time) < MIN_DURATION_SECONDS) {
      showError(`ON/OFF must be at least ${MIN_DURATION_SECONDS} seconds apart.`);
      return;
    }

    saveBtn.disabled = true;
    saveLabel.textContent = "Saving…";
    try {
      await onSave(input);
      close();
    } catch {
      showError("Could not save the event. Please try again.");
      saveBtn.disabled = false;
      saveLabel.textContent = existing ? "Save changes" : "Create event";
    }
  });
}
