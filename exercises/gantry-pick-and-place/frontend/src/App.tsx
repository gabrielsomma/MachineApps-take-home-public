import { useState } from "react";

import { gantry, runCommand } from "./api/client";
import type { CommandOutcome } from "./api/client";
import { useConfig } from "./api/useConfig";
import { useTelemetry } from "./api/useTelemetry";
import type { CommandResult } from "./gen/app_pb";
import { CommandToast, ConnectionBanner, FaultBanner } from "./components/Banners";
import { ConfigForm } from "./components/ConfigForm";
import type { ConfigInit, ConfigPreview } from "./components/ConfigForm";
import { Controls } from "./components/Controls";
import type { CommandName } from "./components/Controls";
import { JogForm } from "./components/JogForm";
import { TelemetryPanel } from "./components/TelemetryPanel";
import { TopView } from "./components/TopView";
import { ZGauge } from "./components/ZGauge";
import { toVec3 } from "./model/format";
import { tablePointToRobotFrame } from "./model/geometry";
import { describeState, permissions } from "./model/machineState";

const COMMANDS: Record<CommandName, () => Promise<CommandResult>> = {
  home: () => gantry.home_robot({}),
  start: () => gantry.start_sequence({}),
  stop: () => gantry.stop({}),
  reset: () => gantry.reset_fault({}),
};

export default function App() {
  const { telemetry, connection } = useTelemetry();
  const { config, reload } = useConfig(connection);
  const [pending, setPending] = useState<CommandName | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [preview, setPreview] = useState<ConfigPreview>({});

  const connected = connection === "connected";
  const state = describeState(telemetry?.state);
  const allowed = permissions(telemetry?.state, connected);

  async function command(name: CommandName) {
    setPending(name);
    const outcome = await runCommand(COMMANDS[name]);
    setPending(null);
    setToast(outcome.ok ? null : outcome.error);
  }

  async function saveConfig(init: ConfigInit): Promise<CommandOutcome> {
    const outcome = await runCommand(() => gantry.set_config(init));
    if (outcome.ok) await reload();
    return outcome;
  }

  const robot = telemetry ? toVec3(telemetry.position) : null;
  const cubeStart = config?.cube ? tablePointToRobotFrame("A", config.cube.x, config.cube.y) : null;

  return (
    <div className="app">
      <header className="app-header">
        <h1>Gantry Pick &amp; Place</h1>
        <div className="header-status">
          <span className={`badge badge-${connection}`}>{connection}</span>
          {telemetry && <span className={`badge state-badge state-${state.kind}`}>{state.label}</span>}
        </div>
      </header>

      <div className="banners">
        <ConnectionBanner connection={connection} />
        {telemetry?.state === "fault" && (
          <FaultBanner message={telemetry.error} canReset={allowed.reset && pending === null} onReset={() => void command("reset")} />
        )}
        {toast && <CommandToast message={toast} onDismiss={() => setToast(null)} />}
      </div>

      <main className={connected ? "layout" : "layout stale"}>
        <section className="panel cell" aria-labelledby="cell-title">
          <h2 id="cell-title">Cell — top view</h2>
          <div className="cell-views">
            <TopView
              robot={robot}
              gripperClosed={telemetry?.gripperClosed ?? false}
              cube={telemetry ? toVec3(telemetry.cubePosition) : null}
              destination={telemetry ? toVec3(telemetry.destinationPosition) : null}
              cubeStart={cubeStart}
              home={config?.home ? [config.home.x, config.home.y] : null}
              preview={preview}
            />
            <ZGauge z={robot ? robot[2] : null} safeZ={config?.safeZ ?? 0} pickZ={config?.pickZ ?? -300} />
          </div>
          <ul className="legend">
            <li><span className="swatch swatch-head" /> Gripper (solid ring = closed)</li>
            <li><span className="swatch swatch-cube" /> Cube</li>
            <li><span className="swatch swatch-destination" /> Destination</li>
            <li><span className="swatch swatch-ghost" /> Unsaved position</li>
            <li><span className="swatch swatch-home" /> Home</li>
          </ul>
        </section>

        <div className="side">
          <TelemetryPanel telemetry={telemetry} />
          <Controls allowed={allowed} pending={pending} onCommand={(name) => void command(name)} />
          <ConfigForm saved={config} enabled={allowed.editConfig} onSave={saveConfig} onPreview={setPreview} />
          <JogForm
            enabled={allowed.jog}
            onMove={(x, y, z) => runCommand(() => gantry.move_robot({ x, y, z }))}
          />
        </div>
      </main>
    </div>
  );
}
