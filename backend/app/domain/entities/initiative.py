"""Iniciativa: a unidade de trabalho, a linha do Gantt (§6.2)."""

from dataclasses import dataclass
from datetime import date
from typing import Self
from uuid import UUID, uuid4

from app.domain.entities.project import Project
from app.domain.errors import (
    InitiativeNotAllocatable,
    InvalidEstimate,
    InvalidName,
    InvalidStatusTransition,
)
from app.domain.ports.clock import Clock
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.priority import Priority


@dataclass
class Initiative:
    id: UUID
    project_id: UUID
    name: str
    entered_at: date
    layer: str | None = None
    description: str = ""
    priority: Priority = Priority.MEDIUM
    estimated_sprints: int | None = None
    status: InitiativeStatus = InitiativeStatus.BACKLOG

    def __post_init__(self) -> None:
        self.name = _require_name(self.name)
        self.layer = _clean_optional(self.layer)
        self.description = self.description.strip()
        _validate_estimate(self.estimated_sprints)

    @classmethod
    def create(
        cls,
        *,
        project_id: UUID,
        name: str,
        clock: Clock,
        layer: str | None = None,
        description: str = "",
        priority: Priority = Priority.MEDIUM,
        estimated_sprints: int | None = None,
        id: UUID | None = None,
    ) -> Self:
        """Iniciativa nova, sempre em BACKLOG e com `entered_at` do `Clock`."""
        return cls(
            id=id or uuid4(),
            project_id=project_id,
            name=name,
            entered_at=clock.today(),
            layer=layer,
            description=description,
            priority=priority,
            estimated_sprints=estimated_sprints,
            status=InitiativeStatus.BACKLOG,
        )

    @classmethod
    def create_first_for_project(
        cls, project: Project, clock: Clock, id: UUID | None = None
    ) -> Self:
        """RN-I1: criar um projeto cria a primeira iniciativa, com o mesmo nome.

        Quem tem uma frente única nunca precisa pensar em iniciativa — o nome é
        editável em seguida.
        """
        return cls.create(
            project_id=project.id,
            name=project.name,
            clock=clock,
            priority=Priority.MEDIUM,
            id=id,
        )

    # ------------------------------------------------------------------ #
    # Status
    # ------------------------------------------------------------------ #

    def recalculate_status(self, has_allocations: bool) -> None:
        """Só BACKLOG <-> PLANNED. Nenhum outro status é tocado (RN2, §6.3).

        Não consulta a tabela de transições manuais de propósito: os dois
        caminhos não devem se contaminar. Uma iniciativa IN_PROGRESS que perde
        todas as alocações **continua** IN_PROGRESS; DEPRIORITIZED que ganha
        alocação **continua** DEPRIORITIZED (RN7).
        """
        if has_allocations and self.status is InitiativeStatus.BACKLOG:
            self.status = InitiativeStatus.PLANNED
        elif not has_allocations and self.status is InitiativeStatus.PLANNED:
            self.status = InitiativeStatus.BACKLOG

    def change_status(self, new_status: InitiativeStatus) -> None:
        """Transição manual, validada contra a tabela do §6.3."""
        if new_status is self.status:
            return
        if not self.status.can_change_to(new_status):
            raise InvalidStatusTransition(self.status.value, new_status.value)
        self.status = new_status

    def ensure_accepts_allocation(self) -> None:
        """RN7: DONE e CANCELLED não aceitam nova alocação."""
        if not self.status.accepts_allocation:
            raise InitiativeNotAllocatable(self.id, self.status.value)

    # ------------------------------------------------------------------ #
    # Edição
    # ------------------------------------------------------------------ #

    def rename(self, name: str) -> None:
        self.name = _require_name(name)

    def set_layer(self, layer: str | None) -> None:
        self.layer = _clean_optional(layer)

    def set_description(self, description: str) -> None:
        self.description = description.strip()

    def set_priority(self, priority: Priority) -> None:
        self.priority = priority

    def set_estimated_sprints(self, estimated_sprints: int | None) -> None:
        _validate_estimate(estimated_sprints)
        self.estimated_sprints = estimated_sprints


def _require_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise InvalidName("da iniciativa")
    return cleaned


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _validate_estimate(estimated_sprints: int | None) -> None:
    if estimated_sprints is not None and estimated_sprints <= 0:
        raise InvalidEstimate(estimated_sprints)
