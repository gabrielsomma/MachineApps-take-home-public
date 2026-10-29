"""Cell configuration: where the cube starts, where it goes, and motion settings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from app.geometry import TableId, is_on_table
from app.robot_driver import MAX_SPEED


@dataclass
class CellConfig:
    cube: tuple[float, float] = (250.0, 250.0)
    """Cube start position in Table A's frame (mm)."""
    destination: tuple[float, float] = (250.0, 250.0)
    """Cube destination in Table B's frame (mm)."""
    home: tuple[float, float, float] = (0.0, 0.0, 0.0)
    """Robot home position in the robot frame (mm)."""
    safe_z: float = 0.0
    """Travel height: the robot lifts to this Z before moving in X/Y."""
    pick_z: float = -300.0
    """Gripper height when picking up or placing the cube."""
    speed: int = 100
    """Motion speed in mm/s, 1-100."""


def validate_config(config: CellConfig, limits: Sequence[float]) -> Optional[str]:
    """Return a message describing the first problem with `config`, or None if it is valid."""
    if not is_on_table(TableId.A, *config.cube):
        return f"Cube position {_fmt(config.cube)} is not on Table A (x and y must be 0-500 mm)"
    if not is_on_table(TableId.B, *config.destination):
        return f"Destination {_fmt(config.destination)} is not on Table B (x and y must be 0-500 mm)"
    if not 1 <= config.speed <= MAX_SPEED:
        return f"Speed must be between 1 and {MAX_SPEED} mm/s, got {config.speed}"
    if config.pick_z >= config.safe_z:
        return f"Pick height ({config.pick_z:g}) must be below the travel height ({config.safe_z:g})"
    z_limit = limits[2]
    for name, z in (("Travel height", config.safe_z), ("Pick height", config.pick_z)):
        if abs(z) > z_limit:
            return f"{name} {z:g} is outside the robot's Z range (+/-{z_limit:g} mm)"
    if any(abs(v) > limit for v, limit in zip(config.home, limits)):
        return f"Home position {_fmt(config.home)} is outside the robot limits"
    return None


def _fmt(values: Sequence[float]) -> str:
    return "(" + ", ".join(f"{v:g}" for v in values) + ")"
