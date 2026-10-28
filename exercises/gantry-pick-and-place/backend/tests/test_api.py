import asyncio
import os
import time

import pytest
from fastapi.testclient import TestClient

from app import api
from app.config import CellConfig
from app.config_store import ConfigStore, RobotStateStore
from app.machine import GantryMachine, RobotSnapshot
from app.main import PROTO_PATH, app, create_machine, load_startup_config, load_startup_robot
from app.robot_driver import RobotDriver
from tests.fakes import FastDriver, StuckDriver


SERVICE = "/rpc/vention.app.v1.GantryAppService"


@pytest.fixture(scope="session", autouse=True)
def database(tmp_path_factory):
    # vention-storage's engine is a process-wide singleton, so the whole test
    # session shares one throwaway database file.
    path = tmp_path_factory.mktemp("db") / "test.db"
    os.environ["GANTRY_DB_URL"] = f"sqlite:///{path.as_posix()}"
    yield
    os.environ.pop("GANTRY_DB_URL", None)


def install_machine(driver=None):
    # Built like main.py builds it, so robot state is saved after each transition.
    machine = create_machine(driver or FastDriver(), CellConfig(), RobotStateStore())
    machine.GRIPPER_DELAY_S = 0
    api.runtime.machine = machine
    return machine


@pytest.fixture(scope="session")
def app_client(database):
    # One client (one event loop) for the whole session: the library's stream
    # queues bind to the first loop that uses them, and a real server only
    # ever has one loop.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client(app_client):
    # Start every test from the defaults with an instant driver.
    api.runtime.store.save(CellConfig(), actor="test")
    install_machine()
    return app_client


def rpc(client, name, body=None):
    response = client.post(f"{SERVICE}/{name}", json=body or {})
    assert response.status_code == 200
    return response.json()


