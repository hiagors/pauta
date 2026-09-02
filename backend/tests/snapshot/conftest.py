"""Apoio da suíte de snapshot (Fase 5).

As fixtures de banco vêm de `tests/persistence/conftest.py`, importadas em vez
de copiadas: o schema desta suíte também tem de sair das migrations (RNF2), e
duas cópias da mesma montagem divergiriam na primeira migration nova.

O `clock` é congelado em 02/09/2026, como nas outras suítes, porque o
`generated_at` do `meta.json` sai dele.
"""

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.outbound.persistence.repositories import SqlAlchemySnapshotStore
from app.adapters.outbound.snapshot.json_writer import JsonSnapshotWriter
from app.adapters.outbound.snapshot.markdown_writer import MarkdownSnapshotWriter
from app.adapters.outbound.snapshot.reader import DirectorySnapshotReader
from app.adapters.outbound.snapshot.writer import DirectorySnapshotWriter
from app.domain.ports.snapshot import SnapshotBundle
from tests.domain.conftest import FrozenClock
from tests.persistence.conftest import (  # noqa: F401 - fixtures reexportadas
    engine,
    migrated_database,
    session_factory,
    sqlite_path,
)
from tests.snapshot.bundles import full_bundle

#: 02/09/2026, a mesma data das outras suítes.
TODAY = date(2026, 9, 2)


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(TODAY)


@pytest.fixture
def bundle() -> SnapshotBundle:
    return full_bundle()


@pytest.fixture
def directory(tmp_path: Path) -> Path:
    """Uma pasta de snapshot por teste. O writer a cria se não existir."""
    return tmp_path / "snapshots"


@pytest.fixture
def writer(directory: Path, clock: FrozenClock) -> DirectorySnapshotWriter:
    """A porta inteira: JSON e Markdown, como o §9 pede."""
    return DirectorySnapshotWriter(directory=directory, clock=clock)


@pytest.fixture
def json_writer(directory: Path, clock: FrozenClock) -> JsonSnapshotWriter:
    return JsonSnapshotWriter(directory, clock)


@pytest.fixture
def markdown_writer(directory: Path) -> MarkdownSnapshotWriter:
    return MarkdownSnapshotWriter(directory)


@pytest.fixture
def reader() -> DirectorySnapshotReader:
    return DirectorySnapshotReader()


@pytest.fixture
def db_session(request: pytest.FixtureRequest) -> Iterator[Session]:
    """Uma sessão sobre o SQLite migrado.

    Chama-se `db_session`, e não `session`, por dois motivos: aqui há testes
    que precisam de **duas** sessões — uma que grava e outra que confere depois
    do `commit` — e um parâmetro com o nome de uma fixture importada esconderia
    o import para o linter. Por isso a fábrica vem por `getfixturevalue`, como
    o `repos` de `tests/persistence/` já faz.
    """
    factory: sessionmaker[Session] = request.getfixturevalue("session_factory")
    with factory() as session:
        yield session
        session.rollback()


@pytest.fixture
def store(db_session: Session) -> SqlAlchemySnapshotStore:
    return SqlAlchemySnapshotStore(db_session)
