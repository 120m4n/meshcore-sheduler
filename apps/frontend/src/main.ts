import "./style.css";
import "./app.css";
import { fetchMe, setUnauthorizedHandler } from "./api";
import { t } from "./lib/i18n";
import { initTheme } from "./lib/theme";
import { renderLoginView } from "./views/login";
import { renderOtpView } from "./views/otp";
import { renderCalendarView } from "./views/calendar";

initTheme();

const root = document.getElementById("app")!;

// Held in memory only for the "resend code" action, which re-submits the
// login step; never persisted (no localStorage/sessionStorage for credentials).
let pendingCredentials: { user: string; password: string } | null = null;

function showLogin(): void {
  pendingCredentials = null;
  renderLoginView(root, {
    onSuccess: (user, password) => {
      // Kept in memory only to support "resend code" without asking the
      // user to retype it; never persisted to storage.
      pendingCredentials = { user, password };
      showOtp(user);
    },
    onDevBypass: async () => {
      const me = await fetchMe();
      if (me.status === "authenticated" && me.user) {
        showCalendar(me.user);
      }
    },
  });
}

function showOtp(user: string): void {
  if (!pendingCredentials) {
    showLogin();
    return;
  }
  renderOtpView(root, {
    user: pendingCredentials.user,
    password: pendingCredentials.password,
    onSuccess: () => {
      pendingCredentials = null;
      showCalendar(user);
    },
    onBackToLogin: showLogin,
  });
}

function showCalendar(user: string): void {
  renderCalendarView(root, {
    user,
    onLoggedOut: showLogin,
  });
}

function showLoadError(): void {
  root.innerHTML = `
    <div class="auth-shell">
      <div class="auth-card">
        <div class="auth-eyebrow">${t("appName")}</div>
        <h1>${t("cantReachServer")}</h1>
        <p class="auth-subtitle">${t("checkBackendRunning")}</p>
        <button type="button" class="btn btn-primary auth-submit" id="retry-btn">${t("retry")}</button>
      </div>
    </div>
  `;
  document.getElementById("retry-btn")!.addEventListener("click", boot);
}

async function boot(): Promise<void> {
  root.innerHTML = `<div class="loading-block">${t("loading")}</div>`;
  try {
    const me = await fetchMe();
    if (me.status === "authenticated" && me.user) {
      showCalendar(me.user);
    } else {
      showLogin();
    }
  } catch {
    showLoadError();
  }
}

setUnauthorizedHandler(() => {
  showLogin();
});

boot();
