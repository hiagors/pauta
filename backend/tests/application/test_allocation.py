"""Alocação em intervalo e desalocação (§7.1, RN1-RN9)."""

import pytest

from app.application.dto.allocations import (
    AllocateRangeInput,
    AllocationFilter,
    DeallocateRangeInput,
)
from app.application.use_cases.planning.allocate_range import AllocateRange
from app.application.use_cases.planning.deallocate import (
    DeallocateCell,
    DeallocateRange,
)
from app.application.use_cases.planning.list_allocations import ListAllocations
from app.domain.errors import (
    AllocationConflict,
    AllocationNotFound,
    AmbiguousAssignee,
    AssigneeRequired,
    InitiativeNotAllocatable,
    InitiativeNotFound,
    InvalidSprintRange,
    MemberNotFound,
    SquadNotFound,
)
from app.domain.value_objects.alert import AlertType
from app.domain.value_objects.initiative_status import InitiativeStatus
from tests.application.conftest import Fakes, World
from tests.domain.conftest import uid


def test_allocating_a_range_creates_one_cell_per_sprint(
    world: World, fakes: Fakes
) -> None:
    """RN1: uma `Allocation` por sprint do intervalo."""
    world.sprints(18, 22)
    initiative = world.initiative(world.project("Aurora"), "Catálogo V1")
    squad = world.squad("Alfa")

    result = fakes.use_case(AllocateRange).execute(
        AllocateRangeInput(
            initiative_id=initiative.id,
            squad_id=squad.id,
            from_sprint_number=18,
            to_sprint_number=22,
        )
    )

    assert [cell.sprint_number for cell in result.created] == [18, 19, 20, 21, 22]
    assert result.already_existed == ()
    assert result.missing_sprint_numbers == ()
    assert fakes.allocations.count_by_initiative(initiative.id) == 5


def test_the_first_allocation_moves_backlog_to_planned(
    world: World, fakes: Fakes
) -> None:
    """RN2, e só de BACKLOG para PLANNED."""
    world.sprints(18, 18)
    initiative = world.initiative(world.project("Aurora"), "V1")

    result = fakes.use_case(AllocateRange).execute(
        AllocateRangeInput(
            initiative_id=initiative.id,
            squad_id=world.squad("Alfa").id,
            from_sprint_number=18,
            to_sprint_number=18,
        )
    )

    assert result.initiative_status is InitiativeStatus.PLANNED
    stored = fakes.initiatives.get(initiative.id)
    assert stored is not None
    assert stored.status is InitiativeStatus.PLANNED


def test_allocating_twice_is_idempotent(world: World, fakes: Fakes) -> None:
    """RN1: célula do mesmo responsável volta em `already_existed`."""
    world.sprints(18, 20)
    initiative = world.initiative(world.project("Aurora"), "V1")
    squad = world.squad("Alfa")
    allocate = fakes.use_case(AllocateRange)
    payload = AllocateRangeInput(
        initiative_id=initiative.id,
        squad_id=squad.id,
        from_sprint_number=18,
        to_sprint_number=19,
    )
    allocate.execute(payload)

    again = allocate.execute(payload)

    assert again.created == ()
    assert [cell.sprint_number for cell in again.already_existed] == [18, 19]
    assert fakes.allocations.count_by_initiative(initiative.id) == 2


def test_a_missing_sprint_does_not_break_the_operation(
    world: World, fakes: Fakes
) -> None:
    """RN5: cria o que existe e relata o que falta cadastrar."""
    world.sprints(18, 20)
    initiative = world.initiative(world.project("Aurora"), "V1")

    result = fakes.use_case(AllocateRange).execute(
        AllocateRangeInput(
            initiative_id=initiative.id,
            squad_id=world.squad("Alfa").id,
            from_sprint_number=19,
            to_sprint_number=22,
        )
    )

    assert [cell.sprint_number for cell in result.created] == [19, 20]
    assert result.missing_sprint_numbers == (21, 22)
    assert result.initiative_status is InitiativeStatus.PLANNED


