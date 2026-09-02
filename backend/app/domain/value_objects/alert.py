"""Alerta calculado (§7.3).

Alerta não é entidade: nunca é persistido, é derivado do plano a cada consulta.
Só o *silenciamento* (`MutedAlert`) tem linha no banco.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Self
from uuid import UUID

if TYPE_CHECKING:  # pragma: no cover - só para o type checker
    from app.domain.entities.muted_alert import MutedAlert


class Severity(StrEnum):
    """Viaja em inglês até a UI, que faz o mapa para o rótulo em português."""

    WARNING = "WARNING"
    INFO = "INFO"


class AlertType(StrEnum):
    SQUAD_OVERLOADED = "SQUAD_OVERLOADED"
    MEMBER_CONFLICT = "MEMBER_CONFLICT"
    MEMBER_IDLE = "MEMBER_IDLE"
    EMPTY_SQUAD = "EMPTY_SQUAD"

    @property
    def severity(self) -> Severity:
        return _SEVERITIES[self]


_SEVERITIES: Final[Mapping[AlertType, Severity]] = {
    AlertType.SQUAD_OVERLOADED: Severity.WARNING,
    AlertType.MEMBER_CONFLICT: Severity.WARNING,
    AlertType.MEMBER_IDLE: Severity.INFO,
    AlertType.EMPTY_SQUAD: Severity.INFO,
}


class EntityRefType(StrEnum):
    """Minúsculo, como `assignee.kind`: é valor de JSON."""

    PROJECT = "project"
    INITIATIVE = "initiative"
    SQUAD = "squad"
    MEMBER = "member"


@dataclass(frozen=True)
class EntityRef:
    """Referência tipada, nunca UUID cru — a UI precisa do nome para o link."""

    type: EntityRefType
    id: UUID
    name: str


@dataclass(frozen=True)
class Alert:
    type: AlertType
    severity: Severity
    sprint_number: int
    subject_id: UUID
    entity_refs: tuple[EntityRef, ...]
    message: str
    fingerprint: str
    is_muted: bool = False
    mute_id: UUID | None = None
    mute_reason: str | None = None

    @classmethod
    def build(
        cls,
        *,
        type: AlertType,
        sprint_number: int,
        subject_id: UUID,
        entity_refs: tuple[EntityRef, ...],
        message: str,
        fingerprint: str,
    ) -> Self:
        """A severidade não é escolha de quem monta: vem do tipo (§7.3)."""
        return cls(
            type=type,
            severity=type.severity,
            sprint_number=sprint_number,
            subject_id=subject_id,
            entity_refs=entity_refs,
            message=message,
            fingerprint=fingerprint,
        )

    def muted_by(self, mute: MutedAlert) -> Alert:
        """Cópia silenciada. `mute_id` é o que o botão "Reativar" usa."""
        return replace(self, is_muted=True, mute_id=mute.id, mute_reason=mute.reason)
