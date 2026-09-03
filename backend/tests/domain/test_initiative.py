"""Iniciativa: os dois caminhos de status não se contaminam (§6.3, RN2, RN7)."""

from datetime import date

import pytest

from app.domain.entities.initiative import Initiative
from app.domain.entities.project import Project
from app.domain.errors import (
    InitiativeNotAllocatable,
    InvalidEstimate,
    InvalidName,
    InvalidStatusTransition,
)
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.priority import Priority
from tests.domain.conftest import FrozenClock, uid

S = InitiativeStatus


def make(clock: FrozenClock, status: InitiativeStatus = S.BACKLOG) -> Initiative:
    initiative = Initiative.create(project_id=uid(1), name="Catálogo V1", clock=clock)
    initiative.status = status
    return initiative


class TestCreation:
    def test_it_is_born_in_backlog_with_medium_priority(
        self, clock: FrozenClock
    ) -> None:
        initiative = Initiative.create(project_id=uid(1), name="Aurora", clock=clock)
        assert initiative.status is S.BACKLOG
        assert initiative.priority is Priority.MEDIUM

    def test_entered_at_comes_from_the_clock_port_and_not_from_the_system(self) -> None:
        clock = FrozenClock(date(2026, 1, 15))
        initiative = Initiative.create(project_id=uid(1), name="Aurora", clock=clock)
        assert initiative.entered_at == date(2026, 1, 15)

    def test_the_name_is_required(self, clock: FrozenClock) -> None:
        with pytest.raises(InvalidName):
            Initiative.create(project_id=uid(1), name="  ", clock=clock)

    def test_an_empty_layer_becomes_none(self, clock: FrozenClock) -> None:
        initiative = Initiative.create(
            project_id=uid(1), name="Aurora", clock=clock, layer="  "
        )
        assert initiative.layer is None

    @pytest.mark.parametrize("estimate", [0, -1])
    def test_the_estimate_must_be_greater_than_zero(
        self, clock: FrozenClock, estimate: int
    ) -> None:
        with pytest.raises(InvalidEstimate):
            Initiative.create(
                project_id=uid(1),
                name="Aurora",
                clock=clock,
                estimated_sprints=estimate,
            )

    def test_a_missing_estimate_is_valid(self, clock: FrozenClock) -> None:
        initiative = Initiative.create(project_id=uid(1), name="Aurora", clock=clock)
        assert initiative.estimated_sprints is None

    def test_the_initiative_does_not_carry_the_capacity_reserve_flag(self) -> None:
        """§6.2: `is_capacity_reserve` é herdado do projeto."""
        assert "is_capacity_reserve" not in Initiative.__dataclass_fields__


class TestFirstInitiativeOfTheProject:
    def test_rn_i1_inherits_the_project_name(self, clock: FrozenClock) -> None:
        project = Project.create(name="Serviço de Envio")
        initiative = Initiative.create_first_for_project(project, clock)
        assert initiative.project_id == project.id
        assert initiative.name == "Serviço de Envio"
        assert initiative.priority is Priority.MEDIUM
        assert initiative.status is S.BACKLOG

    def test_the_name_is_editable_afterwards(self, clock: FrozenClock) -> None:
        project = Project.create(name="Aurora")
        initiative = Initiative.create_first_for_project(project, clock)
        initiative.rename("Catálogo V1")
        assert initiative.name == "Catálogo V1"
        assert project.name == "Aurora"


