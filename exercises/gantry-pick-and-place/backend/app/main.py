"""Application entry point: `uvicorn app.main:app` from the backend folder."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi.middleware.cors import CORSMiddleware

from communication.app import VentionApp

from app import api
from app.config import CellConfig, validate_config
from app.config_store import ConfigStore, RobotStateStore, init_database
from app.machine import GantryMachine, RobotSnapshot
from app.robot_driver import GantryDriver, MotionError, RobotDriver


logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_URL = f"sqlite:///{(BACKEND_DIR / 'data' / 'gantry.db').as_posix()}"
PROTO_PATH = BACKEND_DIR / "proto" / "app.proto"
FRONTEND_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def load_startup_config(store: ConfigStore, machine_limits: list[float]) -> CellConfig:
    """The saved config if there is a valid one, otherwise the defaults (saved for next time)."""
    saved = store.load()
    if saved is not None:
        error = validate_config(saved, machine_limits)
        if error is None:
            return saved
        logger.warning("Ignoring invalid saved configuration: %s", error)
    config = CellConfig()
    store.save(config, actor="system")
    return config


def load_startup_robot(state_store: RobotStateStore) -> tuple[RobotDriver, Optional[RobotSnapshot]]:
    """A simulator driver placed where the robot was last saved, plus that saved state.

    Falls back to a robot at the origin (and no saved state) if nothing was
    saved or the saved position is outside the robot's limits.
    """
    snapshot = state_store.load()
    if snapshot is None:
        return RobotDriver(), None
    try:
        return RobotDriver(initial_position=snapshot.position), snapshot
    except MotionError as exc:
        logger.warning("Ignoring invalid saved robot state: %s", exc)
        return RobotDriver(), None


def create_machine(
    driver: GantryDriver,
    config: CellConfig,
    state_store: RobotStateStore,
    snapshot: Optional[RobotSnapshot] = None,
) -> GantryMachine:
    """Build the machine and make it save the robot's state after every transition.

    `config` is expected to be valid already (see `load_startup_config`).
    """
    machine = GantryMachine(driver=driver, config=config)
    if snapshot is not None:
        machine.restore_robot_state(snapshot)
    # Transitions happen when a move finishes, the gripper acts, or the machine
    # stops/faults, so this saves at each of those points (not on every poll).
    machine.add_state_change_callback(lambda *_: save_robot_state(machine, state_store))
    return machine


def save_robot_state(machine: GantryMachine, state_store: RobotStateStore) -> None:
    try:
        state_store.save(machine.robot_snapshot())
    except Exception:  # noqa: BLE001 - never let a failed save break a transition
        logger.exception("Failed to save robot state")


@asynccontextmanager
async def lifespan(_: VentionApp) -> AsyncIterator[None]:
    db_url = os.getenv("GANTRY_DB_URL", DEFAULT_DB_URL)
    if db_url == DEFAULT_DB_URL:
        (BACKEND_DIR / "data").mkdir(exist_ok=True)
    init_database(db_url)

    config_store = ConfigStore()
    state_store = RobotStateStore()
    driver, snapshot = load_startup_robot(state_store)
    config = load_startup_config(config_store, driver.limits)
    machine = create_machine(driver, config, state_store, snapshot)
    api.runtime.store = config_store
    api.runtime.machine = machine

    telemetry = asyncio.create_task(api.telemetry_loop())
    try:
        yield
    finally:
        telemetry.cancel()
        with suppress(asyncio.CancelledError):
            await telemetry
        await machine.cancel_tasks()
        # Covers a shutdown in the middle of a move.
        save_robot_state(machine, state_store)


app = VentionApp(
    name="GantryApp",
    emit_proto=True,
    proto_path=str(PROTO_PATH),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.finalize()
