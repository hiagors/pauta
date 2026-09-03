"""Listar alertas (`GET /alerts`, §8).

Janela default: da sprint atual (RN12) até a última cadastrada. Olhar para trás
não muda nada — o passado já aconteceu — e olhar além da última sprint não tem
dado.

Os silenciados saem da lista mas continuam contados: o painel mostra os
não silenciados e guarda os outros atrás de um contador expansível (§7.3).
"""

from dataclasses import dataclass

from app.application.dto.alerts import AlertsQuery, AlertsView
from app.application.planning_view import load_mutes, load_snapshot, load_window
from app.domain.ports.clock import Clock
from app.domain.ports.repositories import (
    AllocationRepository,
    InitiativeRepository,
    MemberRepository,
    MutedAlertRepository,
    ProjectRepository,
    SprintRepository,
    SquadMembershipRepository,
    SquadRepository,
)
from app.domain.services.alert_service import evaluate_alerts


@dataclass(frozen=True)
class ListAlerts:
    sprints: SprintRepository
    allocations: AllocationRepository
    initiatives: InitiativeRepository
    projects: ProjectRepository
    squads: SquadRepository
    members: MemberRepository
    memberships: SquadMembershipRepository
    muted_alerts: MutedAlertRepository
    clock: Clock

    def execute(self, query: AlertsQuery | None = None) -> AlertsView:
        criteria = query or AlertsQuery()
        everything = load_window(sprints=self.sprints, clock=self.clock)
        if not everything.selected:
            return AlertsView(items=(), muted_count=0)
        numbers = everything.numbers
        window = everything.narrowed(
            number_from=(
                criteria.sprint_from
                if criteria.sprint_from is not None
                else everything.current_number or min(numbers)
            ),
            number_to=(
                criteria.sprint_to if criteria.sprint_to is not None else max(numbers)
            ),
        )
        alerts = evaluate_alerts(
            load_snapshot(
                window=window,
                allocations=self.allocations,
                initiatives=self.initiatives,
                projects=self.projects,
                members=self.members,
                squads=self.squads,
                memberships=self.memberships,
            ),
            load_mutes(self.muted_alerts),
        )
        return AlertsView(
            items=tuple(
                alert
                for alert in alerts
                if criteria.include_muted or not alert.is_muted
            ),
            muted_count=sum(1 for alert in alerts if alert.is_muted),
        )
