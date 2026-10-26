import { useEffect, useState } from "react";

import type { Telemetry } from "../gen/app_pb";
import { gantry } from "./client";

export type ConnectionState = "connecting" | "connected" | "disconnected";

/** No message for this long means the stream is dead (it normally sends ~20/s). */
const STALE_AFTER_MS = 2000;
const RETRY_AFTER_MS = 1000;

/**
 * Subscribe to the backend's telemetry stream and keep it alive.
 *
 * Reconnects after errors (backend restarted, network drop) and after a
 * silent stall. While disconnected, `telemetry` keeps the last value received
 * so the UI can show it greyed out rather than blank.
 */
export function useTelemetry(): {
  telemetry: Telemetry | null;
  connection: ConnectionState;
} {
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [connection, setConnection] = useState<ConnectionState>("connecting");

  useEffect(() => {
    const unmounted = new AbortController();

    async function run(): Promise<void> {
      while (!unmounted.signal.aborted) {
        // One controller per attempt, so the watchdog can drop a stalled
        // stream without ending the whole loop.
        const attempt = new AbortController();
        const abortAttempt = () => attempt.abort();
        unmounted.signal.addEventListener("abort", abortAttempt);
        let watchdog = setTimeout(abortAttempt, STALE_AFTER_MS);

        try {
          for await (const message of gantry.telemetry({}, { signal: attempt.signal })) {
            clearTimeout(watchdog);
            watchdog = setTimeout(abortAttempt, STALE_AFTER_MS);
            setTelemetry(message);
            setConnection("connected");
          }
        } catch {
          // Error or abort: handled below by reconnecting (unless unmounted).
        } finally {
          clearTimeout(watchdog);
          unmounted.signal.removeEventListener("abort", abortAttempt);
        }

        if (unmounted.signal.aborted) return;
        setConnection("disconnected");
        await sleep(RETRY_AFTER_MS);
      }
    }

    void run();
    return () => unmounted.abort();
  }, []);

  return { telemetry, connection };
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
