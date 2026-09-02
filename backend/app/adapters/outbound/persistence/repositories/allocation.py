"""`AllocationRepository` em SQLAlchemy (§6.7).

Sem `update`: alocação é imutável. Mudar o responsável de uma célula é apagar e
criar de novo — o que também é o que a unicidade `(initiative_id, sprint_id)`
força (RN8).
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.orm import Session

from app.adapters.outbound.persistence.mappers import (
    allocation_to_entity,
    allocation_to_model,
)
from app.adapters.outbound.persistence.models import AllocationModel
from app.adapters.outbound.persistence.repositories.filters import any_of
from app.domain.entities.allocation import Allocation


@dataclass(frozen=True)
class SqlAlchemyAllocationRepository:
    session: Session

    def add_many(self, allocations: Sequence[Allocation]) -> None:
        if not allocations:
            return
        self.session.add_all(
            [allocation_to_model(allocation) for allocation in allocations]
        )
        self.session.flush()

    def get(self, allocation_id: UUID) -> Allocation | None:
        model = self.session.get(AllocationModel, allocation_id)
        return None if model is None else allocation_to_entity(model)

    def list_all(
        self,
        *,
        sprint_ids: Collection[UUID] | None = None,
        initiative_ids: Collection[UUID] | None = None,
        squad_id: UUID | None = None,
        member_id: UUID | None = None,
    ) -> list[Allocation]:
        statement = select(AllocationModel)
        if sprint_ids is not None:
            statement = statement.where(any_of(AllocationModel.sprint_id, sprint_ids))
        if initiative_ids is not None:
            statement = statement.where(
                any_of(AllocationModel.initiative_id, initiative_ids)
            )
        if squad_id is not None:
            statement = statement.where(AllocationModel.squad_id == squad_id)
        if member_id is not None:
            statement = statement.where(AllocationModel.member_id == member_id)
        return [
            allocation_to_entity(model) for model in self.session.scalars(statement)
        ]

    def count_by_initiative(self, initiative_id: UUID) -> int:
        """RN2: é a pergunta "tem alocação?" que move BACKLOG <-> PLANNED."""
        return (
            self.session.scalar(
                select(func.count())
                .select_from(AllocationModel)
                .where(AllocationModel.initiative_id == initiative_id)
            )
            or 0
        )

    def delete(self, allocation_id: UUID) -> None:
        model = self.session.get(AllocationModel, allocation_id)
        if model is not None:
            self.session.delete(model)
            self.session.flush()

    def delete_many(self, ids: Collection[UUID]) -> int:
        wanted = list(ids)
        if not wanted:
            return 0
        #: `Session.execute` é tipado como `Result`, mas um DML devolve
        #: `CursorResult` — é dele que vem o `rowcount`.
        result = cast(
            "CursorResult[Any]",
            self.session.execute(
                delete(AllocationModel).where(AllocationModel.id.in_(wanted)),
                execution_options={"synchronize_session": "fetch"},
            ),
        )
        self.session.flush()
        return result.rowcount
