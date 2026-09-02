"""Ambiente de execução das migrations.

A URL do banco vem de `DATABASE_URL` (definida no `mise.toml`), nunca do
`alembic.ini`. `target_metadata` continua `None` até a Fase 3, quando o
`models.py` do adapter de persistência passa a ser a fonte do autogenerate.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError(
        "DATABASE_URL não está definida. Rode as migrations pelo mise "
        "(`mise run setup:db`), que exporta a variável."
    )
config.set_main_option("sqlalchemy.url", database_url)

# Fase 3 troca por `models.Base.metadata`.
target_metadata = None


def run_migrations_offline() -> None:
    """Gera o SQL sem abrir conexão."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica as migrations com uma conexão aberta."""
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