def test_a_second_assignee_in_the_same_cell_is_a_conflict(
    world: World, fakes: Fakes
) -> None:
    """RN8: unicidade `(initiative_id, sprint_id)`."""
    world.sprints(18, 19)
    initiative = world.initiative(world.project("Aurora"), "V1")
    allocate = fakes.use_case(AllocateRange)
    allocate.execute(
        AllocateRangeInput(
            initiative_id=initiative.id,
            squad_id=world.squad("Alfa").id,
            from_sprint_number=18,
            to_sprint_number=18,
        )
    )

    with pytest.raises(AllocationConflict) as raised:
        allocate.execute(
            AllocateRangeInput(
                initiative_id=initiative.id,
                squad_id=world.squad("Beta").id,
                from_sprint_number=18,
                to_sprint_number=18,
            )
        )

    assert raised.value.details["sprint_number"] == 18
    assert raised.value.details["occupant_kind"] == "squad"
    assert fakes.allocations.count_by_initiative(initiative.id) == 1


def test_the_conflict_does_not_create_the_cells_before_it(
    world: World, fakes: Fakes
) -> None:
    """O plano é decidido inteiro antes de gravar: ou vai tudo, ou nada."""
    world.sprints(18, 20)
    initiative = world.initiative(world.project("Aurora"), "V1")
    allocate = fakes.use_case(AllocateRange)
    allocate.execute(
        AllocateRangeInput(
            initiative_id=initiative.id,
            squad_id=world.squad("Alfa").id,
            from_sprint_number=20,
            to_sprint_number=20,
        )
    )

    with pytest.raises(AllocationConflict):
        allocate.execute(
            AllocateRangeInput(
                initiative_id=initiative.id,
                member_id=world.member("Ana").id,
                from_sprint_number=18,
                to_sprint_number=20,
            )
        )

    assert fakes.allocations.count_by_initiative(initiative.id) == 1


def test_the_same_initiative_can_change_assignee_between_sprints(
    world: World, fakes: Fakes
) -> None:
    """RN3."""
    world.sprints(18, 20)
    initiative = world.initiative(world.project("Aurora"), "V1")
    allocate = fakes.use_case(AllocateRange)

    allocate.execute(
        AllocateRangeInput(
            initiative_id=initiative.id,
            squad_id=world.squad("Alfa").id,
            from_sprint_number=18,
            to_sprint_number=19,
        )
    )
    allocate.execute(
        AllocateRangeInput(
            initiative_id=initiative.id,
            member_id=world.member("Ana").id,
            from_sprint_number=20,
            to_sprint_number=20,
        )
    )

    views = fakes.use_case(ListAllocations).execute()
    assert [(view.sprint_number, view.squad_id is not None) for view in views] == [
        (18, True),
        (19, True),
        (20, False),
    ]


def test_a_done_initiative_refuses_new_allocation(world: World, fakes: Fakes) -> None:
    """RN7. As alocações existentes permanecem, como histórico."""
    world.sprints(18, 18)
    initiative = world.initiative(
        world.project("Aurora"), "V1", status=InitiativeStatus.DONE
    )

    with pytest.raises(InitiativeNotAllocatable):
        fakes.use_case(AllocateRange).execute(
            AllocateRangeInput(
                initiative_id=initiative.id,
                squad_id=world.squad("Alfa").id,
                from_sprint_number=18,
                to_sprint_number=18,
            )
        )


def test_a_deprioritized_initiative_accepts_allocation_and_stays(
    world: World, fakes: Fakes
) -> None:
    """RN7: retomar é decisão manual, não efeito de arrastar uma barra."""
    world.sprints(18, 18)
    initiative = world.initiative(
        world.project("Aurora"), "V1", status=InitiativeStatus.DEPRIORITIZED
    )

    result = fakes.use_case(AllocateRange).execute(
        AllocateRangeInput(
            initiative_id=initiative.id,
            squad_id=world.squad("Alfa").id,
            from_sprint_number=18,
            to_sprint_number=18,
        )
    )

    assert result.initiative_status is InitiativeStatus.DEPRIORITIZED


