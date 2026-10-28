import type { Telemetry } from "../gen/app_pb";
import { mm, toVec3 } from "../model/format";
import { describeState } from "../model/machineState";

export function TelemetryPanel({ telemetry }: { telemetry: Telemetry | null }) {
  const state = describeState(telemetry?.state);
  const [x, y, z] = toVec3(telemetry?.position);
  const [cx, cy, cz] = toVec3(telemetry?.cubePosition);
  const [dx, dy, dz] = toVec3(telemetry?.destinationPosition);

  return (
    <section className="panel telemetry" aria-labelledby="telemetry-title">
      <h2 id="telemetry-title">Status</h2>

      <div className={`state state-${state.kind}`}>
        <span className="state-label">{telemetry ? state.label : "Waiting for data…"}</span>
        {state.step && (
          <span className="state-step">
            step {state.step.index} of {state.step.total}
          </span>
        )}
      </div>
      {state.step && (
        <progress className="sequence-progress" max={state.step.total} value={state.step.index} />
      )}

      <dl className="readouts">
        <dt>Robot X / Y / Z</dt>
        <dd className="mono">
          {mm(x)} / {mm(y)} / {mm(z)}
        </dd>
        <dt>Gripper</dt>
        <dd>{telemetry?.gripperClosed ? "Closed" : "Open"}</dd>
        <dt>Motion</dt>
        <dd>{telemetry?.moving ? "Moving" : "Idle"}</dd>
        <dt>Cube</dt>
        <dd className="mono">
          {mm(cx)} / {mm(cy)} / {mm(cz)}
        </dd>
        <dt>Destination</dt>
        <dd className="mono">
          {mm(dx)} / {mm(dy)} / {mm(dz)}
        </dd>
      </dl>
      <p className="hint">Positions in robot coordinates (mm), origin at the cell centre.</p>
    </section>
  );
}
