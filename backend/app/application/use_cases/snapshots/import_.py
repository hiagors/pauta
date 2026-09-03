"""Importar o snapshot (`POST /snapshots/import`, `pauta snapshot import`).

O nome do módulo termina em `_` porque `import` é palavra reservada: um
`import.py` não pode ser importado por `from ... import import`. A classe é
`ImportSnapshot`, e é ela que aparece no wiring.

Modo `replace` apenas (RNF4): apaga e recria, dentro da transação que o adapter
de entrada abriu. Sem merge — merge exige resolução de conflito, que é escopo
de outra versão.

A checagem de fechamento antes de gravar existe por causa do que a operação é:
ela apaga o banco. Uma pasta copiada pela metade — `allocations.json` novo,
`initiatives.json` velho — falharia no meio do `INSERT`, e o que salvaria o
dado seria o `rollback` do adapter. Preferimos recusar antes de apagar, com uma
mensagem que diz qual referência não fecha, do que depender do rollback para
não perder o banco. As demais invariantes continuam sendo das constraints e das
entidades: nome duplicado, data invertida e responsável ambíguo já são recusados
na leitura ou no `INSERT`.
"""

from collections.abc import Collection
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.application.dto.snapshots import (
    ImportSnapshotInput,
    ImportSnapshotResultView,
    SnapshotCountsView,
)
from app.application.ports.snapshot import SnapshotReader
from app.domain.errors import InvalidSnapshot
from app.domain.ports.snapshot import SnapshotBundle, SnapshotStore


@dataclass(frozen=True)
class ImportSnapshot:
    store: SnapshotStore
    reader: SnapshotReader

    def execute(self, data: ImportSnapshotInput) -> ImportSnapshotResultView:
        bundle = self.reader.read(data.path)
        ensure_closed(bundle)
        self.store.replace(bundle)
        return ImportSnapshotResultView(
            path=data.path,
            mode=data.mode,
            counts=SnapshotCountsView.of(bundle),
        )


def ensure_closed(bundle: SnapshotBundle) -> None:
    """Recusa o snapshot cujas referências não estão nele mesmo."""
    projects = _unique_ids(bundle.projects, "projects")
    initiatives = _unique_ids(bundle.initiatives, "initiatives")
    members = _unique_ids(bundle.members, "members")
    squads = _unique_ids(bundle.squads, "squads")
    sprints = _unique_ids(bundle.sprints, "sprints")
    _unique_ids(bundle.squad_memberships, "squad_memberships")
    _unique_ids(bundle.allocations, "allocations")
    _unique_ids(bundle.muted_alerts, "muted_alerts")

    for initiative in bundle.initiatives:
        _require(initiative.project_id, projects, "initiatives", "project_id")
    for squad in bundle.squads:
        if squad.representative_member_id is not None:
            _require(
                squad.representative_member_id,
                members,
                "squads",
                "representative_member_id",
            )
    for link in bundle.squad_memberships:
        _require(link.squad_id, squads, "squad_memberships", "squad_id")
        _require(link.member_id, members, "squad_memberships", "member_id")
        _require(link.sprint_id, sprints, "squad_memberships", "sprint_id")
    for cell in bundle.allocations:
        _require(cell.initiative_id, initiatives, "allocations", "initiative_id")
        _require(cell.sprint_id, sprints, "allocations", "sprint_id")
        if cell.squad_id is not None:
            _require(cell.squad_id, squads, "allocations", "squad_id")
        if cell.member_id is not None:
            _require(cell.member_id, members, "allocations", "member_id")


class _Identified(Protocol):
    """Qualquer entidade do bundle: o que a checagem precisa é o `id`.

    Declarado como propriedade, e não como atributo, para aceitar tanto as
    entidades mutáveis quanto as `frozen` — as duas formas convivem no §6.
    """

    @property
    def id(self) -> UUID: ...


def _unique_ids(rows: Collection[_Identified], file: str) -> frozenset[UUID]:
    seen: set[UUID] = set()
    for row in rows:
        if row.id in seen:
            raise InvalidSnapshot(
                f"{file}.json tem o id {row.id} mais de uma vez.",
                file=f"{file}.json",
                id=str(row.id),
            )
        seen.add(row.id)
    return frozenset(seen)


def _require(value: UUID, known: frozenset[UUID], file: str, field: str) -> None:
    if value not in known:
        raise InvalidSnapshot(
            f"{file}.json referencia {field}={value}, que não está no snapshot.",
            file=f"{file}.json",
            field=field,
            id=str(value),
        )
