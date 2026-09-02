"""Schemas de alerta e silenciamento (§7.3, §8)."""

from datetime import datetime
from uuid import UUID

from app.adapters.inbound.http.schemas.common import InputModel, OutputModel
from app.application.dto.alerts import MuteAlertInput
from app.domain.value_objects.alert import AlertType, EntityRefType, Severity


class EntityRefOut(OutputModel):
    """Referência tipada, nunca UUID cru — a UI precisa do nome para o link."""

    type: EntityRefType
    id: UUID
    name: str


class AlertOut(OutputModel):
    """Alerta calculado. `mute_id` é o que o botão "Reativar" usa (§7.3)."""

    type: AlertType
    severity: Severity
    sprint_number: int
    subject_id: UUID
    entity_refs: list[EntityRefOut]
    message: str
    fingerprint: str
    is_muted: bool
    mute_id: UUID | None
    mute_reason: str | None


class AlertsOut(OutputModel):
    """`muted_count` alimenta o contador expansível do painel (§7.3)."""

    items: list[AlertOut]
    muted_count: int


class MuteAlertIn(InputModel):
    """Silenciar exige motivo em texto e é reversível (§7.3)."""

    fingerprint: str
    alert_type: AlertType
    reason: str

    def to_input(self) -> MuteAlertInput:
        return MuteAlertInput(
            fingerprint=self.fingerprint,
            alert_type=self.alert_type,
            reason=self.reason,
        )


class MutedAlertOut(OutputModel):
    id: UUID
    alert_type: AlertType
    fingerprint: str
    reason: str
    created_at: datetime