class TestRecalculateStatus:
    def test_the_first_allocation_moves_backlog_to_planned(
        self, clock: FrozenClock
    ) -> None:
        initiative = make(clock, S.BACKLOG)
        initiative.recalculate_status(has_allocations=True)
        assert initiative.status is S.PLANNED

    def test_losing_every_allocation_moves_planned_back_to_backlog(
        self, clock: FrozenClock
    ) -> None:
        initiative = make(clock, S.PLANNED)
        initiative.recalculate_status(has_allocations=False)
        assert initiative.status is S.BACKLOG

    @pytest.mark.parametrize(
        "status", [S.IN_PROGRESS, S.DEPRIORITIZED, S.DONE, S.CANCELLED]
    )
    @pytest.mark.parametrize("has_allocations", [True, False])
    def test_the_other_four_statuses_are_not_touched(
        self, clock: FrozenClock, status: InitiativeStatus, has_allocations: bool
    ) -> None:
        initiative = make(clock, status)
        initiative.recalculate_status(has_allocations=has_allocations)
        assert initiative.status is status

    def test_in_progress_that_loses_everything_stays_in_progress(
        self, clock: FrozenClock
    ) -> None:
        """§6.3: se é para parar, o caminho é DEPRIORITIZED, à mão."""
        initiative = make(clock, S.IN_PROGRESS)
        initiative.recalculate_status(has_allocations=False)
        assert initiative.status is S.IN_PROGRESS

    def test_it_is_idempotent(self, clock: FrozenClock) -> None:
        initiative = make(clock, S.BACKLOG)
        initiative.recalculate_status(has_allocations=True)
        initiative.recalculate_status(has_allocations=True)
        assert initiative.status is S.PLANNED


class TestChangeStatus:
    def test_a_valid_transition(self, clock: FrozenClock) -> None:
        initiative = make(clock, S.PLANNED)
        initiative.change_status(S.IN_PROGRESS)
        assert initiative.status is S.IN_PROGRESS

    def test_a_transition_to_the_same_status_is_a_no_op(
        self, clock: FrozenClock
    ) -> None:
        initiative = make(clock, S.DONE)
        initiative.change_status(S.DONE)
        assert initiative.status is S.DONE

    @pytest.mark.parametrize(
        ("current", "requested"),
        [
            (S.PLANNED, S.BACKLOG),
            (S.IN_PROGRESS, S.BACKLOG),
            (S.BACKLOG, S.PLANNED),
            (S.DONE, S.IN_PROGRESS),
            (S.CANCELLED, S.PLANNED),
            (S.BACKLOG, S.DONE),
        ],
    )
    def test_an_invalid_transition_is_an_error(
        self, clock: FrozenClock, current: InitiativeStatus, requested: InitiativeStatus
    ) -> None:
        initiative = make(clock, current)
        with pytest.raises(InvalidStatusTransition) as excinfo:
            initiative.change_status(requested)
        assert excinfo.value.details["current"] == current.value
        assert excinfo.value.details["requested"] == requested.value
        assert initiative.status is current

    def test_resuming_from_deprioritized_is_manual(self, clock: FrozenClock) -> None:
        initiative = make(clock, S.DEPRIORITIZED)
        initiative.change_status(S.IN_PROGRESS)
        assert initiative.status is S.IN_PROGRESS


class TestAcceptsAllocation:
    @pytest.mark.parametrize(
        "status", [S.BACKLOG, S.PLANNED, S.IN_PROGRESS, S.DEPRIORITIZED]
    )
    def test_it_accepts_allocation(
        self, clock: FrozenClock, status: InitiativeStatus
    ) -> None:
        make(clock, status).ensure_accepts_allocation()

    @pytest.mark.parametrize("status", [S.DONE, S.CANCELLED])
    def test_a_terminal_status_refuses_allocation(
        self, clock: FrozenClock, status: InitiativeStatus
    ) -> None:
        initiative = make(clock, status)
        with pytest.raises(InitiativeNotAllocatable):
            initiative.ensure_accepts_allocation()

    def test_deprioritized_accepts_allocation_and_stays_deprioritized(
        self, clock: FrozenClock
    ) -> None:
        """RN7: retomar é decisão manual, não efeito de arrastar uma barra."""
        initiative = make(clock, S.DEPRIORITIZED)
        initiative.ensure_accepts_allocation()
        initiative.recalculate_status(has_allocations=True)
        assert initiative.status is S.DEPRIORITIZED
