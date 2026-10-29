import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { MessageInitShape } from "@bufbuild/protobuf";

import type { Config, ConfigSchema } from "../gen/app_pb";
import type { CommandOutcome } from "../api/client";
import { isOnTable, tablePointToRobotFrame } from "../model/geometry";
import type { Vec2 } from "../model/geometry";

export type ConfigInit = MessageInitShape<typeof ConfigSchema>;
export interface ConfigPreview {
  cube?: Vec2;
  destination?: Vec2;
}

const FIELDS = [
  "cubeX", "cubeY", "destX", "destY", "homeX", "homeY", "homeZ", "safeZ", "pickZ", "speed",
] as const;
type Field = (typeof FIELDS)[number];
type Draft = Record<Field, string>;

function fromConfig(config: Config): Draft {
  return {
    cubeX: String(config.cube?.x ?? 0),
    cubeY: String(config.cube?.y ?? 0),
    destX: String(config.destination?.x ?? 0),
    destY: String(config.destination?.y ?? 0),
    homeX: String(config.home?.x ?? 0),
    homeY: String(config.home?.y ?? 0),
    homeZ: String(config.home?.z ?? 0),
    safeZ: String(config.safeZ),
    pickZ: String(config.pickZ),
    speed: String(config.speed),
  };
}

function sameDraft(a: Draft, b: Draft): boolean {
  return FIELDS.every((field) => a[field] === b[field]);
}

/** Parse the form; returns the numbers, or a message for the first bad field. */
function parse(draft: Draft): { values: Record<Field, number> } | { error: string } {
  const values = {} as Record<Field, number>;
  for (const field of FIELDS) {
    const text = draft[field].trim();
    const value = Number(text);
    if (text === "" || !Number.isFinite(value)) return { error: `${LABELS[field]} must be a number` };
    values[field] = value;
  }
  if (!Number.isInteger(values.speed)) return { error: "Speed must be a whole number of mm/s" };
  return { values };
}

const LABELS: Record<Field, string> = {
  cubeX: "Cube X", cubeY: "Cube Y", destX: "Destination X", destY: "Destination Y",
  homeX: "Home X", homeY: "Home Y", homeZ: "Home Z",
  safeZ: "Travel height", pickZ: "Pick height", speed: "Speed",
};

export interface ConfigFormProps {
  saved: Config | null;
  enabled: boolean;
  onSave: (config: ConfigInit) => Promise<CommandOutcome>;
  onPreview: (preview: ConfigPreview) => void;
}

/**
 * Edit the cell configuration. Cube and destination are entered in their
 * table's own frame (0-500 mm from the red reference corner), as in Figure 1.
 * The backend validates on save; its message is shown inline.
 */
export function ConfigForm({ saved, enabled, onSave, onPreview }: ConfigFormProps) {
  const [draft, setDraft] = useState<Draft | null>(saved ? fromConfig(saved) : null);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const baseline = saved ? fromConfig(saved) : null;
  // The baseline the current draft was last synced to (only used by the effect below).
  const previousBaseline = useRef<Draft | null>(baseline);
  const replaceOnNextLoad = useRef(false);

  // Follow the backend's config unless the user has unsaved edits
  // (or just saved, in which case take the backend's normalised values).
  useEffect(() => {
    if (!saved) return;
    const incoming = fromConfig(saved);
    const previous = previousBaseline.current;
    const force = replaceOnNextLoad.current;
    previousBaseline.current = incoming;
    replaceOnNextLoad.current = false;
    setDraft((current) =>
      current === null || force || (previous !== null && sameDraft(current, previous)) ? incoming : current,
    );
  }, [saved]);

  const dirty = draft !== null && baseline !== null && !sameDraft(draft, baseline);
  const parsed = draft ? parse(draft) : null;

  useEffect(() => {
    if (!dirty || !parsed || "error" in parsed) {
      onPreview({});
      return;
    }
    const v = parsed.values;
    onPreview({
      cube: tablePointToRobotFrame("A", v.cubeX, v.cubeY),
      destination: tablePointToRobotFrame("B", v.destX, v.destY),
    });
    // `parsed` is derived from `draft`; depending on it directly would re-run every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft, dirty, onPreview]);

  if (!draft || !parsed) {
    return (
      <section className="panel config">
        <h2>Configuration</h2>
        <p className="hint">Loading…</p>
      </section>
    );
  }

  const offTable =
    "values" in parsed
      ? [
          !isOnTable(parsed.values.cubeX, parsed.values.cubeY) && "Cube is off Table A",
          !isOnTable(parsed.values.destX, parsed.values.destY) && "Destination is off Table B",
        ].filter(Boolean)
      : [];

  function update(field: Field, value: string) {
    setDraft((current) => (current ? { ...current, [field]: value } : current));
    setMessage(null);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!parsed || "error" in parsed) return;
    const v = parsed.values;
    setSaving(true);
    replaceOnNextLoad.current = true;
    const outcome = await onSave({
      cube: { x: v.cubeX, y: v.cubeY },
      destination: { x: v.destX, y: v.destY },
      home: { x: v.homeX, y: v.homeY, z: v.homeZ },
      safeZ: v.safeZ,
      pickZ: v.pickZ,
      speed: v.speed,
    });
    if (!outcome.ok) replaceOnNextLoad.current = false;
    setSaving(false);
    setMessage(outcome.ok ? { ok: true, text: "Saved" } : { ok: false, text: outcome.error });
  }

  function revert() {
    if (baseline) setDraft(baseline);
    setMessage(null);
  }

  const field = (name: Field) => (
    <label className="field">
      <span>{LABELS[name].replace(/^(Cube|Destination|Home) /, "")}</span>
      <input
        type="number"
        inputMode="decimal"
        step="1"
        value={draft[name]}
        disabled={!enabled || saving}
        onChange={(event) => update(name, event.target.value)}
      />
    </label>
  );

  return (
    <section className="panel config" aria-labelledby="config-title">
      <h2 id="config-title">Configuration</h2>
      <form onSubmit={submit}>
        <fieldset>
          <legend>Cube start, Table A frame (mm)</legend>
          {field("cubeX")}
          {field("cubeY")}
        </fieldset>
        <fieldset>
          <legend>Destination, Table B frame (mm)</legend>
          {field("destX")}
          {field("destY")}
        </fieldset>
        <fieldset>
          <legend>Home position, robot frame (mm)</legend>
          {field("homeX")}
          {field("homeY")}
          {field("homeZ")}
        </fieldset>
        <fieldset>
          <legend>Motion</legend>
          {field("safeZ")}
          {field("pickZ")}
          {field("speed")}
        </fieldset>

        {"error" in parsed && <p className="form-message error">{parsed.error}</p>}
        {offTable.length > 0 && <p className="form-message warning">{offTable.join(" · ")}</p>}
        {message && <p className={`form-message ${message.ok ? "ok" : "error"}`}>{message.text}</p>}
        {!enabled && <p className="hint">Configuration can only be changed while the machine is ready.</p>}

        <div className="button-row">
          <button type="submit" className="primary" disabled={!enabled || saving || !dirty || "error" in parsed}>
            {saving ? "Saving…" : "Save"}
          </button>
          <button type="button" onClick={revert} disabled={!dirty || saving}>
            Revert
          </button>
        </div>
      </form>
    </section>
  );
}