def test_allocation_needs_exactly_one_assignee(world: World, fakes: Fakes) -> None:
    world.sprints(18, 18)
    initiative = world.initiative(world.project("Aurora"), "V1")
    allocate = fakes.use_case(AllocateRange)

    with pytest.raises(AssigneeRequired):
        allocate.execute(
            AllocateRangeInput(
                initiative_id=initiative.id,
                from_sprint_number=18,
                to_sprint_number=18,
            )
        )

    with pytest.raises(AmbiguousAssignee):
        allocate.execute(
            AllocateRangeInput(
                initiative_id=initiative.id,
                squad_id=world.squad("Alfa").id,
                member_id=world.member("Ana").id,
                from_sprint_number=18,
                to_sprint_number=18,
            )
        )


def test_allocation_reports_unknown_references(world: World, fakes: Fakes) -> None:
    world.sprints(18, 18)
    initiative = world.initiative(world.project("Aurora"), "V1")
    allocate = fakes.use_case(AllocateRange)

    with pytest.raises(InitiativeNotFound):
        allocate.execute(
            AllocateRangeInput(
                initiative_id=uid(999),
                squad_id=world.squad("Alfa").id,
                from_sprint_number=18,
                to_sprint_number=18,
            )
        )
    with pytest.raises(SquadNotFound):
        allocate.execute(
            AllocateRangeInput(
                initiative_id=initiative.id,
                squad_id=uid(998),
                from_sprint_number=18,
                to_sprint_number=18,
            )
        )
    with pytest.raises(MemberNotFound):
        allocate.execute(
            AllocateRangeInput(
                initiative_id=initiative.id,
                member_id=uid(997),
                from_sprint_number=18,
                to_sprint_number=18,
            )
        )


def test_allocation_refuses_an_inverted_range(world: World, fakes: Fakes) -> None:
    world.sprints(18, 20)
    initiative = world.initiative(world.project("Aurora"), "V1")

    with pytest.raises(InvalidSprintRange):
        fakes.use_case(AllocateRange).execute(
            AllocateRangeInput(
                initiative_id=initiative.id,
                squad_id=world.squad("Alfa").id,
                from_sprint_number=20,
                to_sprint_number=18,
            )
        )


def test_the_allocation_response_carries_the_current_alerts(
    world: World, fakes: Fakes
) -> None:
    """§8: o estado atual dos alertas das sprints tocadas, não um diff."""
    world.sprints(18, 19)
    aurora = world.project("Aurora")
    boreal = world.project("Boreal")
    first = world.initiative(aurora, "Catálogo")
    second = world.initiative(boreal, "Portal Externo")
    squad = world.squad("Alfa")
    world.join(squad, world.member("Ana"), 19)
    world.allocate(first, 19, squad=squad)

    result = fakes.use_case(AllocateRange).execute(
        AllocateRangeInput(
            initiative_id=second.id,
            squad_id=squad.id,
            from_sprint_number=19,
            to_sprint_number=19,
        )
    )

    overloaded = [
        alert for alert in result.alerts if alert.type is AlertType.SQUAD_OVERLOADED
    ]
    assert len(overloaded) == 1
    assert overloaded[0].sprint_number == 19
    assert overloaded[0].is_muted is False


def test_deallocating_the_range_sends_planned_back_to_backlog(
    world: World, fakes: Fakes
) -> None:
    """RN2 na volta: perder todas as alocações devolve PLANNED a BACKLOG."""
    world.sprints(18, 20)
    initiative = world.initiative(
        world.project("Aurora"), "V1", status=InitiativeStatus.PLANNED
    )
    world.allocate(initiative, 18, 19, squad=world.squad("Alfa"))

    result = fakes.use_case(DeallocateRange).execute(
        DeallocateRangeInput(
            initiative_id=initiative.id, from_sprint_number=18, to_sprint_number=20
        )
    )

    assert [cell.sprint_number for cell in result.removed] == [18, 19]
    assert result.initiative_status is InitiativeStatus.BACKLOG
    assert fakes.allocations.count_by_initiative(initiative.id) == 0


