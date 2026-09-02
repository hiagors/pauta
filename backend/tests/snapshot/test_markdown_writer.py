"""Os dois arquivos que uma pessoa abre no Drive (§9).

São derivados: nada aqui é fonte da verdade. O que a suíte cobra é que eles
digam a verdade — quem está em quê, na sprint certa — e que sobrevivam aos
casos que quebram tabela: nome com `|`, sprint sem alocação, banco vazio.
"""

from pathlib import Path

from app.adapters.outbound.snapshot.markdown_writer import MarkdownSnapshotWriter
from app.domain.ports.snapshot import SnapshotBundle


def test_one_file_per_sprint_plus_the_grid(
    markdown_writer: MarkdownSnapshotWriter, bundle: SnapshotBundle
) -> None:
    written = {path.name for path in markdown_writer.write(bundle)}

    assert written == {"plan-sprint-18.md", "plan-sprint-19.md", "plan-grid.md"}


def test_the_sprint_file_says_who_is_on_what(
    markdown_writer: MarkdownSnapshotWriter, bundle: SnapshotBundle, directory: Path
) -> None:
    markdown_writer.write(bundle)

    text = (directory / "plan-sprint-18.md").read_text(encoding="utf-8")

    assert text.startswith("# Sprint 18 — 31/08/2026 a 11/09/2026\n")
    assert "| CRM | Reestruturação V1 | IN_PROGRESS | Dados-A |" in text
    assert "| Dados-A | Bianca |" in text, "a composição da sprint (§6.5)"
    assert "Suporte" not in text, "a alocação da Thalita é na 19"


def test_a_member_allocated_directly_appears_by_the_short_name(
    markdown_writer: MarkdownSnapshotWriter, bundle: SnapshotBundle, directory: Path
) -> None:
    """§6.7: o responsável pode ser um membro, sem squad no meio."""
    markdown_writer.write(bundle)

    text = (directory / "plan-sprint-19.md").read_text(encoding="utf-8")

    assert (
        "| Reserva de capacidade | Suporte e imprevistos | BACKLOG | Thalita |" in text
    )


def test_a_pipe_in_a_name_does_not_break_the_table(
    markdown_writer: MarkdownSnapshotWriter, bundle: SnapshotBundle, directory: Path
) -> None:
    markdown_writer.write(bundle)

    grid = (directory / "plan-grid.md").read_text(encoding="utf-8")

    assert "\\|" not in grid, "o pipe do exemplo está na descrição, não no nome"
    for line in grid.splitlines():
        if line.startswith("|"):
            assert line.count("|") >= 3


def test_the_grid_has_one_column_per_sprint_and_the_assignee_in_the_cell(
    markdown_writer: MarkdownSnapshotWriter, bundle: SnapshotBundle, directory: Path
) -> None:
    markdown_writer.write(bundle)

    text = (directory / "plan-grid.md").read_text(encoding="utf-8")

    assert "| Projeto | Iniciativa | S18 | S19 |" in text
    assert "| CRM | Reestruturação V1 | Dados-A | Dados-A |" in text
    assert "| Reserva de capacidade | Suporte e imprevistos |  | Thalita |" in text
    assert "| 18 | 31/08/2026 | 11/09/2026 |" in text


def test_an_initiative_without_allocation_is_not_a_row_of_the_grid(
    markdown_writer: MarkdownSnapshotWriter, bundle: SnapshotBundle, directory: Path
) -> None:
    """A grade é de alocação; o que não foi alocado está no backlog (§8)."""
    without = SnapshotBundle(
        projects=bundle.projects,
        initiatives=bundle.initiatives,
        members=bundle.members,
        squads=bundle.squads,
        sprints=bundle.sprints,
    )
    markdown_writer.write(without)

    text = (directory / "plan-grid.md").read_text(encoding="utf-8")

    assert "Nenhuma alocação registrada." in text
    assert "Reestruturação" not in text


def test_a_sprint_with_nothing_in_it_says_so(
    markdown_writer: MarkdownSnapshotWriter, bundle: SnapshotBundle, directory: Path
) -> None:
    empty = SnapshotBundle(sprints=bundle.sprints)
    markdown_writer.write(empty)

    text = (directory / "plan-sprint-18.md").read_text(encoding="utf-8")

    assert "Nenhuma alocação nesta sprint." in text
    assert "Nenhuma squad com composição nesta sprint." in text


def test_an_empty_database_still_produces_the_grid(
    markdown_writer: MarkdownSnapshotWriter, directory: Path
) -> None:
    written = markdown_writer.write(SnapshotBundle())

    assert [path.name for path in written] == ["plan-grid.md"]
    assert "Nenhuma sprint cadastrada." in (directory / "plan-grid.md").read_text(
        encoding="utf-8"
    )


def test_the_plan_of_a_sprint_that_left_the_snapshot_is_removed(
    markdown_writer: MarkdownSnapshotWriter, bundle: SnapshotBundle, directory: Path
) -> None:
    """A pasta é sincronizada: um `plan-sprint-19.md` órfão de uma restauração
    anterior seria lido como plano vigente."""
    markdown_writer.write(bundle)
    assert (directory / "plan-sprint-19.md").is_file()

    markdown_writer.write(SnapshotBundle(sprints=(bundle.sprints[0],)))

    assert (directory / "plan-sprint-18.md").is_file()
    assert not (directory / "plan-sprint-19.md").exists()


def test_an_assignee_without_a_name_does_not_break_the_export(
    markdown_writer: MarkdownSnapshotWriter, bundle: SnapshotBundle, directory: Path
) -> None:
    """Snapshot incoerente aparece como tal, e não derruba o export.

    O import recusa esse estado (`ensure_closed`) e o banco tem chave
    estrangeira, então isto só chega aqui vindo de um arquivo editado à mão —
    e nesse caso é melhor gerar o plano com a lacuna à vista.
    """
    without_squads = SnapshotBundle(
        projects=bundle.projects,
        initiatives=bundle.initiatives,
        sprints=bundle.sprints,
        allocations=bundle.allocations,
    )
    markdown_writer.write(without_squads)

    text = (directory / "plan-sprint-18.md").read_text(encoding="utf-8")

    assert "(desconhecido " in text
