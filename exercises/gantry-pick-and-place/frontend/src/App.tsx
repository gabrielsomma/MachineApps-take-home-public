import { useState } from "react";
import { toJson } from "@bufbuild/protobuf";

import { TelemetrySchema } from "./gen/app_pb";
import { API_BASE_URL, gantry, runCommand } from "./api/client";
import type { CommandOutcome } from "./api/client";
import { useTelemetry } from "./api/useTelemetry";

/**
 * Temporary connection check page (Step 4): live telemetry and a Home button.
 * Replaced by the real dashboard in Step 5.
 */
export default function App() {
  const { telemetry, connection } = useTelemetry();
  const [lastCommand, setLastCommand] = useState<CommandOutcome | null>(null);
  const [busy, setBusy] = useState(false);

  async function home() {
    setBusy(true);
    setLastCommand(await runCommand(() => gantry.home_robot({})));
    setBusy(false);
  }

  return (
    <main className="connection-check">
      <h1>Gantry backend connection</h1>
      <p>
        Backend: <code>{API_BASE_URL}</code> —{" "}
        <span className={`badge badge-${connection}`}>{connection}</span>
      </p>

      <button type="button" onClick={home} disabled={busy || connection !== "connected"}>
        Home robot
      </button>
      {lastCommand && (
        <p className={lastCommand.ok ? "ok" : "error"}>
          {lastCommand.ok ? "Home accepted" : `Refused: ${lastCommand.error}`}
        </p>
      )}

      <h2>Live telemetry</h2>
      <pre>
        {telemetry
          ? JSON.stringify(toJson(TelemetrySchema, telemetry, { alwaysEmitImplicit: true }), null, 2)
          : "Waiting…"}
      </pre>
    </main>
  );
}
