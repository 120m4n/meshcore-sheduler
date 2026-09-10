import "./style.css";
import "./app.css";
import { fetchMe, setUnauthorizedHandler } from "./api";
import { renderLoginView } from "./views/login";
import { renderOtpView } from "./views/otp";
import { renderCalendarView } from "./views/calendar";

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
        <div class="auth-eyebrow">Mesh Event Scheduler</div>
        <h1>Can't reach the server</h1>
        <p class="auth-subtitle">Check that the backend is running and try again.</p>
        <button type="button" class="btn btn-primary auth-submit" id="retry-btn">Retry</button>
      </div>
    </div>
  `;
  document.getElementById("retry-btn")!.addEventListener("click", boot);
}

async function boot(): Promise<void> {
  root.innerHTML = '<div class="loading-block">Loading…</div>';
  try {
    const me = await fetchMe();
    if (me.state === "authenticated" && me.user) {
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
