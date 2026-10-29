"""Test doubles implementing the `GantryDriver` protocol.

They don't use the simulator: `test_robot_driver.py` covers the real driver.
"""

import asyncio
from typing import Sequence

from app.robot_driver import MAX_SPEED, MotionError


class FastDriver:
    """Teleports to each target so sequences run in milliseconds.

    Checks speed and axis limits like the real driver, and records every
    target it was sent.
    """

    def __init__(
        self,
        position: Sequence[float] = (0.0, 0.0, 0.0),
        limits: Sequence[float] = (1000.0, 1000.0, 1000.0),
    ) -> None:
        self._position = [float(v) for v in position]
        self.limits = [float(v) for v in limits]
        self._gripper_closed = False
        self._moving = False
        self.targets: list[list[float]] = []

    @property
    def position(self) -> list[float]:
        return list(self._position)

    @property
    def gripper_closed(self) -> bool:
        return self._gripper_closed

    @property
    def is_moving(self) -> bool:
        return self._moving

    def open_gripper(self) -> None:
        self._gripper_closed = False

    def close_gripper(self) -> None:
        self._gripper_closed = True

    async def move(self, target: Sequence[float], speed: int) -> list[float]:
        goal = self._check(target, speed)
        self.targets.append(goal)
        self._position = list(goal)
        await asyncio.sleep(0)
        return list(goal)

    def _check(self, target: Sequence[float], speed: int) -> list[float]:
        if not 0 < speed <= MAX_SPEED:
            raise MotionError(f"Speed must be in (0, {MAX_SPEED}] mm/s, got {speed}")
        goal = [float(v) for v in target]
        for axis, value in enumerate(goal):
            if abs(value) > self.limits[axis]:
                raise MotionError(
                    f"Requested position of : {value} for axis {axis} "
                    f"is outside of the limits {self.limits}"
                )
        return goal


class StuckDriver(FastDriver):
    """Never finishes a move, to exercise timeouts and busy states."""

    async def move(self, target: Sequence[float], speed: int) -> list[float]:
        self._check(target, speed)
        self._moving = True
        try:
            await asyncio.sleep(3600)
        finally:
            self._moving = False
        return self.position
