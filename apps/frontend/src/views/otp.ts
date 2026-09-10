import { ApiError, login, verifyOtp } from "../api";

const OTP_LENGTH = 6;
const DEFAULT_TTL_SECONDS = 120; // fallback shown until the backend exposes the real TTL

interface OtpViewOptions {
  user: string;
  password: string;
  onSuccess: () => void;
  onBackToLogin: () => void;
}

export function renderOtpView(root: HTMLElement, opts: OtpViewOptions): void {
  root.innerHTML = "";

  const shell = document.createElement("div");
  shell.className = "auth-shell";

  const card = document.createElement("div");
  card.className = "auth-card";
  card.innerHTML = `
    <div class="auth-eyebrow">Mesh Event Scheduler</div>
    <h1>Enter the code</h1>
    <p class="auth-subtitle">
      A one-time code was sent to <strong>#i2c-am2301</strong> on the mesh.
      Check that channel on your mesh radio and enter the 6 digits below.
    </p>
  `;

  const form = document.createElement("form");
  form.className = "auth-form";

  const boxRow = document.createElement("div");
  boxRow.className = "otp-boxes";
  const boxes: HTMLInputElement[] = [];
  for (let i = 0; i < OTP_LENGTH; i++) {
    const box = document.createElement("input");
    box.type = "text";
    box.inputMode = "numeric";
    box.pattern = "[0-9]*";
    box.maxLength = 1;
    box.className = "otp-box";
    box.autocomplete = i === 0 ? "one-time-code" : "off";
    box.setAttribute("aria-label", `Digit ${i + 1}`);
    boxes.push(box);
    boxRow.appendChild(box);
  }

  const timerRow = document.createElement("div");
  timerRow.className = "otp-timer-row";
  timerRow.innerHTML = `
    <span class="otp-timer hint-text"></span>
    <button type="button" class="btn btn-ghost otp-resend">Resend code</button>
  `;

  const errorEl = document.createElement("div");
  errorEl.className = "auth-error";
  errorEl.hidden = true;

  const actions = document.createElement("div");
  actions.className = "auth-actions";
  actions.innerHTML = `
    <button type="button" class="btn btn-secondary otp-back">Back</button>
    <button type="submit" class="btn btn-primary auth-submit">
      <span class="btn-label">Verify</span>
    </button>
  `;

  form.append(boxRow, timerRow, errorEl, actions);
  card.appendChild(form);
  shell.appendChild(card);
  root.appendChild(shell);

  const timerEl = timerRow.querySelector<HTMLSpanElement>(".otp-timer")!;
  const resendBtn = timerRow.querySelector<HTMLButtonElement>(".otp-resend")!;
  const backBtn = actions.querySelector<HTMLButtonElement>(".otp-back")!;
  const submitBtn = actions.querySelector<HTMLButtonElement>(".auth-submit")!;
  const submitLabel = actions.querySelector<HTMLSpanElement>(".btn-label")!;

  let secondsLeft = DEFAULT_TTL_SECONDS;
  let intervalId: ReturnType<typeof setInterval> | null = null;

  function tick(): void {
    secondsLeft -= 1;
    if (secondsLeft <= 0) {
      timerEl.textContent = "Code expired — request a new one.";
      resendBtn.disabled = false;
      if (intervalId) clearInterval(intervalId);
      return;
    }
    const m = Math.floor(secondsLeft / 60);
    const s = String(secondsLeft % 60).padStart(2, "0");
    timerEl.textContent = `Expires in ${m}:${s}`;
  }

  function startTimer(): void {
    secondsLeft = DEFAULT_TTL_SECONDS;
    resendBtn.disabled = true;
    tick();
    if (intervalId) clearInterval(intervalId);
    intervalId = setInterval(tick, 1000);
  }

  startTimer();
  boxes[0].focus();

  boxes.forEach((box, idx) => {
    box.addEventListener("input", () => {
      box.value = box.value.replace(/[^0-9]/g, "").slice(0, 1);
      if (box.value && idx < OTP_LENGTH - 1) {
        boxes[idx + 1].focus();
      }
    });
    box.addEventListener("keydown", (e) => {
      if (e.key === "Backspace" && !box.value && idx > 0) {
        boxes[idx - 1].focus();
      }
    });
    box.addEventListener("paste", (e) => {
      const text = e.clipboardData?.getData("text") ?? "";
      const digits = text.replace(/[^0-9]/g, "").slice(0, OTP_LENGTH);
      if (!digits) return;
      e.preventDefault();
      digits.split("").forEach((d, i) => {
        if (boxes[i]) boxes[i].value = d;
      });
      boxes[Math.min(digits.length, OTP_LENGTH) - 1].focus();
    });
  });

  function showError(message: string): void {
    errorEl.textContent = message;
    errorEl.hidden = false;
  }

  function setBusy(busy: boolean): void {
    submitBtn.disabled = busy;
    submitLabel.textContent = busy ? "Verifying…" : "Verify";
  }

  backBtn.addEventListener("click", () => {
    if (intervalId) clearInterval(intervalId);
    opts.onBackToLogin();
  });

  // The contract has no dedicated resend endpoint, so resending re-runs the
  // password login step (backend re-issues and re-sends a fresh OTP as a side effect).
  resendBtn.addEventListener("click", async () => {
    errorEl.hidden = true;
    resendBtn.disabled = true;
    resendBtn.textContent = "Sending…";
    try {
      await login(opts.user, opts.password);
      boxes.forEach((b) => (b.value = ""));
      boxes[0].focus();
      startTimer();
    } catch (err) {
      showError(err instanceof ApiError ? (err.detail ?? "Could not resend the code.") : "Could not resend the code.");
      resendBtn.disabled = false;
    } finally {
      resendBtn.textContent = "Resend code";
    }
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorEl.hidden = true;
    const code = boxes.map((b) => b.value).join("");
    if (code.length !== OTP_LENGTH) {
      showError(`Enter all ${OTP_LENGTH} digits.`);
      return;
    }

    setBusy(true);
    try {
      await verifyOtp(code);
      if (intervalId) clearInterval(intervalId);
      opts.onSuccess();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        showError(err.detail ?? "Incorrect or expired code.");
      } else {
        showError("Unexpected error verifying the code.");
      }
      boxes.forEach((b) => (b.value = ""));
      boxes[0].focus();
    } finally {
      setBusy(false);
    }
  });
}
