"""A CLI da Fase 5 (§4.3, §9).

O que só a CLI tem, e por isso é testado aqui: ela lê a configuração do
**ambiente** (é assim que o `mise run snapshot` a chama), abre e fecha a
transação sozinha, pergunta antes de apagar e traduz erro de domínio em
mensagem com código de saída 1 — em vez de traceback.

O formato dos arquivos é `tests/snapshot/`; o comportamento dos use cases é
`tests/application/`. Aqui é a borda.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.adapters.inbound.cli.main import cli
from app.adapters.outbound.persistence.repositories import SqlAlchemySnapshotStore
from app.adapters.outbound.persistence.session import make_engine, make_session_factory
from app.adapters.outbound.snapshot.codec import ENTITY_FILES
from app.adapters.outbound.snapshot.writer import DirectorySnapshotWriter
from app.adapters.outbound.system_clock import SystemClock
from app.config.settings import get_settings
from app.domain.ports.snapshot import SnapshotBundle
from tests.persistence.conftest import database_url, upgrade
from tests.snapshot.bundles import full_bundle


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def database(tmp_path: Path) -> Path:
    """Um banco migrado e vazio, como o de uma máquina nova (RNF2, RNF5)."""
    path = tmp_path / "pauta.sqlite"
    upgrade(path)
    return path


@pytest.fixture
def snapshots(tmp_path: Path) -> Path:
    return tmp_path / "snapshots"


@pytest.fixture(autouse=True)
def environment(
    database: Path, snapshots: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """As duas variáveis do `mise.toml`, e o cache do `get_settings` limpo.

    O cache é por processo: sem limpar, o primeiro teste fixaria a
    configuração de todos os outros.
    """
    monkeypatch.setenv("DATABASE_URL", database_url(database))
    monkeypatch.setenv("SNAPSHOT_DIR", str(snapshots))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _stored(database: Path) -> SnapshotBundle:
    """O que está no banco, lido fora da CLI."""
    engine = make_engine(database_url(database))
    try:
        with make_session_factory(engine)() as session:
            return SqlAlchemySnapshotStore(session).dump()
    finally:
        engine.dispose()


def _write_snapshot(directory: Path) -> Path:
    DirectorySnapshotWriter(directory=directory, clock=SystemClock()).write(
        full_bundle()
    )
    return directory


# --------------------------------------------------------------------------- #
# export
# --------------------------------------------------------------------------- #


def test_the_export_writes_the_snapshot_dir_of_the_environment(
    runner: CliRunner, snapshots: Path
) -> None:
    result = runner.invoke(cli, ["snapshot", "export"])

    assert result.exit_code == 0, result.output
    assert (snapshots / "projects.json").is_file()
    assert (snapshots / "plan-grid.md").is_file()


def test_the_export_lists_what_it_generated(runner: CliRunner, snapshots: Path) -> None:
    """`mise run snapshot` é rodado à mão: dizer só "pronto" não deixa ninguém
    conferir onde o arquivo foi."""
    result = runner.invoke(cli, ["snapshot", "export"])

    assert "0 registros exportados" in result.output
    assert str(snapshots / "meta.json") in result.output
    assert "projetos" in result.output


def test_the_path_option_exports_somewhere_else(
    runner: CliRunner, snapshots: Path, tmp_path: Path
) -> None:
    """Uma cópia sem mexer na pasta sincronizada."""
    other = tmp_path / "copia"

    result = runner.invoke(cli, ["snapshot", "export", "--path", str(other)])

    assert result.exit_code == 0, result.output
    assert (other / "projects.json").is_file()
    assert not snapshots.exists()


# --------------------------------------------------------------------------- #
# import
# --------------------------------------------------------------------------- #


def test_the_import_restores_the_database(
    runner: CliRunner, database: Path, tmp_path: Path
) -> None:
    source = _write_snapshot(tmp_path / "origem")

    result = runner.invoke(cli, ["snapshot", "import", str(source), "--yes"])

    assert result.exit_code == 0, result.output
    assert _stored(database) == full_bundle()
    assert "16 registros importados" in result.output


def test_the_import_asks_before_erasing(
    runner: CliRunner, database: Path, tmp_path: Path
) -> None:
    source = _write_snapshot(tmp_path / "origem")

    result = runner.invoke(cli, ["snapshot", "import", str(source)], input="n\n")

    assert result.exit_code == 1
    assert "apaga todos os dados" in result.output
    assert _stored(database) == SnapshotBundle(), "nada foi importado"


def test_answering_yes_to_the_question_restores(
    runner: CliRunner, database: Path, tmp_path: Path
) -> None:
    source = _write_snapshot(tmp_path / "origem")

    result = runner.invoke(cli, ["snapshot", "import", str(source)], input="s\ny\n")

    assert result.exit_code == 0, result.output
    assert _stored(database).projects == full_bundle().projects


def test_a_path_without_a_snapshot_is_a_message_not_a_traceback(
    runner: CliRunner, tmp_path: Path
) -> None:
    result = runner.invoke(
        cli, ["snapshot", "import", str(tmp_path / "nao-existe"), "--yes"]
    )

    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "Não há snapshot em" in result.output


def test_a_broken_snapshot_leaves_the_database_untouched(
    runner: CliRunner, database: Path, tmp_path: Path
) -> None:
    """A transação é do comando: um snapshot que não fecha não deixa meio
    banco (RNF4)."""
    source = _write_snapshot(tmp_path / "origem")
    (source / "projects.json").write_text("[]\n", encoding="utf-8")

    result = runner.invoke(cli, ["snapshot", "import", str(source), "--yes"])

    assert result.exit_code == 1
    assert "Snapshot inválido" in result.output
    assert _stored(database) == SnapshotBundle()


# --------------------------------------------------------------------------- #
# O critério de aceite, pela CLI
# --------------------------------------------------------------------------- #


def test_import_then_export_reproduces_the_entity_files(
    runner: CliRunner, snapshots: Path, tmp_path: Path
) -> None:
    """O roundtrip da fase, pelo caminho que uma pessoa digita.

    `meta.json` fica fora da comparação: é o único arquivo com timestamp de
    geração (§9), e aqui o relógio é o do sistema.
    """
    source = _write_snapshot(tmp_path / "origem")
    originals = {
        spec.filename: (source / spec.filename).read_bytes() for spec in ENTITY_FILES
    }

    assert runner.invoke(cli, ["snapshot", "import", str(source), "-y"]).exit_code == 0
    assert runner.invoke(cli, ["snapshot", "export"]).exit_code == 0

    assert {
        spec.filename: (snapshots / spec.filename).read_bytes() for spec in ENTITY_FILES
    } == originals
    assert (snapshots / "plan-sprint-18.md").read_bytes() == (
        source / "plan-sprint-18.md"
    ).read_bytes()
