"""DTOs de alerta e silenciamento (§7.3).

`Alert` é value object de domínio e viaja como está: é calculado, nunca
persistido, e o §7.3 já define exatamente os campos que a UI recebe. Só o
silenciamento é entidade, e por isso tem view própria.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Self
from uuid import UUID

from app.domain.entities.muted_alert import MutedAlert
from app.domain.value_objects.alert import Alert, AlertType


@dataclass(frozen=True)
class AlertsQuery:
    """Sem intervalo, a janela é da sprint atual à última cadastrada (§8)."""

    sprint_from: int | None = None
    sprint_to: int | None = None
    include_muted: bool = False


@dataclass(frozen=True)
class MuteAlertInput:
    fingerprint: str
    alert_type: AlertType
    reason: str


@dataclass(frozen=True)
class MutedAlertView:
    id: UUID
    alert_type: AlertType
    fingerprint: str
    reason: str
    created_at: datetime

    @classmethod
    def of(cls, mute: MutedAlert) -> Self:
        return cls(
            id=mute.id,
            alert_type=mute.alert_type,
            fingerprint=mute.fingerprint,
            reason=mute.reason,
            created_at=mute.created_at,
        )


@dataclass(frozen=True)
class AlertsView:
    """`muted_count` alimenta o contador expansível do painel (§7.3)."""

    items: tuple[Alert, ...]
    muted_count: int
