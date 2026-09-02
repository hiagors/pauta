"""Ambiente de execução das migrations.

A URL do banco vem de `DATABASE_URL` (definida no `mise.toml`), nunca do
`alembic.ini`. O `target_metadata` é o do `models.py` do adapter de
persistência — é dele que o `--autogenerate` compara o schema.

Há um segundo caminho de entrada: quem chama pode injetar uma conexão já
aberta em `config.attributes["connection"]`. É o que a suíte de HTTP usa para
criar o schema em memória **rodando as migrations** (RNF2) em vez de
`metadata.create_all()`. Um `sqlite:///:memory:` morre com a conexão, então
migrar por uma engine própria migraria um banco descartável; com a conexão
injetada, a migration e os testes compartilham o mesmo banco.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, engine_from_config, pool

from app.adapters.outbound.persistence.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

#: Conexão injetada por quem chama, quando houver (ver docstring do módulo).
injected_connection = config.attributes.get("connection")

if injected_connection is None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL não está definida. Rode as migrations pelo mise "
            "(`mise run setup:db`), que exporta a variável."
        )
    config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


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


def run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica as migrations com uma conexão aberta.

    A conexão injetada tem precedência: quem a passou é dono dela e a fecha.
    """
    if injected_connection is not None:
        run_migrations(injected_connection)
        return
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
