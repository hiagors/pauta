"""`SnapshotStore` em SQLAlchemy (RNF4).

Mora entre os repositórios porque é o que ele é: fala com a mesma `Session` e
usa os mesmos mappers. O que ele tem de diferente é o escopo — o banco inteiro,
não um agregado — e é por isso que a porta é outra (ver
`domain/ports/snapshot.py`).

Como todo repositório, faz `flush` e nunca `commit`: quem abre e fecha a
transação é o adapter de entrada. É isso que faz o `replace` ser tudo ou nada,
e é isso que protege o banco de uma pasta de snapshot pela metade.

A **ordem** das duas listas é o assunto do módulo. Com
`PRAGMA foreign_keys=ON` (RNF1), apagar na ordem errada bate na chave
estrangeira: as folhas saem primeiro e as raízes entram primeiro.

`external_refs` não é tocada: é pavimento da v2 e está vazia na v1 (§6.10).
Apagá-la num `replace` seria apagar dado que este sistema não sabe recriar.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.adapters.outbound.persistence import mappers
from app.adapters.outbound.persistence.models import (
    AllocationModel,
    Base,
    InitiativeModel,
    MemberModel,
    MutedAlertModel,
    ProjectModel,
    SprintModel,
    SquadMembershipModel,
    SquadModel,
)
from app.domain.ports.snapshot import SnapshotBundle

#: Da raiz para a folha. É a ordem de inserção; a de exclusão é a inversa.
_WRITE_ORDER: Final[tuple[type[Base], ...]] = (
    ProjectModel,
    MemberModel,
    SquadModel,
    SprintModel,
    InitiativeModel,
    SquadMembershipModel,
    AllocationModel,
    MutedAlertModel,
)


@dataclass(frozen=True)
class SqlAlchemySnapshotStore:
    session: Session

    def dump(self) -> SnapshotBundle:
        return SnapshotBundle(
            projects=self._all(ProjectModel, mappers.project_to_entity),
            initiatives=self._all(InitiativeModel, mappers.initiative_to_entity),
            members=self._all(MemberModel, mappers.member_to_entity),
            squads=self._all(SquadModel, mappers.squad_to_entity),
            squad_memberships=self._all(
                SquadMembershipModel, mappers.membership_to_entity
            ),
            sprints=self._all(SprintModel, mappers.sprint_to_entity),
            allocations=self._all(AllocationModel, mappers.allocation_to_entity),
            muted_alerts=self._all(MutedAlertModel, mappers.muted_alert_to_entity),
        )

    def replace(self, bundle: SnapshotBundle) -> None:
        """Apaga tudo e grava o bundle, na mesma transação."""
        for model in reversed(_WRITE_ORDER):
            self.session.execute(delete(model))
        self.session.flush()
        self._add(
            [mappers.project_to_model(entity) for entity in bundle.projects],
            [mappers.member_to_model(entity) for entity in bundle.members],
            [mappers.squad_to_model(entity) for entity in bundle.squads],
            [mappers.sprint_to_model(entity) for entity in bundle.sprints],
            [mappers.initiative_to_model(entity) for entity in bundle.initiatives],
            [
                mappers.membership_to_model(entity)
                for entity in bundle.squad_memberships
            ],
            [mappers.allocation_to_model(entity) for entity in bundle.allocations],
            [mappers.muted_alert_to_model(entity) for entity in bundle.muted_alerts],
        )

    def _all[E](self, model: Any, to_entity: Callable[[Any], E]) -> tuple[E, ...]:
        """Ordenado por `id`: é a ordem que o snapshot grava (§9)."""
        rows = self.session.scalars(select(model).order_by(model.id))
        return tuple(to_entity(row) for row in rows)

    def _add(self, *batches: Sequence[Base]) -> None:
        """Um `flush` por lote, e não um no fim: é o que faz a chave
        estrangeira ver a raiz antes da folha."""
        for batch in batches:
            if batch:
                self.session.add_all(batch)
                self.session.flush()
