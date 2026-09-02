"""`SquadRepository` em SQLAlchemy (§6.5).

Sem `delete`: `DELETE /squads/{id}` é `is_active = false` (§8). E sem lista de
membros — quem está na squad em cada sprint é `SquadMembershipRepository`.
"""

from collections.abc import Collection
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.outbound.persistence.mappers import (
    squad_apply,
    squad_to_entity,
    squad_to_model,
)
from app.adapters.outbound.persistence.models import SquadModel
from app.domain.entities.squad import Squad


@dataclass(frozen=True)
class SqlAlchemySquadRepository:
    session: Session

    def add(self, squad: Squad) -> None:
        self.session.add(squad_to_model(squad))
        self.session.flush()

    def update(self, squad: Squad) -> None:
        model = self.session.get(SquadModel, squad.id)
        if model is None:
            self.session.add(squad_to_model(squad))
        else:
            squad_apply(model, squad)
        self.session.flush()

    def get(self, squad_id: UUID) -> Squad | None:
        model = self.session.get(SquadModel, squad_id)
        return None if model is None else squad_to_entity(model)

    def get_by_name(self, name: str) -> Squad | None:
        model = self.session.scalars(
            select(SquadModel).where(SquadModel.name == name).limit(1)
        ).first()
        return None if model is None else squad_to_entity(model)

    def list_all(self, *, active: bool | None = None) -> list[Squad]:
        statement = select(SquadModel).order_by(SquadModel.name)
        if active is not None:
            statement = statement.where(SquadModel.is_active.is_(active))
        return [squad_to_entity(model) for model in self.session.scalars(statement)]

    def list_by_ids(self, ids: Collection[UUID]) -> list[Squad]:
        wanted = list(ids)
        if not wanted:
            return []
        found = {
            model.id: squad_to_entity(model)
            for model in self.session.scalars(
                select(SquadModel).where(SquadModel.id.in_(wanted))
            )
        }
        return [found[key] for key in wanted if key in found]
