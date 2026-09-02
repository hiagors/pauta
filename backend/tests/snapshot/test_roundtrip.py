"""O critério de aceite da Fase 5.

Duas frases, do §13:

1. "Roundtrip export → import → export produz arquivos idênticos."
2. "Um banco apagado é reconstruído do snapshot."

As duas rodam contra o SQLite de verdade, com o schema criado pelas migrations
(RNF2): é o único jeito de "reconstruído" significar alguma coisa.

Sobre a primeira: com o `Clock` congelado, **todos** os arquivos saem iguais,
`meta.json` inclusive. Em produção só o `meta.json` difere entre dois exports,
pelo `generated_at` — e é justamente para isolar essa diferença num arquivo só
que o §9 proíbe timestamp nos arquivos de entidade.
"""

from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.outbound.persistence.repositories import SqlAlchemySnapshotStore
from app.adapters.outbound.persistence.session import make_engine, make_session_factory
from app.adapters.outbound.snapshot.reader import DirectorySnapshotReader
from app.adapters.outbound.snapshot.writer import DirectorySnapshotWriter
from app.application.dto.snapshots import ImportSnapshotInput
from app.application.use_cases.snapshots.export import ExportSnapshot
from app.application.use_cases.snapshots.import_ import ImportSnapshot
from app.domain.entities.project import Project
from app.domain.ports.snapshot import SnapshotBundle
from tests.domain.conftest import uid
from tests.persistence.conftest import database_url, upgrade
from tests.snapshot.bundles import full_bundle


def _files(directory: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in sorted(directory.iterdir())}


def test_export_import_export_produces_identical_files(
    store: SqlAlchemySnapshotStore,
    db_session: Session,
    writer: DirectorySnapshotWriter,
    reader: DirectorySnapshotReader,
    bundle: SnapshotBundle,
    directory: Path,
) -> None:
    store.replace(bundle)
    db_session.commit()

    ExportSnapshot(store=store, writer=writer).execute()
    first = _files(directory)

    ImportSnapshot(store=store, reader=reader).execute(
        ImportSnapshotInput(path=directory)
    )
    db_session.commit()
    ExportSnapshot(store=store, writer=writer).execute()

    assert _files(directory) == first


def test_a_deleted_database_is_rebuilt_from_the_snapshot(
    store: SqlAlchemySnapshotStore,
    db_session: Session,
    writer: DirectorySnapshotWriter,
    reader: DirectorySnapshotReader,
    bundle: SnapshotBundle,
    directory: Path,
    tmp_path: Path,
) -> None:
    """O caso da RNF4: outra máquina, ou o banco perdido.

    O banco novo é criado pelas migrations e está vazio — não existe `seed`
    (RNF5). Depois da importação ele tem de conter exatamente o que o snapshot
    dizia, com os mesmos UUIDs.
    """
    store.replace(bundle)
    db_session.commit()
    ExportSnapshot(store=store, writer=writer).execute()
    exported = _files(directory)

    rebuilt = tmp_path / "outra-maquina.sqlite"
    upgrade(rebuilt)
    engine = make_engine(database_url(rebuilt))
    try:
        factory = make_session_factory(engine)
        with factory() as fresh:
            fresh_store = SqlAlchemySnapshotStore(fresh)
            assert fresh_store.dump() == SnapshotBundle(), "o banco novo é vazio"
            ImportSnapshot(store=fresh_store, reader=reader).execute(
                ImportSnapshotInput(path=directory)
            )
            fresh.commit()
        with factory() as checking:
            restored = SqlAlchemySnapshotStore(checking)
            assert restored.dump() == bundle
            ExportSnapshot(store=restored, writer=writer).execute()
    finally:
        engine.dispose()

    assert _files(directory) == exported


def test_an_import_that_fails_leaves_the_database_as_it_was(
    store: SqlAlchemySnapshotStore, db_session: Session, bundle: SnapshotBundle
) -> None:
    """RNF4: "dentro de uma transação única".

    Nome de projeto é único (§6.1), e a checagem de fechamento do use case não
    olha nome — então este bundle passa por ela e bate na constraint. O que
    tem de sobrar é o banco de antes, e não meio banco.
    """
    store.replace(bundle)
    db_session.commit()

    duplicated = SnapshotBundle(
        projects=(
            Project(id=uid(71), name="Repetido"),
            Project(id=uid(72), name="Repetido"),
        )
    )
    with pytest.raises(IntegrityError):
        store.replace(duplicated)
    db_session.rollback()

    assert store.dump() == bundle


def test_the_export_is_read_only(
    store: SqlAlchemySnapshotStore,
    db_session: Session,
    writer: DirectorySnapshotWriter,
    bundle: SnapshotBundle,
) -> None:
    """Exportar não muda dado: é o que permite o debounce rodar em qualquer
    momento, numa sessão própria, sem coordenar com ninguém (RNF3)."""
    store.replace(bundle)
    db_session.commit()

    ExportSnapshot(store=store, writer=writer).execute()

    assert store.dump() == full_bundle()