def wait_for_state(client, state, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = rpc(client, "get_status")
        if status["state"] == state:
            return status
        time.sleep(0.01)
    raise AssertionError(f"State never became {state!r}; last status: {status}")


VALID_CONFIG = {
    "cube": {"x": 100, "y": 400},
    "destination": {"x": 50, "y": 450},
    "home": {"x": 0, "y": 0, "z": 0},
    "safe_z": 0,
    "pick_z": -250,
    "speed": 80,
}


def test_status_uses_camel_case_and_starts_ready(client):
    status = rpc(client, "get_status")
    assert status["state"] == "ready"
    assert status["position"] == {"x": 0.0, "y": 0.0, "z": 0.0}
    assert status["gripper_closed"] is False
    assert status["moving"] is False
    assert status["cube_position"] == {"x": -650.0, "y": 650.0, "z": -300.0}
    assert status["error"] == ""


def test_get_config_returns_defaults(client):
    assert rpc(client, "get_config") == {
        "cube": {"x": 250.0, "y": 250.0},
        "destination": {"x": 250.0, "y": 250.0},
        "home": {"x": 0.0, "y": 0.0, "z": 0.0},
        "safe_z": 0.0,
        "pick_z": -300.0,
        "speed": 100,
    }


def test_set_config_applies_and_saves(client):
    assert rpc(client, "set_config", VALID_CONFIG) == {"ok": True, "error": ""}

    config = rpc(client, "get_config")
    assert config["cube"] == {"x": 100.0, "y": 400.0}
    assert config["pick_z"] == -250.0

    saved = ConfigStore().load()
    assert saved.cube == (100.0, 400.0)
    assert saved.speed == 80


def test_set_config_rejects_cube_off_table(client):
    body = {**VALID_CONFIG, "cube": {"x": 600, "y": 0}}
    response = rpc(client, "set_config", body)
    assert response["ok"] is False
    assert "Table A" in response["error"]
    assert ConfigStore().load() == CellConfig()


def test_set_config_accepts_camel_case_too(client):
    # Generated Connect clients send camelCase JSON names; responses are snake_case.
    body = {**VALID_CONFIG, "safeZ": 0, "pickZ": -200}
    del body["safe_z"], body["pick_z"]
    assert rpc(client, "set_config", body)["ok"] is True
    assert rpc(client, "get_config")["pick_z"] == -200.0


def test_zero_valued_fields_may_be_omitted(client):
    # Protobuf JSON leaves out fields at their default value: this is what the
    # generated browser client sends for home (0, 0, 0) and a travel height of 0.
    body = {"cube": {"x": 600, "y": 400}, "destination": {"x": 50, "y": 450}, "home": {}, "pickZ": -250, "speed": 100}
    response = rpc(client, "set_config", body)
    assert response["ok"] is False
    assert "Table A" in response["error"]

    body["cube"] = {"x": 100, "y": 400}
    assert rpc(client, "set_config", body) == {"ok": True, "error": ""}
    config = rpc(client, "get_config")
    assert config["home"] == {"x": 0.0, "y": 0.0, "z": 0.0}
    assert config["safe_z"] == 0.0


def test_move_robot_to_origin_with_empty_body(client):
    rpc(client, "move_robot", {"x": 10, "y": 0, "z": 0})
    wait_for_state(client, "ready")
    assert rpc(client, "move_robot", {}) == {"ok": True, "error": ""}
    wait_for_state(client, "ready")
    assert rpc(client, "get_robot_position") == {"x": 0.0, "y": 0.0, "z": 0.0}


def test_malformed_request_returns_error_envelope(client):
    # The library turns validation exceptions into {"error": {...}} with HTTP 200.
    response = rpc(client, "set_config", {"speed": "fast"})
    assert "error" in response and "code" in response["error"]


def test_start_sequence_runs_to_completion(client):
    assert rpc(client, "start_sequence") == {"ok": True, "error": ""}
    status = wait_for_state(client, "ready")
    assert status["cube_position"] == status["destination_position"]
    assert status["gripper_closed"] is False


def test_start_refused_while_busy(client):
    install_machine(StuckDriver())
    assert rpc(client, "start_sequence")["ok"] is True
    response = rpc(client, "start_sequence")
    assert response["ok"] is False
    assert "PickPlace_moveToCube" in response["error"]


def test_move_robot_and_get_position(client):
    assert rpc(client, "move_robot", {"x": 10, "y": 20, "z": -30})["ok"] is True
    wait_for_state(client, "ready")
    assert rpc(client, "get_robot_position") == {"x": 10.0, "y": 20.0, "z": -30.0}


def test_move_robot_outside_limits_is_refused(client):
    response = rpc(client, "move_robot", {"x": 0, "y": 0, "z": -2000})
    assert response["ok"] is False
    assert "limits" in response["error"]
    assert rpc(client, "get_status")["state"] == "ready"


def test_home_robot(client):
    rpc(client, "move_robot", {"x": 50, "y": 50, "z": -50})
    wait_for_state(client, "ready")
    assert rpc(client, "home_robot")["ok"] is True
    wait_for_state(client, "ready")
    assert rpc(client, "get_robot_position") == {"x": 0.0, "y": 0.0, "z": 0.0}


def test_stop_faults_and_reset_recovers(client):
    install_machine(StuckDriver())
    rpc(client, "home_robot")
    assert rpc(client, "stop")["ok"] is True

    status = wait_for_state(client, "fault")
    assert status["error"] == "Stopped by operator"
    assert status["moving"] is False

    assert rpc(client, "reset_fault")["ok"] is True
    status = rpc(client, "get_status")
    assert status["state"] == "ready"
    assert status["error"] == ""


def test_reset_refused_when_not_faulted(client):
    response = rpc(client, "reset_fault")
    assert response == {"ok": False, "error": "Reset is only needed after a fault"}


def test_config_survives_restart(client):
    assert rpc(client, "set_config", VALID_CONFIG)["ok"] is True

    # What startup does: a fresh store reading the database, then a new machine.
    config = load_startup_config(ConfigStore(), [1000, 1000, 1000])
    restarted = GantryMachine(driver=FastDriver(), config=config)
    assert restarted.config.cube == (100.0, 400.0)
    assert restarted.config.speed == 80


def test_robot_state_saved_after_each_move(client):
    rpc(client, "move_robot", {"x": 10, "y": 20, "z": -30})
    wait_for_state(client, "ready")
    assert RobotStateStore().load().position == [10.0, 20.0, -30.0]


def test_robot_state_saved_where_a_stopped_move_halted(client):
    # Real simulator driver: 50 mm at 100 mm/s takes 0.5 s; stop it halfway.
    install_machine(RobotDriver())
    rpc(client, "move_robot", {"x": 50, "y": 0, "z": 0})
    time.sleep(0.2)
    rpc(client, "stop")
    wait_for_state(client, "fault")

    saved = RobotStateStore().load().position
    current = rpc(client, "get_robot_position")
    assert 0 < saved[0] < 50
    assert saved == [current["x"], current["y"], current["z"]]


def test_robot_state_restored_after_restart(client):
    rpc(client, "start_sequence")
    wait_for_state(client, "ready")
    before = rpc(client, "get_status")

    # What startup does: driver at the saved position, then restore the cube/gripper.
    driver, snapshot = load_startup_robot(RobotStateStore())
    restarted = create_machine(driver, CellConfig(), RobotStateStore(), snapshot)
    status = restarted.status()
    assert status.state == "ready"
    assert status.position == [before["position"][k] for k in "xyz"]
    assert status.cube_position == [before["cube_position"][k] for k in "xyz"]
    assert status.gripper_closed is False


def test_invalid_saved_robot_state_falls_back_to_origin(client):
    RobotStateStore().save(
        RobotSnapshot(position=[5000, 0, 0], gripper_closed=False, cube_position=[0, 0, 0], cube_held=False)
    )
    driver, snapshot = load_startup_robot(RobotStateStore())
    assert driver.position == [0.0, 0.0, 0.0]
    assert snapshot is None


def test_invalid_saved_config_falls_back_to_defaults(client):
    store = ConfigStore()
    store.save(CellConfig(cube=(900, 900)), actor="test")
    config = load_startup_config(store, [1000, 1000, 1000])
    assert config == CellConfig()
    assert store.load() == CellConfig()


def test_telemetry_stream_publishes_status(client):
    manager = app.connect_router.manager

    async def first_message():
        subscriber = manager.subscribe("telemetry")
        try:
            await api.publish_telemetry()
            return await asyncio.wait_for(subscriber.queue.get(), 1)
        finally:
            manager.unsubscribe("telemetry", subscriber)

    message = client.portal.call(first_message)
    payload = message.model_dump(by_alias=True)
    assert payload["state"] == "ready"
    assert set(payload) == {
        "state", "position", "gripper_closed", "moving",
        "cube_position", "destination_position", "error",
    }


def test_proto_is_emitted_with_all_rpcs():
    proto = PROTO_PATH.read_text(encoding="utf-8")
    for name in [
        "get_config", "set_config", "get_robot_position", "move_robot", "home_robot",
        "start_sequence", "stop", "reset_fault", "get_status",
    ]:
        assert f"rpc {name} (" in proto
    assert "rpc telemetry (google.protobuf.Empty) returns (stream Telemetry);" in proto
