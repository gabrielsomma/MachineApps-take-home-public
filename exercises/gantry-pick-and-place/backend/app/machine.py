"""Gantry control logic built on vention-state-machine.

State names are `<Group>_<member>`; the library joins them with "_", so member
names must not contain underscores themselves (hence camelCase).

Each motion state starts a background task on entry. The task drives the robot
through `RobotDriver.move()` (which polls `robot_sim.move_to` until the target is
reached) and fires the next trigger when done. A `MotionError` or a timeout
records the reason and sends the machine to `fault`.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from typing import Any, Awaitable, Callable, Optional, Sequence

from transitions.core import MachineError

from state_machine.core import BaseStates, BaseTriggers, StateMachine
from state_machine.decorators import guard, on_enter_state, on_exit_state
from state_machine.defs import State, StateGroup, Trigger

from app.config import CellConfig, validate_config
from app.geometry import TableId, table_point_to_robot_frame
from app.robot_driver import GantryDriver, MotionError


class Homing(StateGroup):
    moving = State()


class Manual(StateGroup):
    moving = State()


class PickPlace(StateGroup):
    moveToCube = State()
    lowerToCube = State()
    grip = State()
    liftCube = State()
    moveToDest = State()
    lowerToDest = State()
    release = State()
    liftClear = State()


class States:
    homing = Homing()
    manual = Manual()
    pick_place = PickPlace()


class Triggers:
    home = Trigger("home")
    jog = Trigger("jog")
    start_sequence = Trigger("start_sequence")
    next = Trigger("next")
    done = Trigger("done")


READY = BaseStates.READY.value
FAULT = BaseStates.FAULT.value

PICK_PLACE_STEPS: list[State] = [
    PickPlace.moveToCube,
    PickPlace.lowerToCube,
    PickPlace.grip,
    PickPlace.liftCube,
    PickPlace.moveToDest,
    PickPlace.lowerToDest,
    PickPlace.release,
    PickPlace.liftClear,
]

TRANSITIONS = [
    Triggers.home.transition(READY, Homing.moving),
    Triggers.done.transition(Homing.moving, READY),
    Triggers.jog.transition(READY, Manual.moving),
    Triggers.done.transition(Manual.moving, READY),
    Triggers.start_sequence.transition(READY, PickPlace.moveToCube),
    *[
        Triggers.next.transition(step, following)
        for step, following in zip(PICK_PLACE_STEPS, PICK_PLACE_STEPS[1:])
    ],
    Triggers.done.transition(PickPlace.liftClear, READY),
]


@dataclass
class RobotSnapshot:
    """The robot's physical state, saved so it survives a backend restart."""

    position: list[float]
    gripper_closed: bool
    cube_position: list[float]
    cube_held: bool


@dataclass
class MachineStatus:
    state: str
    position: list[float]
    gripper_closed: bool
    moving: bool
    cube_position: list[float]
    destination_position: list[float]
    last_error: Optional[str]


