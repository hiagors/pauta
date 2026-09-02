"""Silenciamento de alerta (§6.9).

É a única coisa do §7.3 que tem linha no banco: os alertas são calculados sob
demanda, o silenciamento é persistido.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self
from uuid import UUID, uuid4

from app.domain.errors import InvalidTimestamp, MuteReasonRequired
from app.domain.ports.clock import Clock
from app.domain.value_objects.alert import AlertType


@dataclass(frozen=True)
class MutedAlert:
    id: UUID
    alert_type: AlertType
    fingerprint: str
    reason: str
    created_at: datetime

    def __post_init__(self) -> None:
        reason = self.reason.strip()
        if not reason:
            raise MuteReasonRequired
        object.__setattr__(self, "reason", reason)
        if self.created_at.tzinfo is None:
            raise InvalidTimestamp("created_at")
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))

    @classmethod
    def create(
        cls,
        *,
        alert_type: AlertType,
        fingerprint: str,
        reason: str,
        clock: Clock,
        id: UUID | None = None,
    ) -> Self:
        return cls(
            id=id or uuid4(),
            alert_type=alert_type,
            fingerprint=fingerprint,
            reason=reason,
            created_at=clock.now(),
        )
