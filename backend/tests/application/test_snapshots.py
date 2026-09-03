"""Os use cases de snapshot, sem banco e sem arquivo (Fase 2 vale aqui também).

O writer e o reader são fakes que guardam o bundle na memória: o que estes
testes cobram é o que o use case decide — ler tudo, checar o fechamento,
substituir — e não o formato JSON, que é `tests/snapshot/`.

Os use cases são instanciados à mão, e não por `fakes.use_case()`, porque
`writer` e `reader` não são portas do feixe: eles variam por teste, e um campo
a mais em `Fakes` obrigaria a suíte de contrato a carregar um writer que ela
não usa.
"""

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from app.application.dto.snapshots import ImportSnapshotInput, SnapshotMode
from app.application.use_cases.snapshots.export import ExportSnapshot
from app.application.use_cases.snapshots.import_ import ImportSnapshot
from app.domain.entities.project import Project
from app.domain.errors import InvalidSnapshot
from app.domain.ports.snapshot import SnapshotBundle
from tests.application.conftest import Fakes, World
from tests.domain.conftest import uid
from tests.snapshot.bundles import full_bundle

SNAPSHOT_DIR = Path("/tmp/pauta-snapshot-de-teste")


@dataclass
class RecordingWriter:
    """`SnapshotWriter` que só anota o que recebeu."""

    written: list[SnapshotBundle] = field(default_factory=list)

    def write(self, bundle: SnapshotBundle) -> tuple[Path, ...]:
        self.written.append(bundle)
        return (SNAPSHOT_DIR / "projects.json", SNAPSHOT_DIR / "meta.json")


@dataclass
class StubReader:
    """`SnapshotReader` que devolve o bundle combinado, sem tocar em disco."""

    bundle: SnapshotBundle
    read_from: list[Path] = field(default_factory=list)

    def read(self, path: Path) -> SnapshotBundle:
        self.read_from.append(path)
        return self.bundle


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #


def test_the_export_hands_the_whole_database_to_the_writer(
    fakes: Fakes, world: World
) -> None:
    world.sprints(18, 19)
    project = world.project("Aurora")
    initiative = world.initiative(project, "Catálogo")
    squad = world.squad("Alfa")
    world.allocate(initiative, 18, 19, squad=squad)
    writer = RecordingWriter()

    result = ExportSnapshot(store=fakes.store, writer=writer).execute()

    (written,) = writer.written
    assert written.projects == (project,)
    assert written.initiatives == (initiative,)
    assert len(written.allocations) == 2
    assert result.counts.allocations == 2
    assert result.counts.total == 7, (
        "2 sprints, 1 projeto, 1 iniciativa, 1 squad, 2 alocações"
    )


def test_the_export_returns_the_paths_the_writer_generated(fakes: Fakes) -> None:
    """§8: o export devolve os caminhos gerados."""
    result = ExportSnapshot(store=fakes.store, writer=RecordingWriter()).execute()

    assert result.paths == (
        SNAPSHOT_DIR / "projects.json",
        SNAPSHOT_DIR / "meta.json",
    )


def test_exporting_an_empty_database_is_not_an_error(fakes: Fakes) -> None:
    """Não existe `seed` (RNF5): banco vazio é o estado inicial de toda
    máquina nova."""
    result = ExportSnapshot(store=fakes.store, writer=RecordingWriter()).execute()

    assert result.counts.total == 0


# --------------------------------------------------------------------------- #
# Import
# --------------------------------------------------------------------------- #


def test_the_import_replaces_what_was_there(fakes: Fakes, world: World) -> None:
    world.project("Projeto que vai embora")
    bundle = full_bundle()

    result = ImportSnapshot(store=fakes.store, reader=StubReader(bundle)).execute(
        ImportSnapshotInput(path=SNAPSHOT_DIR)
    )

    assert result.mode is SnapshotMode.REPLACE
    assert result.counts.projects == 2
    assert [project.name for project in fakes.projects.list_all()] == [
        "Aurora",
        "Reserva de capacidade",
    ]


