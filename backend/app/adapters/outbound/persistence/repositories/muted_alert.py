"""`MutedAlertRepository` em SQLAlchemy (§6.9).

A única tabela do §7.3: o alerta é calculado sob demanda, o silenciamento é
persistido. Sem `update` — reativar é apagar a linha, e mudar o motivo é
silenciar de novo.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.outbound.persistence.mappers import (
    muted_alert_to_entity,
    muted_alert_to_model,
)
from app.adapters.outbound.persistence.models import MutedAlertModel
from app.domain.entities.muted_alert import MutedAlert


@dataclass(frozen=True)
class SqlAlchemyMutedAlertRepository:
    session: Session

    def add(self, mute: MutedAlert) -> None:
        self.session.add(muted_alert_to_model(mute))
        self.session.flush()

    def get(self, mute_id: UUID) -> MutedAlert | None:
        model = self.session.get(MutedAlertModel, mute_id)
        return None if model is None else muted_alert_to_entity(model)

    def get_by_fingerprint(self, fingerprint: str) -> MutedAlert | None:
        """O `fingerprint` é único (§6.9): é a chave que o painel usa para
        saber se o alerta que acabou de calcular está silenciado."""
        model = self.session.scalars(
            select(MutedAlertModel)
            .where(MutedAlertModel.fingerprint == fingerprint)
            .limit(1)
        ).first()
        return None if model is None else muted_alert_to_entity(model)

    def list_all(self) -> list[MutedAlert]:
        return [
            muted_alert_to_entity(model)
            for model in self.session.scalars(
                select(MutedAlertModel).order_by(
                    MutedAlertModel.created_at, MutedAlertModel.id
                )
            )
        ]

    def delete(self, mute_id: UUID) -> None:
        model = self.session.get(MutedAlertModel, mute_id)
        if model is not None:
            self.session.delete(model)
            self.session.flush()
