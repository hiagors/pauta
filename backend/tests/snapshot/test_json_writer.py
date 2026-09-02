"""As regras de formato do §9, uma a uma.

Nenhuma delas é estética: são elas que fazem o roundtrip da Fase 5 dar
arquivos iguais e o diff no Git e no Drive ser legível.
"""

import json
from pathlib import Path

from app.adapters.outbound.snapshot.codec import ENTITY_FILES, META_FILENAME
from app.adapters.outbound.snapshot.json_writer import JsonSnapshotWriter
from app.domain.entities.project import Project
from app.domain.ports.snapshot import SnapshotBundle
from tests.domain.conftest import FrozenClock, uid


def test_every_file_of_the_spec_is_written(
    json_writer: JsonSnapshotWriter, bundle: SnapshotBundle, directory: Path
) -> None:
    written = {path.name for path in json_writer.write(bundle)}

    assert written == {spec.filename for spec in ENTITY_FILES} | {META_FILENAME}
    assert all((directory / name).is_file() for name in written)


def test_the_writer_creates_the_directory_it_needs(
    json_writer: JsonSnapshotWriter, bundle: SnapshotBundle, directory: Path
) -> None:
    """A pasta sincronizada pode não existir numa máquina nova."""
    assert not directory.exists()

    json_writer.write(bundle)

    assert directory.is_dir()


def test_the_keys_are_sorted_and_the_indent_is_two(
    json_writer: JsonSnapshotWriter, bundle: SnapshotBundle, directory: Path
) -> None:
    json_writer.write(bundle)

    text = (directory / "projects.json").read_text(encoding="utf-8")

    assert text.startswith("[\n  {\n")
    first = text.splitlines()[2].strip().split(":")[0]
    assert first == '"color"', "as chaves saem em ordem alfabética"
    assert text.endswith("}\n]\n"), "o arquivo termina com quebra de linha"


def test_the_lists_are_ordered_by_id_not_by_insertion(
    clock: FrozenClock, directory: Path
) -> None:
    """§9. É o que faz o diff mostrar só o que mudou de verdade."""
    later = Project(id=uid(9), name="Depois")
    earlier = Project(id=uid(1), name="Antes")
    JsonSnapshotWriter(directory, clock).write(
        SnapshotBundle(projects=(later, earlier))
    )

    rows = json.loads((directory / "projects.json").read_text(encoding="utf-8"))

    assert [row["name"] for row in rows] == ["Antes", "Depois"]


def test_the_accents_are_not_escaped(
    json_writer: JsonSnapshotWriter, bundle: SnapshotBundle, directory: Path
) -> None:
    """Os nomes deste sistema são em português; `\\u00e7` não é diff legível."""
    json_writer.write(bundle)

    text = (directory / "initiatives.json").read_text(encoding="utf-8")

    assert "Reestruturação V1" in text
    assert "\\u" not in text


def test_only_the_meta_file_carries_a_generation_timestamp(
    json_writer: JsonSnapshotWriter, bundle: SnapshotBundle, directory: Path
) -> None:
    """§9: timestamp em arquivo de entidade muda o arquivo inteiro a cada
    export, sem mudança de dado nenhuma."""
    json_writer.write(bundle)

    meta = json.loads((directory / META_FILENAME).read_text(encoding="utf-8"))

    assert meta["generated_at"] == "2026-09-02T12:00:00+00:00"
    assert meta["format_version"] == 1
    assert meta["counts"]["allocations"] == 3
    for spec in ENTITY_FILES:
        text = (directory / spec.filename).read_text(encoding="utf-8")
        assert "generated_at" not in text, spec.filename


def test_two_exports_of_the_same_data_produce_the_same_entity_files(
    json_writer: JsonSnapshotWriter, bundle: SnapshotBundle, directory: Path
) -> None:
    json_writer.write(bundle)
    before = {
        spec.filename: (directory / spec.filename).read_bytes() for spec in ENTITY_FILES
    }

    json_writer.write(bundle)

    assert {
        spec.filename: (directory / spec.filename).read_bytes() for spec in ENTITY_FILES
    } == before


def test_an_empty_database_is_a_valid_snapshot(
    json_writer: JsonSnapshotWriter, directory: Path
) -> None:
    """Não existe `seed` (RNF5): a primeira exportação de uma máquina nova é
    de um banco vazio, e ela tem de funcionar."""
    json_writer.write(SnapshotBundle())

    assert (directory / "projects.json").read_text(encoding="utf-8") == "[]\n"
