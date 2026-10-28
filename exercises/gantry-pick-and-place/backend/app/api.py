"""RPC actions and the telemetry stream, exposed with vention-communication.

The `@action` / `@stream` decorators register into module-level lists when this
file is imported, and `VentionApp.finalize()` (in main.py) turns them into
routes under /rpc/vention.app.v1.GantryAppService/<name>. Because of that the
handlers are plain functions; they reach the machine and store through the
`runtime` holder, which main.py fills in at startup.

Handlers never raise for expected refusals: the library would turn an exception
into an HTTP 200 with an "error" body, so commands return `CommandResult`.
Requests accept camelCase or snake_case field names (generated Connect clients
send camelCase); responses use the snake_case proto field names, which
protobuf JSON parsers also accept.

Request messages give every field its proto3 default (zero / empty message):
protobuf JSON *omits* fields that hold their default value, so a client sends
`home: {}` for (0, 0, 0) and no `safeZ` at all for 0. Required Pydantic fields
would reject those requests.
"""

from __future__ import annotations

import asyncio
import logging

from pydantic import BaseModel, Field

from communication.decorators import action, stream

from app.config import CellConfig
from app.config_store import ConfigStore
from app.machine import GantryMachine, MachineStatus


logger = logging.getLogger(__name__)

TELEMETRY_PERIOD_S = 0.05


class Runtime:
    """What the handlers act on; set by main.py at startup (and by tests)."""

    machine: GantryMachine
    store: ConfigStore


runtime = Runtime()


# ------------------------------------------------------------------ messages


class Point2(BaseModel):
    x: float = 0.0
    y: float = 0.0


class Point3(BaseModel):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


class Config(BaseModel):
    cube: Point2 = Field(default_factory=Point2)
    """Cube start position in Table A's frame (mm)."""
    destination: Point2 = Field(default_factory=Point2)
    """Cube destination in Table B's frame (mm)."""
    home: Point3 = Field(default_factory=Point3)
    safe_z: float = 0.0
    pick_z: float = 0.0
    speed: int = 0


class CommandResult(BaseModel):
    ok: bool
    error: str = ""


class Telemetry(BaseModel):
    state: str
    position: Point3
    gripper_closed: bool
    moving: bool
    cube_position: Point3
    destination_position: Point3
    error: str
    """Last fault message, or empty when not faulted."""


# ------------------------------------------------------------------- actions


@action()
async def get_config() -> Config:
    return config_to_message(runtime.machine.config)


@action()
async def set_config(request: Config) -> CommandResult:
    config = message_to_config(request)
    error = runtime.machine.update_config(config)
    if error:
        return CommandResult(ok=False, error=error)
    try:
        runtime.store.save(config)
    except Exception as exc:  # noqa: BLE001 - report instead of failing the RPC
        logger.exception("Failed to save configuration")
        return CommandResult(ok=False, error=f"Configuration applied but not saved: {exc}")
    return CommandResult(ok=True)


@action()
async def get_robot_position() -> Point3:
    return point3(runtime.machine.driver.position)


@action()
async def move_robot(request: Point3) -> CommandResult:
    return result(runtime.machine.request_jog([request.x, request.y, request.z]))


@action()
async def home_robot() -> CommandResult:
    return result(runtime.machine.request_home())


@action()
async def start_sequence() -> CommandResult:
    return result(runtime.machine.request_start())


@action()
async def stop() -> CommandResult:
    return result(runtime.machine.request_stop())


@action()
async def reset_fault() -> CommandResult:
    return result(runtime.machine.request_reset())


@action()
async def get_status() -> Telemetry:
    return status_to_telemetry(runtime.machine.status())


# ----------------------------------------------------------------- telemetry


@stream(name="telemetry", payload=Telemetry, replay=True, queue_maxsize=1, policy="latest")
async def publish_telemetry() -> Telemetry:
    return status_to_telemetry(runtime.machine.status())


async def telemetry_loop() -> None:
    """Publish the machine status to all subscribers every TELEMETRY_PERIOD_S."""
    while True:
        try:
            await publish_telemetry()
        except Exception:  # noqa: BLE001 - keep streaming even if one tick fails
            logger.exception("Telemetry publish failed")
        await asyncio.sleep(TELEMETRY_PERIOD_S)


# --------------------------------------------------------------- conversions


def result(error: str | None) -> CommandResult:
    return CommandResult(ok=error is None, error=error or "")


def point3(values: list[float]) -> Point3:
    x, y, z = values
    return Point3(x=x, y=y, z=z)


def config_to_message(config: CellConfig) -> Config:
    return Config(
        cube=Point2(x=config.cube[0], y=config.cube[1]),
        destination=Point2(x=config.destination[0], y=config.destination[1]),
        home=point3(list(config.home)),
        safe_z=config.safe_z,
        pick_z=config.pick_z,
        speed=config.speed,
    )


def message_to_config(message: Config) -> CellConfig:
    return CellConfig(
        cube=(message.cube.x, message.cube.y),
        destination=(message.destination.x, message.destination.y),
        home=(message.home.x, message.home.y, message.home.z),
        safe_z=message.safe_z,
        pick_z=message.pick_z,
        speed=message.speed,
    )


def status_to_telemetry(status: MachineStatus) -> Telemetry:
    return Telemetry(
        state=status.state,
        position=point3(status.position),
        gripper_closed=status.gripper_closed,
        moving=status.moving,
        cube_position=point3(status.cube_position),
        destination_position=point3(status.destination_position),
        error=status.last_error or "",
    )
