import { FOOTPRINT_HALF_MM, TABLES, tableCorners, tablePointToRobotFrame } from "../model/geometry";
import type { TableId, Vec2, Vec3 } from "../model/geometry";

export interface TopViewProps {
  robot: Vec3 | null;
  gripperClosed: boolean;
  cube: Vec3 | null;
  destination: Vec3 | null;
  /** Configured cube start, robot frame. */
  cubeStart: Vec2 | null;
  home: Vec2 | null;
  /** Unsaved positions from the config form, drawn as dashed ghosts. */
  preview?: { cube?: Vec2; destination?: Vec2 };
}

const MARGIN = 80;
const VIEW = FOOTPRINT_HALF_MM + MARGIN;
const CUBE_MM = 50;
const AXIS_MM = 120;

/** SVG's Y axis points down; the robot frame's points up. */
function svg([x, y]: Vec2): Vec2 {
  return [x, -y];
}

function points(corners: Vec2[]): string {
  return corners.map((corner) => svg(corner).join(",")).join(" ");
}

/** Top-down drawing of the cell in robot millimetres (1 SVG unit = 1 mm). */
export function TopView({ robot, gripperClosed, cube, destination, cubeStart, home, preview }: TopViewProps) {
  const cubeHeld =
    robot !== null &&
    cube !== null &&
    gripperClosed &&
    Math.hypot(cube[0] - robot[0], cube[1] - robot[1]) < 1;

  return (
    <svg
      className="top-view"
      viewBox={`${-VIEW} ${-VIEW} ${2 * VIEW} ${2 * VIEW}`}
      role="img"
      aria-label="Top view of the cell"
    >
      <rect
        className="footprint"
        x={-FOOTPRINT_HALF_MM}
        y={-FOOTPRINT_HALF_MM}
        width={2 * FOOTPRINT_HALF_MM}
        height={2 * FOOTPRINT_HALF_MM}
      />
      <Grid />

      {(["A", "B"] as TableId[]).map((table) => (
        <Table key={table} table={table} />
      ))}

      {cubeStart && destination && (
        <line
          className="route"
          x1={svg(cubeStart)[0]}
          y1={svg(cubeStart)[1]}
          x2={svg([destination[0], destination[1]])[0]}
          y2={svg([destination[0], destination[1]])[1]}
        />
      )}

      {destination && <Square className="destination" at={[destination[0], destination[1]]} size={CUBE_MM + 30} />}
      {preview?.cube && <Square className="ghost" at={preview.cube} size={CUBE_MM} />}
      {preview?.destination && <Square className="ghost" at={preview.destination} size={CUBE_MM + 30} />}
      {home && <HomeMarker at={home} />}

      {cube && !cubeHeld && <Square className="cube" at={[cube[0], cube[1]]} size={CUBE_MM} />}

      {robot && <Gantry robot={robot} gripperClosed={gripperClosed} carrying={cubeHeld} />}

      <ScaleBar />
    </svg>
  );
}

function Grid() {
  const lines = [];
  for (let v = -750; v <= 750; v += 250) {
    lines.push(
      <line key={`v${v}`} x1={v} y1={-FOOTPRINT_HALF_MM} x2={v} y2={FOOTPRINT_HALF_MM} />,
      <line key={`h${v}`} x1={-FOOTPRINT_HALF_MM} y1={v} x2={FOOTPRINT_HALF_MM} y2={v} />,
    );
  }
  return <g className="grid">{lines}</g>;
}

function Table({ table }: { table: TableId }) {
  const [cx, cy] = svg(tablePointToRobotFrame(table, 250, 250));
  const origin = svg(TABLES[table].origin);
  const xAxis = svg(tablePointToRobotFrame(table, AXIS_MM, 0));
  const yAxis = svg(tablePointToRobotFrame(table, 0, AXIS_MM));
  return (
    <g className="table">
      <polygon points={points(tableCorners(table))} />
      <text x={cx} y={cy} className="table-label">
        Table {table}
      </text>
      <line className="axis" x1={origin[0]} y1={origin[1]} x2={xAxis[0]} y2={xAxis[1]} />
      <line className="axis" x1={origin[0]} y1={origin[1]} x2={yAxis[0]} y2={yAxis[1]} />
      <text x={xAxis[0]} y={xAxis[1]} className="axis-label">
        x
      </text>
      <text x={yAxis[0]} y={yAxis[1]} className="axis-label">
        y
      </text>
    </g>
  );
}

function Square({ at, size, className }: { at: Vec2; size: number; className: string }) {
  const [x, y] = svg(at);
  return <rect className={className} x={x - size / 2} y={y - size / 2} width={size} height={size} />;
}

function HomeMarker({ at }: { at: Vec2 }) {
  const [x, y] = svg(at);
  return (
    <g className="home">
      <line x1={x - 30} y1={y} x2={x + 30} y2={y} />
      <line x1={x} y1={y - 30} x2={x} y2={y + 30} />
    </g>
  );
}

function Gantry({ robot, gripperClosed, carrying }: { robot: Vec3; gripperClosed: boolean; carrying: boolean }) {
  const [x, y] = svg([robot[0], robot[1]]);
  return (
    <g className="gantry">
      {/* The bridge spans Y at the robot's X; the carriage runs along it. */}
      <line className="bridge" x1={x} y1={-FOOTPRINT_HALF_MM} x2={x} y2={FOOTPRINT_HALF_MM} />
      {/* A ring around the tool point: thick when the gripper is closed. */}
      <circle className={gripperClosed ? "head closed" : "head"} cx={x} cy={y} r={55} />
      {carrying && (
        <rect className="cube" x={x - CUBE_MM / 2} y={y - CUBE_MM / 2} width={CUBE_MM} height={CUBE_MM} />
      )}
      <circle className="tool-point" cx={x} cy={y} r={8} />
    </g>
  );
}

function ScaleBar() {
  const y = FOOTPRINT_HALF_MM + 50;
  const x = -FOOTPRINT_HALF_MM;
  return (
    <g className="scale">
      <line x1={x} y1={y} x2={x + 500} y2={y} />
      <text x={x + 520} y={y}>
        500 mm
      </text>
    </g>
  );
}
