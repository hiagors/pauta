"""`ProjectRepository` em SQLAlchemy (§6.1)."""

from collections.abc import Collection
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.outbound.persistence.mappers import (
    project_apply,
    project_to_entity,
    project_to_model,
)
from app.adapters.outbound.persistence.models import ProjectModel
from app.adapters.outbound.persistence.repositories.filters import contains_text
from app.domain.entities.project import Project


@dataclass(frozen=True)
class SqlAlchemyProjectRepository:
    session: Session

    def add(self, project: Project) -> None:
        self.session.add(project_to_model(project))
        self.session.flush()

    def update(self, project: Project) -> None:
        """Grava sobre a linha existente; se ela não existe, insere.

        A porta não distingue insert de update e o fake da Fase 2 é um upsert.
        Divergir aqui faria a mesma suíte passar num lado e falhar no outro.
        """
        model = self.session.get(ProjectModel, project.id)
        if model is None:
            self.session.add(project_to_model(project))
        else:
            project_apply(model, project)
        self.session.flush()

    def get(self, project_id: UUID) -> Project | None:
        model = self.session.get(ProjectModel, project_id)
        return None if model is None else project_to_entity(model)

    def get_by_name(self, name: str) -> Project | None:
        model = self.session.scalars(
            select(ProjectModel).where(ProjectModel.name == name).limit(1)
        ).first()
        return None if model is None else project_to_entity(model)

    def list_all(
        self, *, active: bool | None = None, query: str | None = None
    ) -> list[Project]:
        statement = select(ProjectModel).order_by(ProjectModel.name)
        if active is not None:
            statement = statement.where(ProjectModel.is_active.is_(active))
        if query is not None:
            statement = statement.where(contains_text(ProjectModel.name, query))
        return [project_to_entity(model) for model in self.session.scalars(statement)]

    def list_by_ids(self, ids: Collection[UUID]) -> list[Project]:
        """Na ordem pedida, pulando o que não existe — como o fake."""
        wanted = list(ids)
        if not wanted:
            return []
        found = {
            model.id: project_to_entity(model)
            for model in self.session.scalars(
                select(ProjectModel).where(ProjectModel.id.in_(wanted))
            )
        }
        return [found[key] for key in wanted if key in found]

    def delete(self, project_id: UUID) -> None:
        """Exclusão física: projeto não tem `is_active` como saída de exclusão
        — o que protege o histórico é a guarda de alocação no use case (§8)."""
        model = self.session.get(ProjectModel, project_id)
        if model is not None:
            self.session.delete(model)
            self.session.flush()
