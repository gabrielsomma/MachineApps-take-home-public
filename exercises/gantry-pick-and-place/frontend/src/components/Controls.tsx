import type { Permissions } from "../model/machineState";

export type CommandName = "home" | "start" | "stop" | "reset";

export interface ControlsProps {
  allowed: Permissions;
  /** The command waiting for the backend's answer, if any. */
  pending: CommandName | null;
  onCommand: (command: CommandName) => void;
}

const BUTTONS: { command: CommandName; label: string; className: string }[] = [
  { command: "home", label: "Home", className: "" },
  { command: "start", label: "Start pick & place", className: "primary" },
  { command: "stop", label: "Stop", className: "danger" },
  { command: "reset", label: "Reset fault", className: "" },
];

export function Controls({ allowed, pending, onCommand }: ControlsProps) {
  return (
    <section className="panel controls" aria-labelledby="controls-title">
      <h2 id="controls-title">Controls</h2>
      <div className="button-row">
        {BUTTONS.map(({ command, label, className }) => (
          <button
            key={command}
            type="button"
            className={className}
            disabled={!allowed[command] || pending !== null}
            onClick={() => onCommand(command)}
          >
            {pending === command ? `${label}…` : label}
          </button>
        ))}
      </div>
    </section>
  );
}