class GantryMachine(StateMachine):
    GRIPPER_DELAY_S = 0.3
    """Simulated time for the gripper to open or close."""
    TIMEOUT_FACTOR = 1.5
    TIMEOUT_MARGIN_S = 2.0
    """A move faults if it takes longer than expected_time * factor + margin."""

    def __init__(self, driver: GantryDriver, config: Optional[CellConfig] = None) -> None:
        # The driver is injected: main.py picks the simulator, tests pass a fake,
        # and a real-hardware driver could be dropped in without touching this file.
        self.driver = driver
        self.config = config or CellConfig()
        self.last_error: Optional[str] = None
        self._jog_target: list[float] = self.driver.position
        self._holding_cube = False
        self._cube_rest: list[float] = []
        self._place_cube_at_start()
        self.driver.home_position = self.config.home
        # We never call start(): the machine begins in `ready`, and recovery
        # into a half-finished motion after a restart would be unsafe.
        super().__init__(States, transitions=TRANSITIONS, enable_last_state_recovery=False)

    # ---------------------------------------------------------------- commands
    # Each returns None on success or a message explaining why it was refused.

    def request_home(self) -> Optional[str]:
        return self._fire(Triggers.home)

    def request_jog(self, target: Sequence[float]) -> Optional[str]:
        if len(target) != 3:
            return f"Position must have 3 axes, got {len(target)}"
        if any(abs(v) > limit for v, limit in zip(target, self.driver.limits)):
            return f"Position {list(target)} is outside the robot limits {self.driver.limits}"
        if self.state != READY:
            return self._not_ready("move the robot")
        self._jog_target = [float(v) for v in target]
        return self._fire(Triggers.jog)

    def request_start(self) -> Optional[str]:
        error = validate_config(self.config, self.driver.limits)
        if error:
            return error
        return self._fire(Triggers.start_sequence)

    def request_stop(self) -> Optional[str]:
        """Operator stop: halt any motion immediately by faulting."""
        if self.state == FAULT:
            return None
        self._fault("Stopped by operator")
        return None

    def request_reset(self) -> Optional[str]:
        if self.state != FAULT:
            return "Reset is only needed after a fault"
        return self._fire(BaseTriggers.RESET.value)

    def update_config(self, config: CellConfig) -> Optional[str]:
        if self.state != READY:
            return self._not_ready("change the configuration")
        error = validate_config(config, self.driver.limits)
        if error:
            return error
        self.config = replace(config)
        self.driver.home_position = config.home
        self._place_cube_at_start()
        return None

    def status(self) -> MachineStatus:
        return MachineStatus(
            state=self.state,
            position=self.driver.position,
            gripper_closed=self.driver.gripper_closed,
            moving=self.driver.is_moving,
            cube_position=self.cube_position,
            destination_position=[*self._destination_xy(), self.config.pick_z],
            last_error=self.last_error,
        )

    def robot_snapshot(self) -> RobotSnapshot:
        return RobotSnapshot(
            position=self.driver.position,
            gripper_closed=self.driver.gripper_closed,
            cube_position=self.cube_position,
            cube_held=self._holding_cube,
        )

    def restore_robot_state(self, snapshot: RobotSnapshot) -> None:
        """Restore the gripper and simulated cube after a restart.

        The robot's position is restored by the driver (it is built at the saved
        position). The machine itself always restarts in `ready`: resuming a
        half-finished motion would be unsafe.
        """
        if snapshot.gripper_closed:
            self.driver.close_gripper()
        else:
            self.driver.open_gripper()
        self._holding_cube = snapshot.cube_held
        self._cube_rest = list(snapshot.cube_position)

    @property
    def cube_position(self) -> list[float]:
        """Where the simulated cube is: in the gripper while held, otherwise resting."""
        return self.driver.position if self._holding_cube else list(self._cube_rest)

    # ------------------------------------------------------------------ guards

    @guard(Triggers.start_sequence)
    def _config_is_valid(self) -> bool:
        return validate_config(self.config, self.driver.limits) is None

    @guard(Triggers.home, Triggers.jog, Triggers.start_sequence)
    def _robot_is_idle(self) -> bool:
        return not self.driver.is_moving

    # ------------------------------------------------------------ state hooks

    @on_enter_state(Homing.moving)
    def _enter_homing(self, _: Any) -> None:
        self._run_step(lambda: self._travel_to(self.config.home), Triggers.done)

    @on_enter_state(Manual.moving)
    def _enter_manual(self, _: Any) -> None:
        self._run_step(lambda: self._move(self._jog_target), Triggers.done)

    @on_enter_state(PickPlace.moveToCube)
    def _enter_move_to_cube(self, _: Any) -> None:
        # Each run assumes the cube has been placed back at its start position.
        self.driver.open_gripper()
        self._place_cube_at_start()
        self._run_step(lambda: self._travel_to(self._above(self._cube_xy())))

    @on_enter_state(PickPlace.lowerToCube)
    def _enter_lower_to_cube(self, _: Any) -> None:
        self._run_step(lambda: self._move([*self._cube_xy(), self.config.pick_z]))

    @on_enter_state(PickPlace.grip)
    def _enter_grip(self, _: Any) -> None:
        async def grip() -> None:
            self.driver.close_gripper()
            self._holding_cube = True
            await asyncio.sleep(self.GRIPPER_DELAY_S)

        self._run_step(grip)

    @on_enter_state(PickPlace.liftCube)
    def _enter_lift_cube(self, _: Any) -> None:
        self._run_step(lambda: self._move(self._above(self._cube_xy())))

    @on_enter_state(PickPlace.moveToDest)
    def _enter_move_to_dest(self, _: Any) -> None:
        self._run_step(lambda: self._move(self._above(self._destination_xy())))

    @on_enter_state(PickPlace.lowerToDest)
    def _enter_lower_to_dest(self, _: Any) -> None:
        self._run_step(lambda: self._move([*self._destination_xy(), self.config.pick_z]))

    @on_enter_state(PickPlace.release)
    def _enter_release(self, _: Any) -> None:
        async def release() -> None:
            self.driver.open_gripper()
            self._cube_rest = self.driver.position
            self._holding_cube = False
            await asyncio.sleep(self.GRIPPER_DELAY_S)

        self._run_step(release)

    @on_enter_state(PickPlace.liftClear)
    def _enter_lift_clear(self, _: Any) -> None:
        self._run_step(lambda: self._move(self._above(self._destination_xy())), Triggers.done)

    @on_enter_state(FAULT)
    def _enter_fault(self, _: Any) -> None:
        # The library's own `to_fault` cleanup is a coroutine that the
        # synchronous transition never awaits, so stop the work here.
        self._clear_all_timeouts()
        current = asyncio.current_task() if _loop_running() else None
        for task in list(self._tasks):
            if task is not current:
                task.cancel()

    @on_exit_state(FAULT)
    def _exit_fault(self, _: Any) -> None:
        self.last_error = None

    # ----------------------------------------------------------------- helpers

    def _run_step(self, work: Callable[[], Awaitable[Any]], on_success: Trigger = Triggers.next) -> None:
        """Run `work` in the background, then fire `on_success` (or fault on error)."""
        state = self.state

        async def runner() -> None:
            try:
                await work()
            except MotionError as exc:
                self._fault(str(exc))
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - any failure must stop the machine
                self._fault(f"Unexpected error in {state}: {exc}")
                return
            if self.state == state:
                self.trigger(on_success.name)

        self.spawn(runner())

    async def _move(self, target: Sequence[float]) -> None:
        self.set_timeout(self.state, self._timeout_for(target), self._on_timeout)
        await self.driver.move(target, self.config.speed)

    async def _travel_to(self, target: Sequence[float]) -> None:
        """Lift to travel height first if below it, so X/Y moves never drag across a table."""
        x, y, z = self.driver.position
        if z < self.config.safe_z:
            await self._move([x, y, self.config.safe_z])
        await self._move(target)

    def _timeout_for(self, target: Sequence[float]) -> float:
        distance = max(abs(t - p) for t, p in zip(target, self.driver.position))
        return distance / self.config.speed * self.TIMEOUT_FACTOR + self.TIMEOUT_MARGIN_S

    def _on_timeout(self) -> str:
        self.last_error = f"Motion timed out in {self.state}"
        return BaseTriggers.TO_FAULT.value

    def _fault(self, message: str) -> None:
        self.last_error = message
        self.trigger(BaseTriggers.TO_FAULT.value)

    def _fire(self, trigger: Any) -> Optional[str]:
        name = getattr(trigger, "name", trigger)
        try:
            allowed = self.trigger(name)
        except MachineError:
            return self._not_ready(name.replace("_", " "))
        return None if allowed else f"Cannot {name.replace('_', ' ')} right now"

    def _not_ready(self, action: str) -> str:
        return f"Cannot {action} while the machine is in state '{self.state}'"

    def _place_cube_at_start(self) -> None:
        self._cube_rest = [*self._cube_xy(), self.config.pick_z]
        self._holding_cube = False

    def _cube_xy(self) -> tuple[float, float]:
        return table_point_to_robot_frame(TableId.A, *self.config.cube)

    def _destination_xy(self) -> tuple[float, float]:
        return table_point_to_robot_frame(TableId.B, *self.config.destination)

    def _above(self, xy: tuple[float, float]) -> list[float]:
        return [*xy, self.config.safe_z]


def _loop_running() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True
