"""A volta: o que o writer escreveu, lido de novo (RNF4).

O que importa aqui é a **igualdade das entidades**, e não só a dos arquivos: é
ela que faz a restauração preservar verbatim os UUIDs e o `created_at` do
silenciamento, que é o que o critério de aceite da fase exige.

A outra metade da suíte é o erro: uma pasta errada tem de virar mensagem em
português, não `KeyError` subindo até um 500.
"""

import json
from pathlib import Path

import pytest

from app.adapters.outbound.snapshot.codec import META_FILENAME
from app.adapters.outbound.snapshot.reader import DirectorySnapshotReader
from app.adapters.outbound.snapshot.writer import DirectorySnapshotWriter
from app.domain.errors import InvalidName, InvalidSnapshot, SnapshotNotFound
from app.domain.ports.snapshot import SnapshotBundle


def test_the_bundle_survives_the_round_trip_entity_by_entity(
    writer: DirectorySnapshotWriter,
    reader: DirectorySnapshotReader,
    bundle: SnapshotBundle,
    directory: Path,
) -> None:
    writer.write(bundle)

    assert reader.read(directory) == bundle


def test_the_muted_alert_keeps_the_same_id_and_timestamp(
    writer: DirectorySnapshotWriter,
    reader: DirectorySnapshotReader,
    bundle: SnapshotBundle,
    directory: Path,
) -> None:
    """RNF4, e é o que faz o segundo export dar o mesmo arquivo."""
    writer.write(bundle)

    restored = reader.read(directory).muted_alerts[0]

    assert restored == bundle.muted_alerts[0]
    assert restored.created_at.tzinfo is not None


def test_a_project_without_color_comes_back_without_color(
    writer: DirectorySnapshotWriter,
    reader: DirectorySnapshotReader,
    bundle: SnapshotBundle,
    directory: Path,
) -> None:
    """§6.1: nulo é nulo, e não a cor padrão gravada no lugar."""
    writer.write(bundle)

    restored = {project.name: project for project in reader.read(directory).projects}

    assert restored["Reserva de capacidade"].color is None
    assert restored["CRM"].color is not None


def test_an_empty_snapshot_reads_back_empty(
    writer: DirectorySnapshotWriter,
    reader: DirectorySnapshotReader,
    directory: Path,
) -> None:
    writer.write(SnapshotBundle())

    assert reader.read(directory) == SnapshotBundle()


def test_a_directory_that_does_not_exist_is_a_not_found(
    reader: DirectorySnapshotReader, tmp_path: Path
) -> None:
    with pytest.raises(SnapshotNotFound) as error:
        reader.read(tmp_path / "nao-existe")

    assert "nao-existe" in error.value.message


def test_a_directory_without_the_meta_file_is_not_a_snapshot(
    reader: DirectorySnapshotReader, tmp_path: Path
) -> None:
    """É o que distingue uma pasta de snapshot de uma pasta com JSON dentro."""
    (tmp_path / "projects.json").write_text("[]\n", encoding="utf-8")

    with pytest.raises(SnapshotNotFound):
        reader.read(tmp_path)


def test_a_missing_entity_file_is_a_not_found(
    writer: DirectorySnapshotWriter,
    reader: DirectorySnapshotReader,
    bundle: SnapshotBundle,
    directory: Path,
) -> None:
    """Pasta copiada pela metade: a restauração para antes de apagar nada."""
    writer.write(bundle)
    (directory / "allocations.json").unlink()

    with pytest.raises(SnapshotNotFound) as error:
        reader.read(directory)

    assert "allocations.json" in error.value.message


def test_a_malformed_file_says_which_file_it_is(
    writer: DirectorySnapshotWriter,
    reader: DirectorySnapshotReader,
    bundle: SnapshotBundle,
    directory: Path,
) -> None:
    writer.write(bundle)
    (directory / "members.json").write_text("{isso não é json", encoding="utf-8")

    with pytest.raises(InvalidSnapshot) as error:
        reader.read(directory)

    assert error.value.details["file"] == "members.json"


def test_a_file_that_is_not_a_list_is_refused(
    writer: DirectorySnapshotWriter,
    reader: DirectorySnapshotReader,
    bundle: SnapshotBundle,
    directory: Path,
) -> None:
    writer.write(bundle)
    (directory / "sprints.json").write_text('{"number": 18}\n', encoding="utf-8")

    with pytest.raises(InvalidSnapshot, match="lista JSON"):
        reader.read(directory)


def test_a_missing_field_is_refused_naming_the_file(
    writer: DirectorySnapshotWriter,
    reader: DirectorySnapshotReader,
    bundle: SnapshotBundle,
    directory: Path,
) -> None:
    writer.write(bundle)
    rows = json.loads((directory / "members.json").read_text(encoding="utf-8"))
    del rows[0]["short_name"]
    (directory / "members.json").write_text(json.dumps(rows), encoding="utf-8")

    with pytest.raises(InvalidSnapshot) as error:
        reader.read(directory)

    assert error.value.details["file"] == "members.json"


def test_an_unknown_format_version_is_refused(
    writer: DirectorySnapshotWriter,
    reader: DirectorySnapshotReader,
    bundle: SnapshotBundle,
    directory: Path,
) -> None:
    """Melhor recusar do que montar entidade errada a partir de um snapshot de
    outra época."""
    writer.write(bundle)
    (directory / META_FILENAME).write_text('{"format_version": 99}', encoding="utf-8")

    with pytest.raises(InvalidSnapshot) as error:
        reader.read(directory)

    assert error.value.details["format_version"] == 99


def test_an_invariant_of_the_entity_keeps_its_own_message(
    writer: DirectorySnapshotWriter,
    reader: DirectorySnapshotReader,
    bundle: SnapshotBundle,
    directory: Path,
) -> None:
    """Nome vazio é `InvalidName`, e a mensagem dela é melhor do que qualquer
    coisa que o reader escreveria em volta."""
    writer.write(bundle)
    rows = json.loads((directory / "projects.json").read_text(encoding="utf-8"))
    rows[0]["name"] = "   "
    (directory / "projects.json").write_text(json.dumps(rows), encoding="utf-8")

    with pytest.raises(InvalidName):
        reader.read(directory)
