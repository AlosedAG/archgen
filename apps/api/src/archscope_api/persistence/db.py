"""Engine and session factory, one engine per database URL per process."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

CONNECT_TIMEOUT_S = 10


@lru_cache(maxsize=8)
def get_engine(database_url: str) -> Engine:
    """The process-wide engine for a URL. SQLite gets foreign keys switched
    on (off by default) and, for in-memory databases, a single shared
    connection so every session sees the same data."""
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if database_url.startswith("postgresql"):
        # A serverless database (Neon) suspends when idle: don't hang on a slow
        # resume, and replace connections it has closed in the meantime.
        kwargs["connect_args"] = {"connect_timeout": CONNECT_TIMEOUT_S}
        kwargs["pool_recycle"] = 300
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in database_url or database_url in ("sqlite://", "sqlite+pysqlite://"):
            kwargs["poolclass"] = StaticPool
        else:
            path = database_url.split("///", 1)[-1]
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url, **kwargs)
    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection: Any, _record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


@lru_cache(maxsize=8)
def _sessionmaker(database_url: str) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(database_url), expire_on_commit=False)


@contextmanager
def session_scope(database_url: str) -> Iterator[Session]:
    """``with session_scope(url) as db:`` — committed when the block
    finishes normally, rolled back if it raises."""
    session = _sessionmaker(database_url)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
