"""Async wrapper around the provided `robot_sim.Robot`.

The simulator is left untouched. This driver handles its quirks:
  - `move_to` is non-blocking and must be polled until the target is reached;
  - errors come back as a string in the return tuple rather than an exception;
  - speed 0 passes validation but divides by zero;
  - on completion it stores the caller's list as its position (aliasing);
  - an interrupted motion leaves a stale `axis_speed` that skews the next one.
"""

from __future__ import annotations

import asyncio
from typing import Protocol, Sequence

from robot_sim import GripperState, Robot


POLL_INTERVAL_S = 0.02
MAX_SPEED = 100


class MotionError(Exception):
    """Raised when the simulator rejects or fails a motion."""


class GantryDriver(Protocol):
    """What the state machine needs from a robot driver.

    `RobotDriver` (the simulator) satisfies it; so could a real-hardware driver
    or a test fake, without inheriting from anything.
    """

    @property
    def position(self) -> list[float]: ...

    @property
    def limits(self) -> list[float]: ...

    @property
    def gripper_closed(self) -> bool: ...

    @property
    def is_moving(self) -> bool: ...

    async def move(self, target: Sequence[float], speed: int) -> list[float]:
        """Move to `target` (mm) at `speed` (mm/s); raise MotionError on failure."""
        ...

    def open_gripper(self) -> None: ...

    def close_gripper(self) -> None: ...


class RobotDriver:
    """`GantryDriver` implementation backed by the provided simulator."""

    def __init__(self, initial_position: Sequence[float] = (0.0, 0.0, 0.0)) -> None:
        """`initial_position` lets the app restore where the robot was before a restart."""
        # Always pass fresh lists: Robot's defaults are shared mutable lists.
        # Homing is done by the state machine (to the configured home), so the
        # simulator's own home position is left at its default.
        self._robot = Robot(initial_position=self._as_target(initial_position), home_position=[0.0, 0.0, 0.0])
        start = self._robot.current_position
        if any(abs(v) > limit for v, limit in zip(start, self._robot.robot_limits)):
            raise MotionError(f"Initial position {start} is outside the robot limits")
        self._moving = False

    @property
    def position(self) -> list[float]:
        return list(self._robot.current_position)

    @property
    def limits(self) -> list[float]:
        """Maximum absolute position per axis (mm)."""
        return list(self._robot.robot_limits)

    @property
    def gripper_closed(self) -> bool:
        return self._robot.gripper_state == GripperState.CLOSED

    @property
    def is_moving(self) -> bool:
        return self._moving

    def open_gripper(self) -> None:
        self._robot.open_gripper()

    def close_gripper(self) -> None:
        self._robot.closed_gripper()

    async def move(self, target: Sequence[float], speed: int) -> list[float]:
        """Move to `target` (mm) at `speed` (mm/s), polling until it is reached."""
        if not (0 < speed <= MAX_SPEED):
            raise MotionError(f"Speed must be in (0, {MAX_SPEED}] mm/s, got {speed}")
        goal = self._as_target(target)

        # Start from a clean plan in case a previous motion was interrupted.
        self._robot.axis_speed = [0, 0, 0]
        self._moving = True
        try:
            while True:
                position, _, error = self._robot.move_to(list(goal), speed)
                if error:
                    raise MotionError(error)
                if position == goal:
                    return list(position)
                await asyncio.sleep(POLL_INTERVAL_S)
        finally:
            # Also runs on cancellation, so a stopped motion is not resumed later.
            self._robot.axis_speed = [0, 0, 0]
            self._moving = False

    @staticmethod
    def _as_target(value: Sequence[float]) -> list[float]:
        if len(value) != 3:
            raise MotionError(f"Position must have 3 axes, got {len(value)}")
        return [float(v) for v in value]
