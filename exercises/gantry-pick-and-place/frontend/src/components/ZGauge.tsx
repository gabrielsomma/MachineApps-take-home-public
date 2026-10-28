import { mm } from "../model/format";

export interface ZGaugeProps {
  z: number | null;
  safeZ: number;
  pickZ: number;
}

const HEIGHT = 300;
const PAD = 20;

/** Vertical gauge of the gripper height, with the travel and pick heights marked. */
export function ZGauge({ z, safeZ, pickZ }: ZGaugeProps) {
  const top = Math.max(safeZ, z ?? safeZ) + 50;
  const bottom = Math.min(pickZ, z ?? pickZ) - 50;
  const toY = (value: number) => PAD + ((top - value) / (top - bottom)) * (HEIGHT - 2 * PAD);

  return (
    <svg className="z-gauge" viewBox={`0 0 120 ${HEIGHT}`} role="img" aria-label={`Gripper height ${z === null ? "unknown" : mm(z)} mm`}>
      <line className="track" x1={30} y1={PAD} x2={30} y2={HEIGHT - PAD} />
      <Mark y={toY(safeZ)} label={`travel ${mm(safeZ)}`} />
      <Mark y={toY(pickZ)} label={`pick ${mm(pickZ)}`} />
      {z !== null && (
        <g className="indicator">
          <rect x={18} y={toY(z) - 6} width={24} height={12} rx={3} />
        </g>
      )}
      <text className="caption" x={30} y={12}>
        Z
      </text>
    </svg>
  );
}

function Mark({ y, label }: { y: number; label: string }) {
  return (
    <g className="mark">
      <line x1={22} y1={y} x2={38} y2={y} />
      <text x={46} y={y}>
        {label}
      </text>
    </g>
  );
}
