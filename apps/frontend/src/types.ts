export type Recurrence = "once" | "daily";

export interface EventDTO {
  id: string;
  label: string | null;
  pin: number;
  recurrence: Recurrence;
  start_date: string;
  end_date: string | null;
  on_time: string; // "HH:MM:SS", local to the fixed server TZ
  off_time: string; // "HH:MM:SS" — must be strictly after on_time, same day (no midnight-crossing)
  enabled: boolean;
  created_by: string;
}

export type EventInput = Omit<EventDTO, "id" | "created_by">;

export type AuthState = "unauthenticated" | "pending_otp" | "authenticated";

export interface AuthMeResponse {
  status: AuthState;
  user?: string;
}

export interface LoginResponse {
  pending_otp: true;
}

export interface OtpResponse {
  authenticated: true;
}

// Last echo the gateway has observed per pin, decoupled from anything this
// process sent — see app/mesh/gateway.py. age_seconds is the server's own
// staleness measurement (time.monotonic() at observation), not something
// the client should try to keep ticking locally.
export interface ActuatorPinState {
  state: "ON" | "OFF";
  age_seconds: number;
}

export interface HealthResponse {
  mesh_connected: boolean;
  actuator_state: Record<string, ActuatorPinState>;
}
