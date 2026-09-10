// Minimal i18n: a flat key -> string dict per language, an active-language
// module variable, and t(key, params) for {placeholder} interpolation.
// Spanish by default; English only if the user explicitly switches (stored
// in localStorage so the choice sticks across reloads). No framework, no
// pluralization rules, no date/number formatting layer — this app's copy
// doesn't need any of that, and a bigger i18n library would be solving a
// problem this project doesn't have.

export type Lang = "es" | "en";

const STORAGE_KEY = "mesh-scheduler-lang";

const dict = {
  es: {
    appName: "Programador de Actuadores",
    calendar: "Calendario",
    week: "Semana",
    month: "Mes",
    today: "Hoy",
    allEvents: "Todos los eventos",
    noEventsYet: "Aún no hay eventos programados. Hacé clic en un día del calendario para agregar uno.",
    noEventsThisWeek: "No hay eventos esta semana — hacé clic en una hora para agregar uno.",
    noEventsThisDay: "No hay eventos este día — tocá abajo para agregar uno.",
    noDailyEventsThisWeek: "No hay eventos diarios recurrentes esta semana.",
    addEvent: "Agregar evento",
    logOut: "Cerrar sesión",
    checkNow: "Verificar ahora",
    meshConnected: "Mesh conectado",
    meshOffline: "Mesh desconectado",
    checkingMesh: "Verificando mesh…",
    loadingCalendar: "Cargando calendario…",
    couldNotLoadEvents: "No se pudieron cargar los eventos.",
    couldNotMoveEvent: "No se pudo mover el evento.",
    daily: "Diario",
    once: "Una vez",
    saved: 'Guardado "{name}".',
    created: 'Creado "{name}".',
    deleted: 'Eliminado "{name}".',
    // event drawer
    editEvent: "Editar evento",
    newEvent: "Nuevo evento",
    close: "Cerrar",
    label: "Nombre",
    labelPlaceholder: "Nombre opcional para este evento",
    pin: "Pin",
    recurrence: "Recurrencia",
    startDate: "Fecha de inicio",
    endDate: "Fecha de fin",
    onTime: "Hora ON",
    offTime: "Hora OFF",
    minDurationHint: "OFF debe ser al menos {seconds} segundos después de ON, el mismo día (los eventos no pueden cruzar medianoche).",
    enabled: "Habilitado",
    delete: "Eliminar",
    cancel: "Cancelar",
    saveChanges: "Guardar cambios",
    createEvent: "Crear evento",
    saving: "Guardando…",
    deleteConfirm: "¿Eliminar este evento? Esto cambia la programación del actuador de inmediato.",
    couldNotDelete: "No se pudo eliminar el evento. Probá de nuevo.",
    couldNotSave: "No se pudo guardar el evento. Probá de nuevo.",
    requiredFields: "Fecha de inicio, hora ON y hora OFF son obligatorias.",
    endBeforeStart: "La fecha de fin no puede ser anterior a la de inicio.",
    offBeforeOn: "La hora OFF debe ser posterior a ON (los eventos no pueden cruzar medianoche).",
    minDurationError: "ON/OFF deben estar separados por al menos {seconds} segundos.",
    minDurationErrorSameDay: "ON/OFF deben estar separados por al menos {seconds} segundos, el mismo día.",
    overlapError: "Se superpone con un evento existente en el pin {pin}: {event}",
    longDurationWarning: "Este evento dura {hours}h — confirmá que sea intencional.",
    // login
    signIn: "Iniciar sesión",
    signInSubtitle: "El acceso está limitado a operadores registrados.",
    username: "Usuario",
    password: "Contraseña",
    continueLabel: "Continuar",
    signingIn: "Iniciando sesión…",
    incorrectCredentials: "Usuario o contraseña incorrectos.",
    signInFailed: "Error al iniciar sesión. Probá de nuevo.",
    unexpectedError: "Error inesperado. Probá de nuevo.",
    devBypass: "Bypass de desarrollo (omitir login)",
    devBypassUnavailable: "Bypass no disponible (configurar DEV_AUTH_BYPASS=true)",
    // otp
    enterCode: "Ingresá el código",
    otpSubtitle: "Se envió un código de un solo uso a {channel} en la mesh. Revisá ese canal en tu radio mesh e ingresá los 6 dígitos.",
    expiresIn: "Expira en {time}",
    codeExpired: "Código expirado — pedí uno nuevo.",
    resendCode: "Reenviar código",
    sending: "Enviando…",
    back: "Volver",
    verify: "Verificar",
    verifying: "Verificando…",
    enterAllDigits: "Ingresá los {count} dígitos.",
    digitLabel: "Dígito {n}",
    incorrectOrExpired: "Código incorrecto o expirado.",
    couldNotResend: "No se pudo reenviar el código.",
    // health
    cantReachServer: "No se puede conectar al servidor",
    checkBackendRunning: "Verificá que el backend esté corriendo e intentá de nuevo.",
    retry: "Reintentar",
    loading: "Cargando…",
    lastEchoTitle: "Último eco del actuador en este pin, no necesariamente de este evento",
    // language toggle
    language: "Idioma",
  },
  en: {
    appName: "Actuator Scheduler",
    calendar: "Calendar",
    week: "Week",
    month: "Month",
    today: "Today",
    allEvents: "All events",
    noEventsYet: "No events scheduled yet. Click a day on the calendar to add one.",
    noEventsThisWeek: "No events this week — click any hour to add one.",
    noEventsThisDay: "No events this day — tap below to add one.",
    noDailyEventsThisWeek: "No recurring (daily) events this week.",
    addEvent: "Add event",
    logOut: "Log out",
    checkNow: "Check now",
    meshConnected: "Mesh connected",
    meshOffline: "Mesh offline",
    checkingMesh: "Checking mesh…",
    loadingCalendar: "Loading calendar…",
    couldNotLoadEvents: "Could not load events.",
    couldNotMoveEvent: "Could not move the event.",
    daily: "Daily",
    once: "Once",
    saved: 'Saved "{name}".',
    created: 'Created "{name}".',
    deleted: 'Deleted "{name}".',
    editEvent: "Edit event",
    newEvent: "New event",
    close: "Close",
    label: "Label",
    labelPlaceholder: "Optional name for this event",
    pin: "Pin",
    recurrence: "Recurrence",
    startDate: "Start date",
    endDate: "End date",
    onTime: "ON time",
    offTime: "OFF time",
    minDurationHint: "OFF must be at least {seconds} seconds after ON, same day (events can't cross midnight).",
    enabled: "Enabled",
    delete: "Delete",
    cancel: "Cancel",
    saveChanges: "Save changes",
    createEvent: "Create event",
    saving: "Saving…",
    deleteConfirm: "Delete this event? This changes the actuator's schedule immediately.",
    couldNotDelete: "Could not delete the event. Please try again.",
    couldNotSave: "Could not save the event. Please try again.",
    requiredFields: "Start date, ON time, and OFF time are required.",
    endBeforeStart: "End date cannot be before the start date.",
    offBeforeOn: "OFF time must be after ON time (events can't cross midnight).",
    minDurationError: "ON/OFF must be at least {seconds} seconds apart.",
    minDurationErrorSameDay: "ON/OFF must be at least {seconds} seconds apart, same day.",
    overlapError: "Overlaps with existing event on pin {pin}: {event}",
    longDurationWarning: "This event runs for {hours}h — double-check that's intended.",
    signIn: "Sign in",
    signInSubtitle: "Access is limited to registered operators.",
    username: "Username",
    password: "Password",
    continueLabel: "Continue",
    signingIn: "Signing in…",
    incorrectCredentials: "Incorrect username or password.",
    signInFailed: "Sign-in failed. Please try again.",
    unexpectedError: "Unexpected error. Please try again.",
    devBypass: "Dev bypass (skip login)",
    devBypassUnavailable: "Dev bypass unavailable (set DEV_AUTH_BYPASS=true)",
    enterCode: "Enter the code",
    otpSubtitle: "A one-time code was sent to {channel} on the mesh. Check that channel on your mesh radio and enter the 6 digits below.",
    expiresIn: "Expires in {time}",
    codeExpired: "Code expired — request a new one.",
    resendCode: "Resend code",
    sending: "Sending…",
    back: "Back",
    verify: "Verify",
    verifying: "Verifying…",
    enterAllDigits: "Enter all {count} digits.",
    digitLabel: "Digit {n}",
    incorrectOrExpired: "Incorrect or expired code.",
    couldNotResend: "Could not resend the code.",
    cantReachServer: "Can't reach the server",
    checkBackendRunning: "Check that the backend is running and try again.",
    retry: "Retry",
    loading: "Loading…",
    lastEchoTitle: "Last echo from the actuator on this pin, not necessarily from this event",
    language: "Language",
  },
} as const;

export type TKey = keyof typeof dict.es;

let currentLang: Lang = readStoredLang();

function readStoredLang(): Lang {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "en" || stored === "es") return stored;
  } catch {
    // localStorage unavailable (private mode etc.) — fall through to default.
  }
  return "es";
}

export function getLang(): Lang {
  return currentLang;
}

export function setLang(lang: Lang): void {
  currentLang = lang;
  try {
    localStorage.setItem(STORAGE_KEY, lang);
  } catch {
    // Non-fatal — the choice just won't survive a reload.
  }
}

export function t(key: TKey, params?: Record<string, string | number>): string {
  let str: string = dict[currentLang][key];
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      str = str.replace(`{${k}}`, String(v));
    }
  }
  return str;
}
