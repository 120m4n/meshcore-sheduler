export type Recurrence = "once" | "daily";

export interface EventDTO {
  id: string;
  label: string | null;
  pin: number;
  recurrence: Recurrence;
  start_date: string;
  end_date: string | null;
  on_time: string; // "HH:MM:SS", local to the fixed server TZ
  off_time: string; // "HH:MM:SS" — off_time <= on_time means it wraps past midnight
  enabled: boolean;
  created_by: string;
}

export type EventInput = Omit<EventDTO, "id" | "created_by">;

export type AuthState = "unauthenticated" | "pending" | "authenticated";

export interface AuthMeResponse {
  state: AuthState;
  user?: string;
}

export interface LoginResponse {
  pending_otp: true;
}

export interface OtpResponse {
  authenticated: true;
}

export interface HealthResponse {
  mesh_connected: boolean;
}
