import { ApiError, devLogin, login } from "../api";
import { t } from "../lib/i18n";

interface LoginViewOptions {
  onSuccess: (user: string, password: string) => void;
  // Bypasses the OTP step entirely (dev-login authenticates directly), so
  // this takes a distinct callback rather than reusing onSuccess.
  onDevBypass?: () => void;
}

export function renderLoginView(root: HTMLElement, { onSuccess, onDevBypass }: LoginViewOptions): void {
  root.innerHTML = "";

  const shell = document.createElement("div");
  shell.className = "auth-shell";

  const card = document.createElement("div");
  card.className = "auth-card";

  card.innerHTML = `
    <div class="auth-eyebrow">${t("appName")}</div>
    <h1>${t("signIn")}</h1>
    <p class="auth-subtitle">${t("signInSubtitle")}</p>
  `;

  const form = document.createElement("form");
  form.className = "auth-form";
  form.innerHTML = `
    <div class="field">
      <label for="login-user">${t("username")}</label>
      <input id="login-user" name="user" type="text" autocomplete="username" required autofocus />
    </div>
    <div class="field">
      <label for="login-password">${t("password")}</label>
      <input id="login-password" name="password" type="password" autocomplete="current-password" required />
    </div>
    <div class="auth-error" hidden></div>
    <button type="submit" class="btn btn-primary auth-submit">
      <span class="spinner btn-spinner" hidden></span>
      <span class="btn-label">${t("continueLabel")}</span>
    </button>
  `;

  const errorEl = form.querySelector<HTMLDivElement>(".auth-error")!;
  const submitBtn = form.querySelector<HTMLButtonElement>(".auth-submit")!;
  const submitLabel = form.querySelector<HTMLSpanElement>(".btn-label")!;
  const submitSpinner = form.querySelector<HTMLSpanElement>(".btn-spinner")!;
  const userInput = form.querySelector<HTMLInputElement>("#login-user")!;
  const passwordInput = form.querySelector<HTMLInputElement>("#login-password")!;
  userInput.focus();

  function setBusy(busy: boolean): void {
    submitBtn.disabled = busy;
    submitSpinner.hidden = !busy;
    submitLabel.textContent = busy ? t("signingIn") : t("continueLabel");
  }

  function showError(message: string): void {
    errorEl.textContent = message;
    errorEl.hidden = false;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorEl.hidden = true;
    const user = userInput.value.trim();
    const password = passwordInput.value;
    if (!user || !password) return;

    setBusy(true);
    try {
      await login(user, password);
      onSuccess(user, password);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        showError(t("incorrectCredentials"));
      } else if (err instanceof ApiError) {
        showError(err.detail ?? t("signInFailed"));
      } else {
        showError(t("unexpectedError"));
      }
      passwordInput.value = "";
      passwordInput.focus();
    } finally {
      setBusy(false);
    }
  });

  card.appendChild(form);

  // Dev-only escape hatch to skip password+OTP while testing the UI. Only
  // rendered in a Vite dev build; the backend endpoint itself 404s unless
  // DEV_AUTH_BYPASS=true is set in its .env, so this is inert everywhere
  // except an explicitly opted-in local setup.
  if (import.meta.env.DEV && onDevBypass) {
    const devBtn = document.createElement("button");
    devBtn.type = "button";
    devBtn.className = "btn btn-ghost btn-sm auth-dev-bypass";
    devBtn.textContent = t("devBypass");
    devBtn.addEventListener("click", async () => {
      devBtn.disabled = true;
      try {
        await devLogin();
        onDevBypass();
      } catch {
        devBtn.disabled = false;
        devBtn.textContent = t("devBypassUnavailable");
      }
    });
    card.appendChild(devBtn);
  }

  shell.appendChild(card);
  root.appendChild(shell);
}
