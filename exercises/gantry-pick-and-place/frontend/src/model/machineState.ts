/**
 * How the UI interprets the state machine's state names.
 *
 * The rules for which commands are allowed mirror backend/app/machine.py, so
 * buttons are only enabled when the backend would accept them. The backend
 * still enforces everything; this only avoids offering impossible actions.
 */

const PICK_PLACE_STEPS: { name: string; label: string }[] = [
  { name: "moveToCube", label: "Moving to cube" },
  { name: "lowerToCube", label: "Lowering to cube" },
  { name: "grip", label: "Gripping cube" },
  { name: "liftCube", label: "Lifting cube" },
  { name: "moveToDest", label: "Moving to destination" },
  { name: "lowerToDest", label: "Lowering to destination" },
  { name: "release", label: "Releasing cube" },
  { name: "liftClear", label: "Lifting clear" },
];

export type StateKind = "ready" | "busy" | "fault" | "unknown";

export interface StateInfo {
  kind: StateKind;
  label: string;
  /** Position in the pick-and-place sequence, when running it. */
  step?: { index: number; total: number };
}

export function describeState(state: string | undefined): StateInfo {
  if (state === undefined) return { kind: "unknown", label: "Unknown" };
  if (state === "ready") return { kind: "ready", label: "Ready" };
  if (state === "fault") return { kind: "fault", label: "Fault" };
  if (state === "Homing_moving") return { kind: "busy", label: "Homing" };
  if (state === "Manual_moving") return { kind: "busy", label: "Moving to position" };

  const [group, member] = state.split("_");
  if (group === "PickPlace") {
    const index = PICK_PLACE_STEPS.findIndex((step) => step.name === member);
    if (index >= 0) {
      return {
        kind: "busy",
        label: PICK_PLACE_STEPS[index].label,
        step: { index: index + 1, total: PICK_PLACE_STEPS.length },
      };
    }
  }
  return { kind: "busy", label: state };
}

export interface Permissions {
  home: boolean;
  start: boolean;
  stop: boolean;
  reset: boolean;
  jog: boolean;
  editConfig: boolean;
}

export function permissions(state: string | undefined, connected: boolean): Permissions {
  const kind = connected ? describeState(state).kind : "unknown";
  const ready = kind === "ready";
  return {
    home: ready,
    start: ready,
    jog: ready,
    editConfig: ready,
    // Stop must always be available while the robot could be doing something.
    stop: kind === "ready" || kind === "busy",
    reset: kind === "fault",
  };
}
