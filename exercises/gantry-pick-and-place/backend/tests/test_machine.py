import asyncio

import pytest

from app.config import CellConfig
from app.geometry import TableId, table_point_to_robot_frame
from app.machine import GantryMachine
from tests.fakes import FastDriver, StuckDriver


def make_machine(driver=None, **config):
    machine = GantryMachine(driver=driver or FastDriver(), config=CellConfig(**config))
    machine.GRIPPER_DELAY_S = 0
    return machine


async def wait_for_state(machine, state, timeout=2.0):
    async def poll():
        while machine.state != state:
            await asyncio.sleep(0.005)

    await asyncio.wait_for(poll(), timeout)


def visited(machine):
    return [entry["state"] for entry in machine.history]


def run(coro):
    return asyncio.run(coro)


EXPECTED_SEQUENCE = [
    "PickPlace_moveToCube",
    "PickPlace_lowerToCube",
    "PickPlace_grip",
    "PickPlace_liftCube",
    "PickPlace_moveToDest",
    "PickPlace_lowerToDest",
    "PickPlace_release",
    "PickPlace_liftClear",
    "ready",
]


def test_starts_in_ready():
    machine = make_machine()
    assert machine.state == "ready"
    assert machine.status().last_error is None


def test_full_pick_and_place_sequence():
    machine = make_machine(cube=(100, 400), destination=(250, 250))
    cube_xy = table_point_to_robot_frame(TableId.A, 100, 400)
    dest_xy = table_point_to_robot_frame(TableId.B, 250, 250)

    async def scenario():
        assert machine.request_start() is None
        await wait_for_state(machine, "PickPlace_liftClear")
        await wait_for_state(machine, "ready")

    run(scenario())

    assert visited(machine) == EXPECTED_SEQUENCE
    assert machine.driver.targets == [
        [*cube_xy, 0.0],      # move above cube
        [*cube_xy, -300.0],   # lower
        [*cube_xy, 0.0],      # lift
        [*dest_xy, 0.0],      # move above destination
        [*dest_xy, -300.0],   # lower
        [*dest_xy, 0.0],      # lift clear
    ]
    status = machine.status()
    assert status.cube_position == [*dest_xy, -300.0]
    assert status.gripper_closed is False
    assert status.position == [*dest_xy, 0.0]


def test_cube_follows_gripper_while_held():
    machine = make_machine()
    seen = {}

    async def scenario():
        machine.request_start()
        await wait_for_state(machine, "PickPlace_moveToDest")
        seen["held"] = machine.cube_position == machine.driver.position
        seen["gripper"] = machine.driver.gripper_closed
        await wait_for_state(machine, "ready")

    run(scenario())
    assert seen == {"held": True, "gripper": True}


def test_snapshot_while_carrying_and_restore_after_restart():
    machine = make_machine()
    snapshots = {}

    async def scenario():
        machine.request_start()
        await wait_for_state(machine, "PickPlace_moveToDest")
        snapshots["carrying"] = machine.robot_snapshot()
        await wait_for_state(machine, "ready")

    run(scenario())
    carrying = snapshots["carrying"]
    assert carrying.cube_held is True
    assert carrying.gripper_closed is True
    assert carrying.cube_position == carrying.position

    # "Restart": a new driver built at the saved position, then restore.
    restarted = make_machine(driver=FastDriver(position=carrying.position))
    restarted.restore_robot_state(carrying)
    assert restarted.state == "ready"
    assert restarted.driver.gripper_closed is True
    assert restarted.cube_position == carrying.position


def test_snapshot_after_sequence_has_cube_on_table_b():
    machine = make_machine()

    async def scenario():
        machine.request_start()
        await wait_for_state(machine, "PickPlace_liftClear")
        await wait_for_state(machine, "ready")

    run(scenario())
    snapshot = machine.robot_snapshot()
    assert snapshot.cube_held is False
    assert snapshot.gripper_closed is False
    assert snapshot.cube_position == machine.status().destination_position


