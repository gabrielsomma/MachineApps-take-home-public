import { useCallback, useEffect, useState } from "react";

import type { Config } from "../gen/app_pb";
import { gantry } from "./client";
import type { ConnectionState } from "./useTelemetry";

/**
 * The configuration saved on the backend. Loaded whenever the telemetry
 * connection (re)connects, and on demand via `reload` (e.g. after saving).
 */
export function useConfig(connection: ConnectionState): {
  config: Config | null;
  reload: () => Promise<void>;
} {
  const [config, setConfig] = useState<Config | null>(null);

  const reload = useCallback(async () => {
    try {
      setConfig(await gantry.get_config({}));
    } catch {
      // Backend unreachable: keep the last known config; the connection
      // banner already tells the user.
    }
  }, []);

  useEffect(() => {
    if (connection === "connected") void reload();
  }, [connection, reload]);

  return { config, reload };
}
