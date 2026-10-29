import { ConnectError, createClient } from "@connectrpc/connect";
import { createConnectTransport } from "@connectrpc/connect-web";

import { GantryAppService } from "../gen/app_pb";
import type { CommandResult } from "../gen/app_pb";

/** Backend RPC root; override with VITE_API_URL (e.g. in a .env.local file). */
const API_BASE_URL: string =
  import.meta.env.VITE_API_URL ?? "http://localhost:8000/rpc";

const transport = createConnectTransport({
  baseUrl: API_BASE_URL,
  // The backend only speaks the Connect protocol's JSON encoding.
  useBinaryFormat: false,
});

/** Typed client for every backend action and the telemetry stream. */
export const gantry = createClient(GantryAppService, transport);

/** Outcome of a command: `error` is empty on success. */
export interface CommandOutcome {
  ok: boolean;
  error: string;
}

/**
 * Run a command and fold every failure into a CommandOutcome: refusals come
 * back from the backend as `{ok: false, error}`, while network or protocol
 * failures (backend down, bad response) are thrown by the client.
 */
export async function runCommand(
  call: () => Promise<CommandResult>,
): Promise<CommandOutcome> {
  try {
    const result = await call();
    return { ok: result.ok, error: result.error };
  } catch (err) {
    return { ok: false, error: describeError(err) };
  }
}

function describeError(err: unknown): string {
  if (err instanceof ConnectError) {
    return `Backend unreachable or failed: ${err.rawMessage}`;
  }
  return err instanceof Error ? err.message : String(err);
}
