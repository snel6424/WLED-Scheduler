"""Alembic environment configuration.

Two things make this different from the stock template Alembic
generates:

1. The database URL comes from app.database.DATABASE_URL rather than
   the static value in alembic.ini, so `alembic upgrade head` always
   targets whatever DATABASE_PATH the app itself would use. The value
   in alembic.ini is only a fallback for local development.
2. render_as_batch=True is set in both online and offline mode.
   SQLite doesn't support most ALTER TABLE operations directly, so
   Alembic has to recreate the table under the hood instead. Without
   this, any future migration that touches an existing column (not
   just adding a new table) would fail outright on SQLite.
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Make `app` importable when Alembic is run from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import DATABASE_URL  # noqa: E402
from app.models import Base  # noqa: E402

config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
