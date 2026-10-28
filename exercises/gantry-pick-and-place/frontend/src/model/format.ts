import type { Point3 } from "../gen/app_pb";
import type { Vec3 } from "./geometry";

/** Nested proto messages are optional; treat a missing point as the origin. */
export function toVec3(point: Point3 | undefined): Vec3 {
  return point ? [point.x, point.y, point.z] : [0, 0, 0];
}

export function mm(value: number): string {
  return value.toFixed(1);
}
