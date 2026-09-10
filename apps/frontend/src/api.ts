import type {
  AuthMeResponse,
  EventDTO,
  EventInput,
  HealthResponse,
  LoginResponse,
  OtpResponse,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL;

export class ApiError extends Error {
  status: number;
  detail?: string;

  constructor(status: number, detail?: string) {
    super(detail ?? `Request failed with status ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

// Any 401 on a session-protected endpoint means the cookie is gone or expired;
// the app-level handler below forces a return to the login view instead of
// letting every view re-implement that check.
type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler): void {
  onUnauthorized = handler;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  opts: { treatUnauthorizedAsSessionLoss?: boolean } = {},
): Promise<T> {
  const { treatUnauthorizedAsSessionLoss = true } = opts;

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...options,
      credentials: "include",
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new ApiError(0, "Could not reach the server. Check your connection.");
  }

  if (res.status === 401 && treatUnauthorizedAsSessionLoss) {
    onUnauthorized?.();
  }

  if (!res.ok) {
    let detail: string | undefined;
    try {
      const body = await res.json();
      detail = body?.detail;
    } catch {
      // no JSON body, fall through with generic message
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return (await res.json()) as T;
}

export function login(user: string, password: string): Promise<LoginResponse> {
  return request<LoginResponse>(
    "/auth/login",
    { method: "POST", body: JSON.stringify({ user, password }) },
    { treatUnauthorizedAsSessionLoss: false },
  );
}

export function verifyOtp(code: string): Promise<OtpResponse> {
  return request<OtpResponse>(
    "/auth/otp",
    { method: "POST", body: JSON.stringify({ code }) },
    { treatUnauthorizedAsSessionLoss: false },
  );
}

export function fetchMe(): Promise<AuthMeResponse> {
  return request<AuthMeResponse>("/auth/me", {}, { treatUnauthorizedAsSessionLoss: false });
}

export function logout(): Promise<void> {
  return request<void>("/auth/logout", { method: "POST" }, { treatUnauthorizedAsSessionLoss: false });
}

export function fetchEvents(): Promise<EventDTO[]> {
  return request<EventDTO[]>("/events");
}

export function createEvent(input: EventInput): Promise<EventDTO> {
  return request<EventDTO>("/events", { method: "POST", body: JSON.stringify(input) });
}

export function updateEvent(id: string, input: EventInput): Promise<EventDTO> {
  return request<EventDTO>(`/events/${id}`, { method: "PUT", body: JSON.stringify(input) });
}

export function deleteEvent(id: string): Promise<void> {
  return request<void>(`/events/${id}`, { method: "DELETE" });
}

export function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}
