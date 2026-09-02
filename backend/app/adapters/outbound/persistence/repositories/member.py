"""`MemberRepository` em SQLAlchemy (§6.4).

Sem `delete`: `DELETE /members/{id}` é `is_active = false`, e apagar
reescreveria alocações passadas.
"""

from collections.abc import Collection
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.outbound.persistence.mappers import (
    member_apply,
    member_to_entity,
    member_to_model,
)
from app.adapters.outbound.persistence.models import MemberModel
from app.domain.entities.member import Member


@dataclass(frozen=True)
class SqlAlchemyMemberRepository:
    session: Session

    def add(self, member: Member) -> None:
        self.session.add(member_to_model(member))
        self.session.flush()

    def update(self, member: Member) -> None:
        model = self.session.get(MemberModel, member.id)
        if model is None:
            self.session.add(member_to_model(member))
        else:
            member_apply(model, member)
        self.session.flush()

    def get(self, member_id: UUID) -> Member | None:
        model = self.session.get(MemberModel, member_id)
        return None if model is None else member_to_entity(model)

    def list_all(self, *, active: bool | None = None) -> list[Member]:
        statement = select(MemberModel).order_by(MemberModel.name)
        if active is not None:
            statement = statement.where(MemberModel.is_active.is_(active))
        return [member_to_entity(model) for model in self.session.scalars(statement)]

    def list_by_ids(self, ids: Collection[UUID]) -> list[Member]:
        wanted = list(ids)
        if not wanted:
            return []
        found = {
            model.id: member_to_entity(model)
            for model in self.session.scalars(
                select(MemberModel).where(MemberModel.id.in_(wanted))
            )
        }
        return [found[key] for key in wanted if key in found]