def test_the_import_preserves_the_uuids_verbatim(fakes: Fakes) -> None:
    """RNF4, e é o que faz o roundtrip da fase produzir arquivos iguais."""
    bundle = full_bundle()

    ImportSnapshot(store=fakes.store, reader=StubReader(bundle)).execute(
        ImportSnapshotInput(path=SNAPSHOT_DIR)
    )

    restored = fakes.muted_alerts.get(bundle.muted_alerts[0].id)
    assert restored == bundle.muted_alerts[0]


def test_the_import_reads_the_path_it_was_given(fakes: Fakes) -> None:
    reader = StubReader(SnapshotBundle())

    ImportSnapshot(store=fakes.store, reader=reader).execute(
        ImportSnapshotInput(path=SNAPSHOT_DIR)
    )

    assert reader.read_from == [SNAPSHOT_DIR]


def test_importing_an_empty_snapshot_empties_the_database(
    fakes: Fakes, world: World
) -> None:
    """`replace` é `replace`: quem restaura um snapshot de banco vazio está
    pedindo um banco vazio (RNF4)."""
    world.project("Aurora")

    ImportSnapshot(store=fakes.store, reader=StubReader(SnapshotBundle())).execute(
        ImportSnapshotInput(path=SNAPSHOT_DIR)
    )

    assert fakes.projects.list_all() == []


def test_a_reference_that_does_not_close_is_refused_before_anything_is_erased(
    fakes: Fakes, world: World
) -> None:
    """Uma pasta copiada pela metade não pode apagar o banco.

    O `initiatives.json` aponta para um projeto que não está em
    `projects.json`: a recusa vem antes do `replace`, e o que estava gravado
    continua lá.
    """
    survivor = world.project("Continua aqui")
    orphan = SnapshotBundle(
        initiatives=(full_bundle().initiatives[0],),
    )

    with pytest.raises(InvalidSnapshot) as error:
        ImportSnapshot(store=fakes.store, reader=StubReader(orphan)).execute(
            ImportSnapshotInput(path=SNAPSHOT_DIR)
        )

    assert error.value.details["field"] == "project_id"
    assert fakes.projects.list_all() == [survivor]


def test_an_allocation_pointing_to_a_sprint_outside_the_snapshot_is_refused(
    fakes: Fakes,
) -> None:
    complete = full_bundle()
    without_sprints = SnapshotBundle(
        projects=complete.projects,
        initiatives=complete.initiatives,
        members=complete.members,
        squads=complete.squads,
        allocations=complete.allocations,
    )

    with pytest.raises(InvalidSnapshot) as error:
        ImportSnapshot(store=fakes.store, reader=StubReader(without_sprints)).execute(
            ImportSnapshotInput(path=SNAPSHOT_DIR)
        )

    assert error.value.details["file"] == "allocations.json"
    assert error.value.details["field"] == "sprint_id"


def test_a_repeated_id_is_refused(fakes: Fakes) -> None:
    """Dois ids iguais no mesmo arquivo bateriam na chave primária no meio do
    `INSERT`; aqui o pedido é recusado antes."""
    repeated = SnapshotBundle(
        projects=(Project(id=uid(1), name="Um"), Project(id=uid(1), name="Outro"))
    )

    with pytest.raises(InvalidSnapshot, match="mais de uma vez"):
        ImportSnapshot(store=fakes.store, reader=StubReader(repeated)).execute(
            ImportSnapshotInput(path=SNAPSHOT_DIR)
        )


def test_a_squad_representative_outside_the_snapshot_is_refused(
    fakes: Fakes,
) -> None:
    """RN-S1: o representante é um membro, e ele tem de vir no snapshot."""
    complete = full_bundle()
    without_members = SnapshotBundle(squads=complete.squads)

    with pytest.raises(InvalidSnapshot) as error:
        ImportSnapshot(store=fakes.store, reader=StubReader(without_members)).execute(
            ImportSnapshotInput(path=SNAPSHOT_DIR)
        )

    assert error.value.details["field"] == "representative_member_id"
