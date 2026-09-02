"""`InitiativeRepository` em SQLAlchemy (§6.2)."""

from collections.abc import Collection
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters.outbound.persistence.mappers import (
    initiative_apply,
    initiative_to_entity,
    initiative_to_model,
)
from app.adapters.outbound.persistence.models import InitiativeModel
from app.adapters.outbound.persistence.repositories.filters import any_of, contains_text
from app.domain.entities.initiative import Initiative
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.priority import Priority


@dataclass(frozen=True)
class SqlAlchemyInitiativeRepository:
    session: Session

    def add(self, initiative: Initiative) -> None:
        self.session.add(initiative_to_model(initiative))
        self.session.flush()

    def update(self, initiative: Initiative) -> None:
        model = self.session.get(InitiativeModel, initiative.id)
        if model is None:
            self.session.add(initiative_to_model(initiative))
        else:
            initiative_apply(model, initiative)
        self.session.flush()

    def get(self, initiative_id: UUID) -> Initiative | None:
        model = self.session.get(InitiativeModel, initiative_id)
        return None if model is None else initiative_to_entity(model)

    def get_by_name(self, *, project_id: UUID, name: str) -> Initiative | None:
        """Nome é único **dentro do projeto** (§6.2)."""
        model = self.session.scalars(
            select(InitiativeModel)
            .where(
                InitiativeModel.project_id == project_id,
                InitiativeModel.name == name,
            )
            .limit(1)
        ).first()
        return None if model is None else initiative_to_entity(model)

    def list_all(
        self,
        *,
        project_id: UUID | None = None,
        statuses: Collection[InitiativeStatus] | None = None,
        priorities: Collection[Priority] | None = None,
        layer: str | None = None,
        query: str | None = None,
    ) -> list[Initiative]:
        statement = select(InitiativeModel).order_by(InitiativeModel.name)
        if project_id is not None:
            statement = statement.where(InitiativeModel.project_id == project_id)
        if statuses is not None:
            statement = statement.where(any_of(InitiativeModel.status, statuses))
        if priorities is not None:
            statement = statement.where(any_of(InitiativeModel.priority, priorities))
        if layer is not None:
            statement = statement.where(InitiativeModel.layer == layer)
        if query is not None:
            statement = statement.where(contains_text(InitiativeModel.name, query))
        return [
            initiative_to_entity(model) for model in self.session.scalars(statement)
        ]

    def list_by_ids(self, ids: Collection[UUID]) -> list[Initiative]:
        wanted = list(ids)
        if not wanted:
            return []
        found = {
            model.id: initiative_to_entity(model)
            for model in self.session.scalars(
                select(InitiativeModel).where(InitiativeModel.id.in_(wanted))
            )
        }
        return [found[key] for key in wanted if key in found]

    def count_by_project(self, project_id: UUID) -> int:
        """RN-I2: é o que impede o projeto de ficar sem iniciativa."""
        return (
            self.session.scalar(
                select(func.count())
                .select_from(InitiativeModel)
                .where(InitiativeModel.project_id == project_id)
            )
            or 0
        )

    def delete(self, initiative_id: UUID) -> None:
        model = self.session.get(InitiativeModel, initiative_id)
        if model is not None:
            self.session.delete(model)
            self.session.flush()
