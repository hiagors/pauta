"""A migration sobe e desce — o critério de aceite da Fase 3.

E, o que é mais fácil de esquecer: ela **não divergiu** do `models.py`. Um
schema escrito à mão numa migration e um `models.py` editado depois passam
anos concordando por sorte; `compare_metadata` é a mesma comparação que o
`alembic check` faz, rodando na suíte em vez de na memória de quem lembrar de
rodar o comando.
"""

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, inspect

from app.adapters.outbound.persistence.models import Base
from app.adapters.outbound.persistence.session import make_engine
from tests.persistence.conftest import (
    alembic_config,
    database_url,
    downgrade,
    upgrade,
)

#: A tabela de controle do próprio Alembic, que o `downgrade` não remove.
ALEMBIC_VERSION = "alembic_version"


def _tables(path: Path) -> set[str]:
    with sqlite3.connect(path) as connection:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return {name for (name,) in rows if not name.startswith("sqlite_")}


def test_the_migration_creates_every_table_of_the_model(sqlite_path: Path) -> None:
    assert _tables(sqlite_path) == set(Base.metadata.tables) | {ALEMBIC_VERSION}


def test_external_refs_exists_and_is_empty(sqlite_path: Path) -> None:
    """§6.10 e §12: a tabela é pavimento da v2 e nasce vazia — não há `seed`
    (RNF5) e nenhum repositório escreve nela."""
    with sqlite3.connect(sqlite_path) as connection:
        (count,) = connection.execute("SELECT count(*) FROM external_refs").fetchone()
    assert count == 0


def test_the_migration_goes_down_and_up_again(tmp_path: Path) -> None:
    """Descer tem de deixar o banco vazio, e subir de novo tem de funcionar —
    é o que permite refazer o schema sem apagar o arquivo à mão."""
    path = tmp_path / "ciclo.sqlite"

    upgrade(path)
    assert "allocations" in _tables(path)

    downgrade(path)
    assert _tables(path) == {ALEMBIC_VERSION}

    upgrade(path)
    assert _tables(path) == set(Base.metadata.tables) | {ALEMBIC_VERSION}


def test_the_migration_and_the_models_do_not_diverge(engine: Engine) -> None:
    """`compare_metadata` vazio é o `alembic check` limpo."""
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        assert compare_metadata(context, Base.metadata) == []


def test_the_migration_is_the_only_way_the_schema_gets_created(
    tmp_path: Path,
) -> None:
    """RNF2: sem `create_all` no caminho de produção.

    Um banco novo, sem migration aplicada, não tem tabela nenhuma — inclusive
    porque abrir a engine não cria schema como efeito colateral.
    """
    path = tmp_path / "virgem.sqlite"
    engine = make_engine(database_url(path))
    with engine.connect() as connection:
        assert inspect(connection).get_table_names() == []
    engine.dispose()


def test_the_migration_refuses_to_run_without_database_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`migrations/env.py` falha alto: a URL vem do ambiente, nunca do
    `alembic.ini`, e um default silencioso migraria o banco errado."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        command.upgrade(alembic_config(tmp_path / "x.sqlite"), "head")
