"""Persist the cell configuration with vention-storage.

We deliberately don't call `storage.bootstrap()`: it would also mount REST
CRUD endpoints for the config table (and a /db backup/restore router), which
would let clients change the configuration without validation and while the
machine is busy. Using the lower-level pieces keeps `set_config` as the only
way to change it, while still getting the library's sessions and audit log.
"""

from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel

from storage.accessor import ModelAccessor
from storage.database import get_engine, set_database_url

from app.config import CellConfig


CONFIG_ROW_ID = 1


class ConfigRecord(SQLModel, table=True):
    """The single saved configuration row (flattened `CellConfig`)."""

    __tablename__ = "cell_config"

    id: Optional[int] = Field(default=None, primary_key=True)
    cube_x: float
    cube_y: float
    destination_x: float
    destination_y: float
    home_x: float
    home_y: float
    home_z: float
    safe_z: float
    pick_z: float
    speed: int


def init_database(url: str) -> None:
    """Point vention-storage at `url` and create missing tables.

    The library's engine is a process-wide singleton whose URL can only be set
    before first use, so later calls (e.g. a second app startup in tests) just
    ensure the tables exist on the existing engine.
    """
    try:
        set_database_url(url)
    except RuntimeError:
        pass
    SQLModel.metadata.create_all(get_engine())


class ConfigStore:
    def __init__(self) -> None:
        self._accessor = ModelAccessor(ConfigRecord, "cell_config")

    def load(self) -> Optional[CellConfig]:
        """The saved configuration, or None if nothing has been saved yet."""
        record = self._accessor.get(CONFIG_ROW_ID)
        return _to_config(record) if record else None

    def save(self, config: CellConfig, actor: str = "operator") -> None:
        self._accessor.save(_to_record(config), actor=actor)


def _to_record(config: CellConfig) -> ConfigRecord:
    return ConfigRecord(
        id=CONFIG_ROW_ID,
        cube_x=config.cube[0],
        cube_y=config.cube[1],
        destination_x=config.destination[0],
        destination_y=config.destination[1],
        home_x=config.home[0],
        home_y=config.home[1],
        home_z=config.home[2],
        safe_z=config.safe_z,
        pick_z=config.pick_z,
        speed=config.speed,
    )


def _to_config(record: ConfigRecord) -> CellConfig:
    return CellConfig(
        cube=(record.cube_x, record.cube_y),
        destination=(record.destination_x, record.destination_y),
        home=(record.home_x, record.home_y, record.home_z),
        safe_z=record.safe_z,
        pick_z=record.pick_z,
        speed=record.speed,
    )
