"""Application entry point: `uvicorn app.main:app` from the backend folder."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import AsyncIterator

from fastapi.middleware.cors import CORSMiddleware

from communication.app import VentionApp

from app import api
from app.config import CellConfig, validate_config
from app.config_store import ConfigStore, init_database
from app.machine import GantryMachine


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


@asynccontextmanager
async def lifespan(_: VentionApp) -> AsyncIterator[None]:
    db_url = os.getenv("GANTRY_DB_URL", DEFAULT_DB_URL)
    if db_url == DEFAULT_DB_URL:
        (BACKEND_DIR / "data").mkdir(exist_ok=True)
    init_database(db_url)

    store = ConfigStore()
    machine = GantryMachine()
    machine.update_config(load_startup_config(store, machine.driver.limits))
    api.runtime.store = store
    api.runtime.machine = machine

    telemetry = asyncio.create_task(api.telemetry_loop())
    try:
        yield
    finally:
        telemetry.cancel()
        with suppress(asyncio.CancelledError):
            await telemetry
        await machine.cancel_tasks()


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
