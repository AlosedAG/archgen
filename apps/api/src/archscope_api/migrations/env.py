"""Alembic environment: the database URL comes from the app settings
(ARCHSCOPE_DATABASE_URL), the schema from the ORM models."""

from __future__ import annotations

from alembic import context
from sqlalchemy import Connection, engine_from_config, pool

from archscope_api.persistence.models import Base
from archscope_api.settings import Settings

config = context.config
url = config.get_main_option("sqlalchemy.url") or Settings().database_url
target_metadata = Base.metadata


def run_offline() -> None:
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, render_as_batch=url.startswith("sqlite"))
    with context.begin_transaction():
        context.run_migrations()


def run_online() -> None:
    connectable = config.attributes.get("connection")
    if connectable is None:
        connectable = engine_from_config({"sqlalchemy.url": url}, prefix="sqlalchemy.", poolclass=pool.NullPool)
        with connectable.connect() as connection:
            _run(connection)
    else:
        _run(connectable)


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=url.startswith("sqlite"))
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_offline()
else:
    run_online()
