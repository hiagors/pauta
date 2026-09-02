"""Schemas de snapshot (§8, §9).

`path` viaja como string e chega como `Path`: o Pydantic converte, e o OpenAPI
publica `string` com formato `path` — o que o front tipa é uma string, como
tem de ser.

`mode` tem um valor só (`replace`, RNF4). Publicá-lo como enum de um membro é
deliberado: o corpo do pedido diz por escrito que a operação apaga tudo, e o
dia em que houver um segundo modo o contrato já tem onde colocá-lo.
"""

from pathlib import Path

from app.adapters.inbound.http.schemas.common import InputModel, OutputModel
from app.application.dto.snapshots import ImportSnapshotInput, SnapshotMode


class SnapshotCountsOut(OutputModel):
    """Quantas linhas o snapshot carrega, por entidade."""

    projects: int
    initiatives: int
    members: int
    squads: int
    squad_memberships: int
    sprints: int
    allocations: int
    muted_alerts: int


class SnapshotExportOut(OutputModel):
    """§8: o export devolve os caminhos gerados."""

    paths: list[Path]
    counts: SnapshotCountsOut


class SnapshotImportIn(InputModel):
    path: Path
    mode: SnapshotMode = SnapshotMode.REPLACE

    def to_input(self) -> ImportSnapshotInput:
        return ImportSnapshotInput(path=self.path, mode=self.mode)


class SnapshotImportOut(OutputModel):
    path: Path
    mode: SnapshotMode
    counts: SnapshotCountsOut
