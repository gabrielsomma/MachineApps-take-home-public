"""Cell layout and coordinate transforms.

Robot frame: origin at the centre of the 2 m x 2 m footprint, X to the right,
Y up (top view), Z up, all in millimetres. This matches the simulator's
+/-1000 mm axis limits.

Each table has its own reference frame (see Figure 1). Cube and destination
positions are entered in table coordinates and converted here. The table
placements are round values chosen to resemble the figure, not measurements.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


TABLE_SIZE_MM = 500.0


class TableId(str, Enum):
    A = "A"
    B = "B"


@dataclass(frozen=True)
class TableFrame:
    origin: tuple[float, float]
    """Position of the table's reference frame in the robot frame (mm)."""
    rotation_deg: float
    """Rotation of the table's X axis relative to the robot's X axis (CCW positive)."""
    size: float = TABLE_SIZE_MM


TABLES: dict[TableId, TableFrame] = {
    # 100 mm in from the left and top edges of the footprint.
    TableId.A: TableFrame(origin=(-900.0, 400.0), rotation_deg=0.0),
    # Bottom-right, rotated so its X axis points down-right and Y axis up-right.
    TableId.B: TableFrame(origin=(250.0, -550.0), rotation_deg=-45.0),
}


def table_point_to_robot_frame(table: TableId, x: float, y: float) -> tuple[float, float]:
    """Convert a point in a table's frame to the robot frame."""
    frame = TABLES[table]
    theta = math.radians(frame.rotation_deg)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    rx = frame.origin[0] + x * cos_t - y * sin_t
    ry = frame.origin[1] + x * sin_t + y * cos_t
    # Round away floating-point noise from the rotation (sub-micron).
    return round(rx, 3), round(ry, 3)


def is_on_table(table: TableId, x: float, y: float) -> bool:
    """True if (x, y), in the table's frame, lies on the table (edges included)."""
    size = TABLES[table].size
    return 0.0 <= x <= size and 0.0 <= y <= size
