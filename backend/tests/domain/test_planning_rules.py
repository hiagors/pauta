"""Calendário de sprints, alocação em intervalo e alocação efetiva."""

from datetime import date, timedelta

import pytest

from app.domain.entities.sprint import Sprint
from app.domain.errors import (
    AllocationConflict,
    SprintNotFound,
    SprintNumberGap,
    SprintNumberTaken,
    SprintOverlap,
)
from app.domain.services import planning_rules as rules
from app.domain.value_objects.assignee import Assignee
from app.domain.value_objects.sprint_range import SprintRange
from tests.domain.conftest import (
    make_ref,
    make_sprint,
    member_alloc,
    membership,
    sprint_18_to_22,
    squad_alloc,
    uid,
)

ALFA = uid(1)
BETA = uid(2)
ANA = uid(10)
CARLA = uid(11)
BRUNO = uid(12)

AURORA = make_ref(50, "Catálogo V1", project_seed=90, project_name="Aurora")
ENVIO = make_ref(51, "Serviço de Envio", project_seed=90, project_name="Aurora")
PORTAL = make_ref(52, "Portal Externo", project_seed=91, project_name="Boreal")
PLANTAO = make_ref(
    53, "Sustentação", project_seed=92, project_name="Plantão", reserve=True
)


class TestSprintSequence:
    def test_the_real_world_data_is_valid(self) -> None:
        rules.validate_sprint_sequence(sprint_18_to_22())

    def test_an_empty_set_is_valid(self) -> None:
        rules.validate_sprint_sequence([])

    def test_a_hole_in_the_numbering_is_an_error(self) -> None:
        sprints = [
            make_sprint(18, date(2026, 8, 31)),
            make_sprint(20, date(2026, 9, 28)),
        ]
        with pytest.raises(SprintNumberGap) as excinfo:
            rules.validate_sprint_sequence(sprints)
        assert excinfo.value.details == {"expected": 19, "received": 20}

    def test_a_repeated_number_is_an_error(self) -> None:
        sprints = [
            make_sprint(18, date(2026, 8, 31)),
            Sprint.create(
                number=18,
                start_date=date(2026, 9, 14),
                end_date=date(2026, 9, 25),
                id=uid(999),
            ),
        ]
        with pytest.raises(SprintNumberTaken):
            rules.validate_sprint_sequence(sprints)

    def test_the_next_start_must_be_after_the_previous_end(self) -> None:
        sprints = [
            make_sprint(18, date(2026, 8, 31)),
            make_sprint(19, date(2026, 9, 7)),
        ]
        with pytest.raises(SprintOverlap):
            rules.validate_sprint_sequence(sprints)

    def test_the_input_order_does_not_matter(self) -> None:
        rules.validate_sprint_sequence(list(reversed(sprint_18_to_22())))

    def test_the_first_sprint_does_not_have_to_be_number_one(self) -> None:
        """O time cadastra a 18, que é a que existe na vida real."""
        rules.ensure_can_add_sprint([], make_sprint(18, date(2026, 8, 31)))

    def test_the_new_sprint_must_be_the_next_one(self) -> None:
        existing = sprint_18_to_22()
        rules.ensure_can_add_sprint(existing, make_sprint(23, date(2026, 11, 9)))
        with pytest.raises(SprintNumberGap):
            rules.ensure_can_add_sprint(existing, make_sprint(24, date(2026, 11, 23)))


class TestCurrentSprint:
    def test_it_is_the_latest_start_that_has_already_passed(self) -> None:
        sprints = sprint_18_to_22()
        current = rules.current_sprint(sprints, date(2026, 9, 2))
        assert current is not None
        assert current.number == 18

    def test_on_the_first_day_the_sprint_is_already_the_current_one(self) -> None:
        sprints = sprint_18_to_22()
        current = rules.current_sprint(sprints, date(2026, 9, 14))
        assert current is not None
        assert current.number == 19

    def test_a_calendar_gap_does_not_leave_the_system_without_a_current_sprint(
        self,
    ) -> None:
        """RN12: uma sprint só termina de verdade quando a próxima começa."""
        sprints = [
            make_sprint(18, date(2026, 8, 31)),
            make_sprint(19, date(2026, 9, 21)),
        ]
        current = rules.current_sprint(sprints, date(2026, 9, 16))
        assert current is not None
        assert current.number == 18
        assert current.end_date < date(2026, 9, 16)

    def test_with_no_sprint_started_there_is_no_current_sprint(self) -> None:
        sprints = sprint_18_to_22()
        assert rules.current_sprint(sprints, date(2026, 8, 1)) is None
        assert all(not rules.is_current(s, sprints, date(2026, 8, 1)) for s in sprints)

    def test_is_current_marks_one_and_only_one(self) -> None:
        sprints = sprint_18_to_22()
        today = date(2026, 9, 20)
        marked = [s for s in sprints if rules.is_current(s, sprints, today)]
        assert [s.number for s in marked] == [19]


