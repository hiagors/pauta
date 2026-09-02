"""`pauta snapshot export` e `pauta snapshot import` (§9, RNF4).

O export é o comando do dia a dia (`mise run snapshot`): lê o banco e escreve a
pasta sincronizada. O import é o de emergência: apaga o banco e o recria a
partir de uma pasta de snapshot.

Duas coisas que o comando faz e a borda HTTP não:

- **pergunta antes de apagar.** O `--yes` existe para script; à mão, a
  confirmação é o que separa "restaurar" de "perder tudo".
- **traduz `DomainError` em mensagem e código de saída 1.** Um traceback de
  `SnapshotNotFound` não diz a quem digitou o caminho errado o que ele digitou
  errado.

A importação **não** dispara export automático (RNF3): quem acabou de restaurar
uma pasta não quer que o sistema a reescreva antes de ele olhar o resultado.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer

from app.adapters.inbound.cli.deps import ports
from app.application.dto.snapshots import (
    ImportSnapshotInput,
    SnapshotCountsView,
    SnapshotMode,
)
from app.application.use_cases.snapshots.export import ExportSnapshot
from app.application.use_cases.snapshots.import_ import ImportSnapshot
from app.domain.errors import DomainError

cli = typer.Typer(
    help="Exporta e restaura o snapshot em JSON e Markdown.",
    no_args_is_help=True,
)


@cli.command("export")
def export(
    path: Annotated[
        Path | None,
        typer.Option(
            "--path",
            help="Pasta de destino. Sem isso, a do SNAPSHOT_DIR.",
        ),
    ] = None,
) -> None:
    """Exporta o banco para a pasta sincronizada."""
    with _reported(), ports(snapshot_dir=path) as wiring:
        result = ExportSnapshot(store=wiring.store, writer=wiring.writer).execute()
    typer.echo(f"{result.counts.total} registros exportados:")
    for written in result.paths:
        typer.echo(f"  {written}")
    _echo_counts(result.counts)


@cli.command("import")
def import_snapshot(
    path: Annotated[Path, typer.Argument(help="Pasta com os arquivos do snapshot.")],
    mode: Annotated[
        SnapshotMode,
        typer.Option(help="Só existe replace: apaga tudo e recria (RNF4)."),
    ] = SnapshotMode.REPLACE,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Não pergunta antes de apagar."),
    ] = False,
) -> None:
    """Restaura o banco a partir de um snapshot. Destrutivo."""
    if not yes:
        typer.confirm(
            f"Isto apaga todos os dados do banco e recria a partir de {path}. "
            "Continuar?",
            abort=True,
        )
    with _reported(), ports() as wiring:
        result = ImportSnapshot(store=wiring.store, reader=wiring.reader).execute(
            ImportSnapshotInput(path=path, mode=mode)
        )
    typer.echo(f"{result.counts.total} registros importados de {result.path}:")
    _echo_counts(result.counts)


def _echo_counts(counts: SnapshotCountsView) -> None:
    for field, label in (
        ("projects", "projetos"),
        ("initiatives", "iniciativas"),
        ("members", "membros"),
        ("squads", "squads"),
        ("squad_memberships", "composições de squad"),
        ("sprints", "sprints"),
        ("allocations", "alocações"),
        ("muted_alerts", "alertas silenciados"),
    ):
        typer.echo(f"  {getattr(counts, field):>5}  {label}")


@contextmanager
def _reported() -> Iterator[None]:
    """Erro de domínio é mensagem, não traceback."""
    try:
        yield
    except DomainError as error:
        typer.secho(f"Erro: {error.message}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error