def test_home_lifts_first_then_moves_home():
    driver = FastDriver(position=[100, 100, -200])
    machine = make_machine(driver=driver)

    async def scenario():
        assert machine.request_home() is None
        await wait_for_state(machine, "ready")

    run(scenario())
    assert visited(machine) == ["Homing_moving", "ready"]
    assert driver.targets == [[100.0, 100.0, 0.0], [0.0, 0.0, 0.0]]


def test_jog_moves_robot_and_returns_to_ready():
    machine = make_machine()

    async def scenario():
        assert machine.request_jog([10, -20, -30]) is None
        await wait_for_state(machine, "ready")

    run(scenario())
    assert machine.driver.position == [10.0, -20.0, -30.0]


def test_jog_outside_limits_is_refused_without_fault():
    machine = make_machine()
    error = machine.request_jog([0, 0, -1500])
    assert error is not None and "limits" in error
    assert machine.state == "ready"


def test_motion_error_faults_and_reset_recovers():
    machine = make_machine()

    async def scenario():
        assert machine.request_start() is None
        # Shrink the driver's Z range after validation passed, so the
        # lowering move (to -300) is rejected by the driver at runtime.
        machine.driver.limits = [1000, 1000, 100]
        await wait_for_state(machine, "fault")

    run(scenario())
    status = machine.status()
    assert "outside of the limits" in status.last_error
    assert visited(machine)[-2:] == ["PickPlace_lowerToCube", "fault"]
    assert status.moving is False

    assert machine.request_reset() is None
    assert machine.state == "ready"
    assert machine.status().last_error is None


def test_motion_timeout_faults():
    machine = make_machine(driver=StuckDriver())
    machine.TIMEOUT_MARGIN_S = 0.05
    machine.TIMEOUT_FACTOR = 0

    async def scenario():
        machine.request_home()
        await wait_for_state(machine, "fault")
        await asyncio.sleep(0.01)
        return [t for t in machine._tasks if not t.done()]

    alive = run(scenario())
    assert machine.status().last_error == "Motion timed out in Homing_moving"
    assert alive == []
    assert machine.driver.is_moving is False


def test_operator_stop_cancels_motion():
    machine = make_machine(driver=StuckDriver())

    async def scenario():
        machine.request_home()
        await asyncio.sleep(0.01)
        assert machine.driver.is_moving
        machine.request_stop()
        await asyncio.sleep(0.01)

    run(scenario())
    assert machine.state == "fault"
    assert machine.status().last_error == "Stopped by operator"
    assert machine.driver.is_moving is False


def test_start_refused_while_sequence_running():
    machine = make_machine(driver=StuckDriver())

    async def scenario():
        assert machine.request_start() is None
        await asyncio.sleep(0.01)
        return machine.request_start(), machine.request_home()

    start_error, home_error = run(scenario())
    assert "PickPlace_moveToCube" in start_error
    assert "PickPlace_moveToCube" in home_error


def test_start_refused_with_invalid_config():
    machine = make_machine()
    machine.config.cube = (600, 0)
    error = machine.request_start()
    assert error is not None and "Table A" in error
    assert machine.state == "ready"


def test_update_config_validates_and_moves_cube():
    machine = make_machine()
    assert machine.update_config(CellConfig(destination=(0, 900))) is not None

    assert machine.update_config(CellConfig(cube=(0, 0), home=(5, 5, 0))) is None
    assert machine.cube_position == [-900.0, 400.0, -300.0]
    assert machine.driver.home_position == [5.0, 5.0, 0.0]


def test_update_config_refused_while_busy():
    machine = make_machine(driver=StuckDriver())

    async def scenario():
        machine.request_home()
        await asyncio.sleep(0.01)
        return machine.update_config(CellConfig())

    assert "Homing_moving" in run(scenario())


def test_reset_only_from_fault():
    machine = make_machine()
    assert machine.request_reset() is not None


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"speed": 0}, "Speed"),
        ({"pick_z": 10, "safe_z": 0}, "below the travel height"),
        ({"safe_z": 0, "pick_z": -1100}, "Z range"),
        ({"home": (0, 0, 2000)}, "Home position"),
    ],
)
def test_invalid_configs_are_rejected(changes, message):
    machine = make_machine()
    error = machine.update_config(CellConfig(**changes))
    assert error is not None and message in error
