"""Apoio dos testes de persistência (Fase 3).

Duas decisões que valem explicação:

- **O schema vem das migrations, não de `metadata.create_all()`** (RNF2). Se a
  migration não cria a tabela, a suíte não roda — é o único jeito de "a
  migration sobe" significar alguma coisa.
- **O banco migrado é montado uma vez e copiado por teste.** Reaplicar as
  migrations em cada um dos testes de contrato custaria mais do que copiar o
  arquivo, e cada teste continua começando num banco limpo e só seu.

A fixture `repos` é o coração da fase: ela devolve o **mesmo feixe de portas**
duas vezes, uma com os fakes da Fase 2 e outra com os repositórios SQLAlchemy.
É o que faz `test_repository_contract.py` ser literalmente a mesma suíte para
as duas implementações — o critério de aceite da fase.
"""

import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Self

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.outbound.persistence.repositories import (
    SqlAlchemyAllocationRepository,
    SqlAlchemyInitiativeRepository,
    SqlAlchemyMemberRepository,
    SqlAlchemyMutedAlertRepository,
    SqlAlchemyProjectRepository,
    SqlAlchemySprintRepository,
    SqlAlchemySquadMembershipRepository,
    SqlAlchemySquadRepository,
)
from app.adapters.outbound.persistence.session import make_engine, make_session_factory
from tests.application.conftest import TODAY, Fakes, Repositories, World
from tests.domain.conftest import FrozenClock

BACKEND = Path(__file__).resolve().parents[2]


def database_url(path: Path) -> str:
    """As três barras do `sqlite+pysqlite:///` mais o caminho absoluto dão as
    quatro que o SQLAlchemy exige — a mesma forma do `mise.toml`."""
    return f"sqlite+pysqlite:///{path}"


def alembic_config() -> Config:
    """O `alembic.ini` do projeto, com `script_location` absoluto.

    O do arquivo é relativo e depende de o processo estar em `backend/` (é o
    que o `dir` das tasks do mise garante); aqui o absoluto deixa a suíte
    rodar de qualquer diretório.
    """
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    return config


@contextmanager
def _database_url(path: Path) -> Iterator[None]:
    """`migrations/env.py` lê a URL de `DATABASE_URL`, e é assim que ela chega.

    Passar pela variável de ambiente, e não por `set_main_option`, é o que
    exercita o caminho de verdade — inclusive o `RuntimeError` que o `env.py`
    levanta quando ela falta.
    """
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url(path)
    try:
        yield
    finally:
        if previous is None:
            del os.environ["DATABASE_URL"]
        else:
            os.environ["DATABASE_URL"] = previous


def upgrade(path: Path, revision: str = "head") -> None:
    with _database_url(path):
        command.upgrade(alembic_config(), revision)


def downgrade(path: Path, revision: str = "base") -> None:
    with _database_url(path):
        command.downgrade(alembic_config(), revision)


@pytest.fixture(scope="session")
def migrated_database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Banco com as migrations aplicadas, montado uma vez por sessão."""
    path = tmp_path_factory.mktemp("schema") / "pauta.sqlite"
    upgrade(path)
    return path


@pytest.fixture
def sqlite_path(migrated_database: Path, tmp_path: Path) -> Path:
    """Cópia limpa do banco migrado, uma por teste."""
    path = tmp_path / "pauta.sqlite"
    shutil.copyfile(migrated_database, path)
    return path


@pytest.fixture
def engine(sqlite_path: Path) -> Iterator[Engine]:
    engine = make_engine(database_url(sqlite_path))
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return make_session_factory(engine)


@pytest.fixture
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Sessão sem `commit`: o teste termina com `rollback` e nada sobra.

    Repositório não faz `commit` (ver `session.py`), então a suíte também não
    precisa — o `flush` de cada escrita é o que a leitura seguinte vê.
    """
    with session_factory() as session:
        yield session
        session.rollback()


@dataclass(frozen=True)
class SqlRepositories:
    """O mesmo feixe de `Fakes`, com os repositórios SQLAlchemy.

    Todos compartilham uma `Session`, como vai acontecer na Fase 4: é uma
    transação por requisição, não uma por repositório.
    """

    clock: FrozenClock
    projects: SqlAlchemyProjectRepository
    initiatives: SqlAlchemyInitiativeRepository
    members: SqlAlchemyMemberRepository
    squads: SqlAlchemySquadRepository
    memberships: SqlAlchemySquadMembershipRepository
    sprints: SqlAlchemySprintRepository
    allocations: SqlAlchemyAllocationRepository
    muted_alerts: SqlAlchemyMutedAlertRepository

    @classmethod
    def build(cls, *, session: Session, clock: FrozenClock) -> Self:
        return cls(
            clock=clock,
            projects=SqlAlchemyProjectRepository(session),
            initiatives=SqlAlchemyInitiativeRepository(session),
            members=SqlAlchemyMemberRepository(session),
            squads=SqlAlchemySquadRepository(session),
            memberships=SqlAlchemySquadMembershipRepository(session),
            sprints=SqlAlchemySprintRepository(session),
            allocations=SqlAlchemyAllocationRepository(session),
            muted_alerts=SqlAlchemyMutedAlertRepository(session),
        )


@pytest.fixture
def clock() -> FrozenClock:
    """02/09/2026, a mesma data da suíte de use case."""
    return FrozenClock(TODAY)


@pytest.fixture(params=["fake", "sqlalchemy"])
def repos(request: pytest.FixtureRequest, clock: FrozenClock) -> Repositories:
    """O feixe de portas, uma vez por implementação.

    `getfixturevalue` em vez de depender de `session` direto: o parâmetro
    `fake` não deve pagar o custo de migrar e copiar um banco que não vai usar.
    """
    if request.param == "fake":
        return Fakes(clock=clock)
    return SqlRepositories.build(
        session=request.getfixturevalue("session"), clock=clock
    )


@pytest.fixture
def world(repos: Repositories) -> World:
    return World(repos=repos)
