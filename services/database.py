import os
from collections.abc import Generator

from sqlalchemy import Engine, event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.storage import db as tinydb_client, users_table as tinydb_users

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be configured before starting the inventory service")

_engine_options: dict[str, object] = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    _engine_options["connect_args"] = {"check_same_thread": False}
    if DATABASE_URL in {"sqlite://", "sqlite:///:memory:"}:
        _engine_options["poolclass"] = StaticPool

engine: Engine = create_engine(DATABASE_URL, **_engine_options)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(connection, _record) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_db_and_tables() -> None:
    from services import models as inventory_models

    tables = [inventory_models.SKU.__table__, inventory_models.StockEntry.__table__, inventory_models.StockExit.__table__]
    SQLModel.metadata.create_all(engine, tables=tables)


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