def test_deallocating_part_of_the_range_keeps_planned(
    world: World, fakes: Fakes
) -> None:
    world.sprints(18, 20)
    initiative = world.initiative(
        world.project("Aurora"), "V1", status=InitiativeStatus.PLANNED
    )
    world.allocate(initiative, 18, 19, 20, squad=world.squad("Alfa"))

    result = fakes.use_case(DeallocateRange).execute(
        DeallocateRangeInput(
            initiative_id=initiative.id, from_sprint_number=18, to_sprint_number=19
        )
    )

    assert result.initiative_status is InitiativeStatus.PLANNED
    assert fakes.allocations.count_by_initiative(initiative.id) == 1


def test_an_in_progress_initiative_stays_in_progress_without_allocation(
    world: World, fakes: Fakes
) -> None:
    """§6.3: nada volta para BACKLOG depois de ter começado."""
    world.sprints(18, 18)
    initiative = world.initiative(
        world.project("Aurora"), "V1", status=InitiativeStatus.IN_PROGRESS
    )
    world.allocate(initiative, 18, squad=world.squad("Alfa"))

    result = fakes.use_case(DeallocateRange).execute(
        DeallocateRangeInput(
            initiative_id=initiative.id, from_sprint_number=18, to_sprint_number=18
        )
    )

    assert result.initiative_status is InitiativeStatus.IN_PROGRESS


def test_deallocating_one_cell(world: World, fakes: Fakes) -> None:
    """RN6: a célula única, para apagar um pedaço da barra."""
    world.sprints(18, 20)
    initiative = world.initiative(
        world.project("Aurora"), "V1", status=InitiativeStatus.PLANNED
    )
    cells = world.allocate(initiative, 18, 19, squad=world.squad("Alfa"))

    result = fakes.use_case(DeallocateCell).execute(cells[1].id)

    assert [cell.sprint_number for cell in result.removed] == [19]
    assert result.initiative_status is InitiativeStatus.PLANNED
    assert fakes.allocations.get(cells[1].id) is None
    assert fakes.allocations.get(cells[0].id) is not None


def test_deallocating_an_unknown_cell_is_not_found(fakes: Fakes) -> None:
    with pytest.raises(AllocationNotFound):
        fakes.use_case(DeallocateCell).execute(uid(999))


def test_deallocating_an_empty_range_is_an_empty_operation(
    world: World, fakes: Fakes
) -> None:
    world.sprints(18, 20)
    initiative = world.initiative(world.project("Aurora"), "V1")

    result = fakes.use_case(DeallocateRange).execute(
        DeallocateRangeInput(
            initiative_id=initiative.id, from_sprint_number=18, to_sprint_number=20
        )
    )

    assert result.removed == ()
    assert result.initiative_status is InitiativeStatus.BACKLOG


def test_list_allocations_filters_by_project_and_sprint_window(
    world: World, fakes: Fakes
) -> None:
    world.sprints(18, 22)
    aurora = world.project("Aurora")
    first = world.initiative(aurora, "V1")
    other = world.initiative(world.project("Boreal"), "Portal Externo")
    squad = world.squad("Alfa")
    world.allocate(first, 18, 19, squad=squad)
    world.allocate(other, 19, 20, squad=squad)

    listing = fakes.use_case(ListAllocations)
    assert [view.sprint_number for view in listing.execute()] == [18, 19, 19, 20]
    assert [
        view.sprint_number
        for view in listing.execute(AllocationFilter(project_id=aurora.id))
    ] == [18, 19]
    assert [
        view.sprint_number
        for view in listing.execute(AllocationFilter(sprint_from=19, sprint_to=19))
    ] == [19, 19]
    assert (
        listing.execute(AllocationFilter(project_id=aurora.id, initiative_id=other.id))
        == []
    )
