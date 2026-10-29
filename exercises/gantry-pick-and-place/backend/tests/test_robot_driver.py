import asyncio

import pytest

from app.robot_driver import MotionError, RobotDriver


# Short moves at full speed keep these tests fast (5 mm at 100 mm/s = 50 ms).
FAST = 100


def run(coro):
    return asyncio.run(coro)


def test_move_reaches_target_exactly():
    driver = RobotDriver()
    final = run(driver.move([5, -3, 2], FAST))
    assert final == [5.0, -3.0, 2.0]
    assert driver.position == [5.0, -3.0, 2.0]
    assert not driver.is_moving


def test_starts_at_initial_position():
    driver = RobotDriver(initial_position=[100, -50, -20])
    assert driver.position == [100.0, -50.0, -20.0]
    assert run(driver.move([100, -50, 0], FAST)) == [100.0, -50.0, 0.0]


def test_initial_position_outside_limits_is_rejected():
    with pytest.raises(MotionError, match="outside the robot limits"):
        RobotDriver(initial_position=[0, 0, -1500])


def test_move_to_current_position_returns_immediately():
    driver = RobotDriver()
    assert run(driver.move([0, 0, 0], FAST)) == [0.0, 0.0, 0.0]


def test_is_moving_while_in_motion():
    driver = RobotDriver()

    async def scenario():
        task = asyncio.create_task(driver.move([5, 0, 0], FAST))
        await asyncio.sleep(0.01)
        moving_during = driver.is_moving
        await task
        return moving_during

    assert run(scenario()) is True
    assert driver.is_moving is False


def test_out_of_limits_target_raises():
    driver = RobotDriver()
    with pytest.raises(MotionError, match="outside of the limits"):
        run(driver.move([1500, 0, 0], FAST))
    assert driver.position == [0.0, 0.0, 0.0]


@pytest.mark.parametrize("speed", [0, -10, 101])
def test_invalid_speed_is_rejected(speed):
    driver = RobotDriver()
    with pytest.raises(MotionError, match="Speed"):
        run(driver.move([5, 0, 0], speed))


def test_wrong_number_of_axes_is_rejected():
    driver = RobotDriver()
    with pytest.raises(MotionError, match="3 axes"):
        run(driver.move([5, 0], FAST))


def test_caller_list_is_not_aliased():
    driver = RobotDriver()
    target = [5.0, 0.0, 0.0]
    run(driver.move(target, FAST))
    run(driver.move([0, 5, 0], FAST))
    assert target == [5.0, 0.0, 0.0]

    # Mutating the returned position must not move the robot either.
    driver.position[0] = 999
    assert driver.position == [0.0, 5.0, 0.0]


def test_new_move_after_cancellation_is_not_skewed():
    driver = RobotDriver()

    async def scenario():
        task = asyncio.create_task(driver.move([50, 0, 0], FAST))
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        stopped_at = driver.position
        final = await driver.move([0, 5, 0], FAST)
        return stopped_at, final

    stopped_at, final = run(scenario())
    assert 0 < stopped_at[0] < 50
    assert final == [0.0, 5.0, 0.0]
    assert not driver.is_moving


def test_gripper_open_and_close():
    driver = RobotDriver()
    assert driver.gripper_closed is False
    driver.close_gripper()
    assert driver.gripper_closed is True
    driver.open_gripper()
    assert driver.gripper_closed is False