class TestNextSprint:
    def test_the_proposal_follows_the_pattern_of_rn10(self) -> None:
        proposal = rules.propose_next_sprint(sprint_18_to_22())
        assert proposal.number == 23
        assert proposal.start_date == date(2026, 11, 9)
        assert proposal.start_date.weekday() == 0
        assert (proposal.end_date - proposal.start_date).days == 11
        assert proposal.end_date.weekday() == 4

    def test_the_following_monday_is_strictly_after(self) -> None:
        assert rules.next_monday_after(date(2026, 9, 11)) == date(2026, 9, 14)
        assert rules.next_monday_after(date(2026, 9, 14)) == date(2026, 9, 21)

    def test_the_proposal_does_not_overlap_the_last_sprint(self) -> None:
        sprints = sprint_18_to_22()
        proposal = rules.propose_next_sprint(sprints)
        rules.ensure_can_add_sprint(
            sprints,
            Sprint.create(
                number=proposal.number,
                start_date=proposal.start_date,
                end_date=proposal.end_date,
                id=uid(777),
            ),
        )

    def test_without_any_sprint_there_is_nothing_to_propose(self) -> None:
        with pytest.raises(SprintNotFound):
            rules.propose_next_sprint([])


class TestGridWindow:
    def test_the_civil_quarter_of_today(self) -> None:
        assert rules.civil_quarter_bounds(date(2026, 9, 2)) == (
            date(2026, 7, 1),
            date(2026, 9, 30),
        )
        assert rules.civil_quarter_bounds(date(2026, 1, 1)) == (
            date(2026, 1, 1),
            date(2026, 3, 31),
        )
        assert rules.civil_quarter_bounds(date(2026, 12, 31)) == (
            date(2026, 10, 1),
            date(2026, 12, 31),
        )

    def test_the_default_grid_brings_whoever_intersects_the_quarter(self) -> None:
        sprints = sprint_18_to_22()
        window = rules.sprints_in_quarter(sprints, date(2026, 9, 2))
        assert [s.number for s in window] == [18, 19, 20]

    def test_a_sprint_across_the_quarter_boundary_is_in_both(self) -> None:
        across_quarters = make_sprint(21, date(2026, 9, 28))
        assert across_quarters.end_date == date(2026, 10, 9)
        assert rules.sprints_in_quarter([across_quarters], date(2026, 9, 2))
        assert rules.sprints_in_quarter([across_quarters], date(2026, 10, 15))


class TestAllocationPlan:
    def make_range(self) -> SprintRange:
        return SprintRange(18, 22)

    def test_the_whole_range_is_free(self) -> None:
        plan = rules.plan_allocation(
            initiative_id=AURORA.id,
            sprint_range=self.make_range(),
            assignee=Assignee.for_squad(ALFA),
            existing_sprint_numbers={18, 19, 20, 21, 22},
            occupied={},
        )
        assert plan.to_create == (18, 19, 20, 21, 22)
        assert plan.already_existing == ()
        assert plan.missing_sprint_numbers == ()

    def test_rn1_allocating_is_idempotent(self) -> None:
        squad = Assignee.for_squad(ALFA)
        plan = rules.plan_allocation(
            initiative_id=AURORA.id,
            sprint_range=self.make_range(),
            assignee=squad,
            existing_sprint_numbers={18, 19, 20, 21, 22},
            occupied={19: squad, 20: squad},
        )
        assert plan.to_create == (18, 21, 22)
        assert plan.already_existing == (19, 20)

    def test_rn5_a_missing_sprint_does_not_break_the_operation(self) -> None:
        plan = rules.plan_allocation(
            initiative_id=AURORA.id,
            sprint_range=self.make_range(),
            assignee=Assignee.for_squad(ALFA),
            existing_sprint_numbers={18, 19, 20},
            occupied={},
        )
        assert plan.to_create == (18, 19, 20)
        assert plan.missing_sprint_numbers == (21, 22)

    def test_rn8_another_assignee_in_the_same_cell_is_a_conflict(self) -> None:
        with pytest.raises(AllocationConflict) as excinfo:
            rules.plan_allocation(
                initiative_id=AURORA.id,
                sprint_range=SprintRange(18, 20),
                assignee=Assignee.for_squad(ALFA),
                existing_sprint_numbers={18, 19, 20},
                occupied={19: Assignee.for_squad(BETA)},
            )
        details = excinfo.value.details
        assert details["sprint_number"] == 19
        assert details["occupant_kind"] == "squad"
        assert details["occupant_id"] == str(BETA)

    def test_a_member_holding_the_cell_of_a_squad_is_also_a_conflict(self) -> None:
        with pytest.raises(AllocationConflict) as excinfo:
            rules.plan_allocation(
                initiative_id=AURORA.id,
                sprint_range=SprintRange(19, 19),
                assignee=Assignee.for_squad(ALFA),
                existing_sprint_numbers={19},
                occupied={19: Assignee.for_member(BRUNO)},
            )
        assert excinfo.value.details["occupant_kind"] == "member"


