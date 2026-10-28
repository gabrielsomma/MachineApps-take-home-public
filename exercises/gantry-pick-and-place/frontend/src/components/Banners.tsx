import type { ConnectionState } from "../api/useTelemetry";

export function ConnectionBanner({ connection }: { connection: ConnectionState }) {
  if (connection === "connected") return null;
  return (
    <div className="banner banner-warning" role="status">
      {connection === "connecting"
        ? "Connecting to the backend…"
        : "Backend disconnected — reconnecting. Values below are the last ones received."}
    </div>
  );
}

export interface FaultBannerProps {
  message: string;
  canReset: boolean;
  onReset: () => void;
}

export function FaultBanner({ message, canReset, onReset }: FaultBannerProps) {
  return (
    <div className="banner banner-error" role="alert">
      <div>
        <strong>Fault:</strong> {message || "Unknown error"}
        <div className="banner-detail">Motion is stopped. Reset to return to ready.</div>
      </div>
      <button type="button" onClick={onReset} disabled={!canReset}>
        Reset
      </button>
    </div>
  );
}

/** A command refused by the backend (or a failed call), shown until dismissed or replaced. */
export function CommandToast({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  return (
    <div className="banner banner-notice" role="status">
      <span>{message}</span>
      <button type="button" className="link" onClick={onDismiss} aria-label="Dismiss">
        ✕
      </button>
    </div>
  );
}
