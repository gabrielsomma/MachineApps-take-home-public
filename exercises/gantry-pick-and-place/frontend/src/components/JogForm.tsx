import { useState } from "react";
import type { FormEvent } from "react";

import type { CommandOutcome } from "../api/client";

export interface JogFormProps {
  enabled: boolean;
  onMove: (x: number, y: number, z: number) => Promise<CommandOutcome>;
}

/** Move the robot to an absolute position (robot frame), via the move_robot action. */
export function JogForm({ enabled, onMove }: JogFormProps) {
  const [target, setTarget] = useState({ x: "0", y: "0", z: "0" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const values = [target.x, target.y, target.z].map((text) => (text.trim() === "" ? NaN : Number(text)));
  const valid = values.every(Number.isFinite);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid) return;
    setBusy(true);
    const [x, y, z] = values;
    const outcome = await onMove(x, y, z);
    setBusy(false);
    setError(outcome.ok ? null : outcome.error);
  }

  return (
    <section className="panel jog" aria-labelledby="jog-title">
      <h2 id="jog-title">Move robot</h2>
      <form onSubmit={submit}>
        <fieldset>
          <legend>Target, robot frame (mm)</legend>
          {(["x", "y", "z"] as const).map((axis) => (
            <label key={axis} className="field">
              <span>{axis.toUpperCase()}</span>
              <input
                type="number"
                inputMode="decimal"
                value={target[axis]}
                disabled={!enabled || busy}
                onChange={(event) => {
                  setTarget({ ...target, [axis]: event.target.value });
                  setError(null);
                }}
              />
            </label>
          ))}
        </fieldset>
        {error && <p className="form-message error">{error}</p>}
        <div className="button-row">
          <button type="submit" disabled={!enabled || busy || !valid}>
            {busy ? "Moving…" : "Move"}
          </button>
        </div>
      </form>
    </section>
  );
}