class TestEffectiveAllocation:
    def snapshot(self) -> rules.PlanningSnapshot:
        return rules.PlanningSnapshot(
            sprint_numbers=(18, 19, 20),
            allocations=(
                squad_alloc(19, AURORA, ALFA),
                squad_alloc(19, PORTAL, BETA),
                member_alloc(19, ENVIO, BRUNO),
                squad_alloc(20, PLANTAO, ALFA),
            ),
            memberships=(
                membership(19, ALFA, ANA),
                membership(19, BETA, ANA),
                membership(19, ALFA, CARLA),
                membership(20, ALFA, CARLA),
            ),
            squads={ALFA: "Alfa", BETA: "Beta"},
            members={ANA: "Ana", CARLA: "Carla", BRUNO: "Bruno"},
            current_sprint_number=19,
        )

    def test_the_union_of_direct_and_via_squad(self) -> None:
        effective = rules.effective_initiatives(
            self.snapshot(),
            member_id=ANA,
            sprint_number=19,
            include_capacity_reserve=False,
        )
        assert {ref.id for ref in effective} == {AURORA.id, PORTAL.id}

    def test_a_direct_allocation_counts(self) -> None:
        effective = rules.effective_initiatives(
            self.snapshot(),
            member_id=BRUNO,
            sprint_number=19,
            include_capacity_reserve=False,
        )
        assert [ref.id for ref in effective] == [ENVIO.id]

    def test_the_composition_is_per_sprint_and_does_not_leak(self) -> None:
        effective = rules.effective_initiatives(
            self.snapshot(),
            member_id=ANA,
            sprint_number=18,
            include_capacity_reserve=False,
        )
        assert effective == ()

    def test_capacity_reserve_leaves_the_set_before_the_conflict_check(self) -> None:
        snapshot = self.snapshot()
        without_reserve = rules.effective_initiatives(
            snapshot,
            member_id=CARLA,
            sprint_number=20,
            include_capacity_reserve=False,
        )
        with_reserve = rules.effective_initiatives(
            snapshot,
            member_id=CARLA,
            sprint_number=20,
            include_capacity_reserve=True,
        )
        assert without_reserve == ()
        assert [ref.id for ref in with_reserve] == [PLANTAO.id]

    def test_the_initiatives_of_a_squad(self) -> None:
        initiatives = rules.squad_initiatives(
            self.snapshot(),
            squad_id=ALFA,
            sprint_number=19,
            include_capacity_reserve=False,
        )
        assert [ref.id for ref in initiatives] == [AURORA.id]

    def test_the_output_is_sorted_and_without_repetition(self) -> None:
        snapshot = rules.PlanningSnapshot(
            sprint_numbers=(19,),
            allocations=(
                squad_alloc(19, PORTAL, ALFA),
                squad_alloc(19, AURORA, BETA),
                member_alloc(19, AURORA, ANA),
            ),
            memberships=(
                membership(19, ALFA, ANA),
                membership(19, BETA, ANA),
            ),
            squads={ALFA: "Alfa", BETA: "Beta"},
            members={ANA: "Ana"},
        )
        effective = rules.effective_initiatives(
            snapshot, member_id=ANA, sprint_number=19, include_capacity_reserve=False
        )
        assert [ref.label for ref in effective] == [
            "Aurora / Catálogo V1",
            "Boreal / Portal Externo",
        ]


class TestIdleFrom:
    def test_it_starts_at_the_current_sprint(self) -> None:
        snapshot = rules.PlanningSnapshot(
            sprint_numbers=(18, 19, 20), current_sprint_number=19
        )
        assert snapshot.idle_from == 19

    def test_without_a_current_sprint_the_whole_window_is_future(self) -> None:
        snapshot = rules.PlanningSnapshot(sprint_numbers=(18, 19, 20))
        assert snapshot.idle_from == 18

    def test_an_empty_window(self) -> None:
        assert rules.PlanningSnapshot(sprint_numbers=()).idle_from is None


def test_the_default_length_matches_the_real_world_data() -> None:
    start = date(2026, 8, 31)
    assert start + timedelta(days=rules.DEFAULT_SPRINT_LENGTH_DAYS) == date(2026, 9, 11)
