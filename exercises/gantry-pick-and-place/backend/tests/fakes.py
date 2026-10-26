"""Test doubles for RobotDriver."""

import asyncio

from app.robot_driver import MotionError, RobotDriver


class FastDriver(RobotDriver):
    """Teleports to each target so sequences run in milliseconds.

    Keeps the real simulator's validation by issuing one `move_to` call first,
    and records every target it was sent.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.targets: list[list[float]] = []

    async def move(self, target, speed):
        goal = self._as_target(target)
        _, _, error = self._robot.move_to(list(goal), speed)
        if error:
            raise MotionError(error)
        self.targets.append(goal)
        self._robot.axis_speed = [0, 0, 0]
        self._robot.current_position = list(goal)
        await asyncio.sleep(0)
        return list(goal)


class StuckDriver(FastDriver):
    """Never finishes a move, to exercise timeouts and busy states."""

    async def move(self, target, speed):
        self._moving = True
        try:
            await asyncio.sleep(3600)
        finally:
            self._moving = False
