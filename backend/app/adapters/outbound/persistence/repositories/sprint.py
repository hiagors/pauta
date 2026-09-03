"""`SprintRepository` em SQLAlchemy (§6.6).

Sem `delete` e sem `update`: sprint nunca é excluída (D13), e as datas de uma
sprint existente só mudam por `POST /sprints` de uma nova — o §8 não tem
`PATCH /sprints/{id}`.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.outbound.persistence.mappers import sprint_to_entity, sprint_to_model
from app.adapters.outbound.persistence.models import SprintModel
from app.domain.entities.sprint import Sprint


@dataclass(frozen=True)
class SqlAlchemySprintRepository:
    session: Session

    def add(self, sprint: Sprint) -> None:
        self.session.add(sprint_to_model(sprint))
        self.session.flush()

    def get(self, sprint_id: UUID) -> Sprint | None:
        model = self.session.get(SprintModel, sprint_id)
        return None if model is None else sprint_to_entity(model)

    def get_by_number(self, number: int) -> Sprint | None:
        model = self.session.scalars(
            select(SprintModel).where(SprintModel.number == number).limit(1)
        ).first()
        return None if model is None else sprint_to_entity(model)

    def list_all(
        self, *, number_from: int | None = None, number_to: int | None = None
    ) -> list[Sprint]:
        """Ordenado por `number` crescente — a porta promete, e a consolidação
        de barras da grade conta com isso."""
        statement = select(SprintModel).order_by(SprintModel.number)
        if number_from is not None:
            statement = statement.where(SprintModel.number >= number_from)
        if number_to is not None:
            statement = statement.where(SprintModel.number <= number_to)
        return [sprint_to_entity(model) for model in self.session.scalars(statement)]
