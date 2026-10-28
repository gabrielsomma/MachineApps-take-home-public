/**
 * Cell layout, mirroring backend/app/geometry.py (keep the two in sync).
 *
 * Robot frame: origin at the centre of the 2 m x 2 m footprint, X right,
 * Y up (top view), millimetres.
 */

export type TableId = "A" | "B";
export type Vec2 = [number, number];
export type Vec3 = [number, number, number];

export const FOOTPRINT_HALF_MM = 1000;
export const TABLE_SIZE_MM = 500;

interface TableFrame {
  origin: Vec2;
  /** Rotation of the table's X axis from the robot's X axis, CCW positive. */
  rotationDeg: number;
}

export const TABLES: Record<TableId, TableFrame> = {
  A: { origin: [-900, 400], rotationDeg: 0 },
  B: { origin: [250, -550], rotationDeg: -45 },
};

/** Convert a point in a table's frame to the robot frame. */
export function tablePointToRobotFrame(table: TableId, x: number, y: number): Vec2 {
  const { origin, rotationDeg } = TABLES[table];
  const theta = (rotationDeg * Math.PI) / 180;
  const cos = Math.cos(theta);
  const sin = Math.sin(theta);
  return [origin[0] + x * cos - y * sin, origin[1] + x * sin + y * cos];
}

/** The table's four corners in the robot frame, in drawing order. */
export function tableCorners(table: TableId): Vec2[] {
  const s = TABLE_SIZE_MM;
  return [
    [0, 0],
    [s, 0],
    [s, s],
    [0, s],
  ].map(([x, y]) => tablePointToRobotFrame(table, x, y));
}

export function isOnTable(x: number, y: number): boolean {
  return x >= 0 && x <= TABLE_SIZE_MM && y >= 0 && y <= TABLE_SIZE_MM;
}
