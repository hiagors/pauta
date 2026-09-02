"""DTOs do export e do import de snapshot (§9, §8 `/snapshots`).

`SnapshotMode` tem **um** valor de propósito: a RNF4 diz "modo `replace`
apenas". Merge exige resolução de conflito, que é escopo de outra versão. O
campo existe no contrato porque o §8 o documenta no corpo do pedido — e porque
é ele que faz o pedido dizer, por escrito, que a operação apaga tudo.
"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Self

from app.domain.ports.snapshot import SnapshotBundle


class SnapshotMode(StrEnum):
    """Minúsculo porque viaja no JSON (`mode: "replace"`, §8)."""

    REPLACE = "replace"


@dataclass(frozen=True)
class ImportSnapshotInput:
    path: Path
    mode: SnapshotMode = SnapshotMode.REPLACE


@dataclass(frozen=True)
class SnapshotCountsView:
    """Quantas linhas o snapshot carrega, por entidade.

    É o que o comando da CLI imprime e o que a UI mostra depois de restaurar:
    "importado" sem número nenhum não deixa ninguém conferir se veio o banco
    inteiro ou uma pasta pela metade.
    """

    projects: int
    initiatives: int
    members: int
    squads: int
    squad_memberships: int
    sprints: int
    allocations: int
    muted_alerts: int

    @classmethod
    def of(cls, bundle: SnapshotBundle) -> Self:
        return cls(
            projects=len(bundle.projects),
            initiatives=len(bundle.initiatives),
            members=len(bundle.members),
            squads=len(bundle.squads),
            squad_memberships=len(bundle.squad_memberships),
            sprints=len(bundle.sprints),
            allocations=len(bundle.allocations),
            muted_alerts=len(bundle.muted_alerts),
        )

    @property
    def total(self) -> int:
        return (
            self.projects
            + self.initiatives
            + self.members
            + self.squads
            + self.squad_memberships
            + self.sprints
            + self.allocations
            + self.muted_alerts
        )


@dataclass(frozen=True)
class ExportSnapshotResultView:
    """§8: o export devolve os caminhos gerados."""

    paths: tuple[Path, ...]
    counts: SnapshotCountsView


@dataclass(frozen=True)
class ImportSnapshotResultView:
    path: Path
    mode: SnapshotMode
    counts: SnapshotCountsView
