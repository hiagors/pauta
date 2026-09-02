"""Propor e criar a sprint seguinte (RN10).

Duas operações, um módulo: a proposta (`GET /sprints/next/preview`) e a criação
dela (`POST /sprints/next`). O cálculo — número incrementado, início na segunda
seguinte ao fim da última, fim em `início + 11 dias` — é do domínio.

Quem quer datas diferentes edita a proposta e chama `POST /sprints`.
"""

from dataclasses import dataclass

from app.application.dto.sprints import SprintProposalView, SprintView
from app.domain.entities.sprint import Sprint
from app.domain.ports.clock import Clock
from app.domain.ports.repositories import SprintRepository
from app.domain.services.planning_rules import (
    ensure_can_add_sprint,
    is_current,
    propose_next_sprint,
)


@dataclass(frozen=True)
class PreviewNextSprint:
    sprints: SprintRepository

    def execute(self) -> SprintProposalView:
        """Sem nenhuma sprint cadastrada não há o que propor: 404 (§6.6)."""
        return SprintProposalView.of(propose_next_sprint(list(self.sprints.list_all())))


@dataclass(frozen=True)
class CreateNextSprint:
    sprints: SprintRepository
    clock: Clock

    def execute(self) -> SprintView:
        existing = list(self.sprints.list_all())
        proposal = propose_next_sprint(existing)
        sprint = Sprint.create(
            number=proposal.number,
            start_date=proposal.start_date,
            end_date=proposal.end_date,
        )
        ensure_can_add_sprint(existing, sprint)
        self.sprints.add(sprint)
        return SprintView.of(
            sprint,
            is_current=is_current(sprint, [*existing, sprint], self.clock.today()),
        )
