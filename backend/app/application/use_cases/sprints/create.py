"""Criar sprint com datas informadas (`POST /sprints`)."""

from dataclasses import dataclass

from app.application.dto.sprints import CreateSprintInput, SprintView
from app.domain.entities.sprint import Sprint
from app.domain.ports.clock import Clock
from app.domain.ports.repositories import SprintRepository
from app.domain.services.planning_rules import ensure_can_add_sprint, is_current
from app.domain.value_objects.sprint_range import MIN_SPRINT_NUMBER


@dataclass(frozen=True)
class CreateSprint:
    sprints: SprintRepository
    clock: Clock

    def execute(self, data: CreateSprintInput) -> SprintView:
        """Aceita datas arbitrárias que respeitem as invariantes do §6.6.

        `number` ausente continua a numeração: a próxima da última cadastrada,
        ou `1` quando o banco está vazio. A primeira sprint do time normalmente
        vem com número explícito — a 18, no dado real — e por isso a validação
        do conjunto não exige que a numeração comece em 1.
        """
        existing = list(self.sprints.list_all())
        last = max(existing, key=lambda sprint: sprint.number, default=None)
        number = data.number
        if number is None:
            number = last.number + 1 if last is not None else MIN_SPRINT_NUMBER
        sprint = Sprint.create(
            number=number, start_date=data.start_date, end_date=data.end_date
        )
        ensure_can_add_sprint(existing, sprint)
        self.sprints.add(sprint)
        return SprintView.of(
            sprint,
            is_current=is_current(sprint, [*existing, sprint], self.clock.today()),
        )
