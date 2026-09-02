"""`SquadMembershipRepository` em SQLAlchemy (§6.5).

Sem `get` e sem `update`: membership é uma linha de composição, não uma
entidade que se edita. O que se faz com ela é criar em lote, listar, checar
existência e apagar em lote — que é exatamente o que `PUT` e `DELETE
/squads/{id}/memberships` precisam.
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.orm import Session

from app.adapters.outbound.persistence.mappers import (
    membership_to_entity,
    membership_to_model,
)
from app.adapters.outbound.persistence.models import SquadMembershipModel
from app.adapters.outbound.persistence.repositories.filters import any_of
from app.domain.entities.squad_membership import SquadMembership


@dataclass(frozen=True)
class SqlAlchemySquadMembershipRepository:
    session: Session

    def add_many(self, memberships: Sequence[SquadMembership]) -> None:
        """O `flush` é obrigatório, não zelo: `PUT /memberships` apaga o
        intervalo e insere em seguida, e `compose_by_sprint` relê logo depois
        para devolver a composição resultante."""
        if not memberships:
            return
        self.session.add_all(
            [membership_to_model(membership) for membership in memberships]
        )
        self.session.flush()

    def exists(self, *, squad_id: UUID, member_id: UUID, sprint_id: UUID) -> bool:
        return (
            self.session.scalars(
                select(SquadMembershipModel.id)
                .where(
                    SquadMembershipModel.squad_id == squad_id,
                    SquadMembershipModel.member_id == member_id,
                    SquadMembershipModel.sprint_id == sprint_id,
                )
                .limit(1)
            ).first()
            is not None
        )

    def list_all(
        self,
        *,
        squad_id: UUID | None = None,
        member_id: UUID | None = None,
        sprint_ids: Collection[UUID] | None = None,
    ) -> list[SquadMembership]:
        statement = select(SquadMembershipModel)
        if squad_id is not None:
            statement = statement.where(SquadMembershipModel.squad_id == squad_id)
        if member_id is not None:
            statement = statement.where(SquadMembershipModel.member_id == member_id)
        if sprint_ids is not None:
            statement = statement.where(
                any_of(SquadMembershipModel.sprint_id, sprint_ids)
            )
        return [
            membership_to_entity(model) for model in self.session.scalars(statement)
        ]

    def delete(
        self,
        *,
        squad_id: UUID,
        sprint_ids: Collection[UUID],
        member_ids: Collection[UUID] | None = None,
    ) -> int:
        """`member_ids` ausente remove todo mundo do intervalo (§8).

        Devolve quantas linhas saíram — é o `rowcount` do `DELETE`, não uma
        contagem separada, para não fazer duas idas ao banco.
        """
        statement = delete(SquadMembershipModel).where(
            SquadMembershipModel.squad_id == squad_id,
            any_of(SquadMembershipModel.sprint_id, sprint_ids),
        )
        if member_ids is not None:
            statement = statement.where(
                any_of(SquadMembershipModel.member_id, member_ids)
            )
        #: `Session.execute` é tipado como `Result`, mas um DML devolve
        #: `CursorResult` — é dele que vem o `rowcount`.
        result = cast(
            "CursorResult[Any]",
            self.session.execute(
                statement, execution_options={"synchronize_session": "fetch"}
            ),
        )
        self.session.flush()
        return result.rowcount
