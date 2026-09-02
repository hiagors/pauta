"""Use cases de sprint (§6.6, RN10, RN12). Não existe exclusão (D13)."""

from datetime import date

import pytest

from app.application.dto.sprints import CreateSprintInput
from app.application.use_cases.sprints.create import CreateSprint
from app.application.use_cases.sprints.create_next import (
    CreateNextSprint,
    PreviewNextSprint,
)
from app.application.use_cases.sprints.list import ListSprints
from app.domain.entities.sprint import Sprint
from app.domain.errors import (
    InvalidSprintDates,
    SprintNotFound,
    SprintNumberGap,
    SprintNumberTaken,
    SprintOverlap,
)
from tests.application.conftest import Fakes, World
from tests.domain.conftest import FrozenClock


def test_create_the_first_sprint_with_the_real_number(fakes: Fakes) -> None:
    """O time cadastra a primeira com o número que ela tem na vida real."""
    view = fakes.use_case(CreateSprint).execute(
        CreateSprintInput(
            number=18, start_date=date(2026, 8, 31), end_date=date(2026, 9, 11)
        )
    )

    assert view.number == 18
    assert view.is_current is True


def test_create_sprint_without_number_continues_the_sequence(
    world: World, fakes: Fakes
) -> None:
    world.sprints(18, 18)

    view = fakes.use_case(CreateSprint).execute(
        CreateSprintInput(start_date=date(2026, 9, 14), end_date=date(2026, 9, 25))
    )

    assert view.number == 19
    assert view.is_current is False


def test_create_sprint_refuses_a_gap_in_the_numbering(
    world: World, fakes: Fakes
) -> None:
    world.sprints(18, 18)

    with pytest.raises(SprintNumberGap):
        fakes.use_case(CreateSprint).execute(
            CreateSprintInput(
                number=20, start_date=date(2026, 9, 14), end_date=date(2026, 9, 25)
            )
        )


def test_create_sprint_refuses_a_repeated_number(world: World, fakes: Fakes) -> None:
    world.sprints(18, 18)

    with pytest.raises(SprintNumberTaken):
        fakes.use_case(CreateSprint).execute(
            CreateSprintInput(
                number=18, start_date=date(2026, 9, 14), end_date=date(2026, 9, 25)
            )
        )


def test_create_sprint_refuses_an_overlap(world: World, fakes: Fakes) -> None:
    world.sprints(18, 18)

    with pytest.raises(SprintOverlap):
        fakes.use_case(CreateSprint).execute(
            CreateSprintInput(
                number=19, start_date=date(2026, 9, 7), end_date=date(2026, 9, 18)
            )
        )


def test_create_sprint_refuses_inverted_dates(fakes: Fakes) -> None:
    with pytest.raises(InvalidSprintDates):
        fakes.use_case(CreateSprint).execute(
            CreateSprintInput(
                number=18, start_date=date(2026, 9, 11), end_date=date(2026, 8, 31)
            )
        )


def test_preview_next_sprint_starts_on_the_monday_after_the_last_end(
    world: World, fakes: Fakes
) -> None:
    """RN10: número + 1, próxima segunda depois do fim, e mais 11 dias."""
    world.sprints(18, 18)

    proposal = fakes.use_case(PreviewNextSprint).execute()

    assert proposal.number == 19
    assert proposal.start_date == date(2026, 9, 14)
    assert proposal.end_date == date(2026, 9, 25)
    assert proposal.start_date.weekday() == 0


def test_preview_next_sprint_without_any_sprint_is_not_found(fakes: Fakes) -> None:
    with pytest.raises(SprintNotFound):
        fakes.use_case(PreviewNextSprint).execute()


def test_create_next_sprint_persists_the_proposal(world: World, fakes: Fakes) -> None:
    world.sprints(18, 18)

    view = fakes.use_case(CreateNextSprint).execute()

    assert (view.number, view.start_date, view.end_date) == (
        19,
        date(2026, 9, 14),
        date(2026, 9, 25),
    )
    assert fakes.sprints.get_by_number(19) is not None


def test_list_sprints_marks_the_current_one(world: World, fakes: Fakes) -> None:
    world.sprints(18, 22)

    views = fakes.use_case(ListSprints).execute()

    assert [view.number for view in views] == [18, 19, 20, 21, 22]
    assert [view.number for view in views if view.is_current] == [18]


def test_list_sprints_keeps_is_current_out_of_the_asked_window(
    world: World, fakes: Fakes
) -> None:
    """A janela não promove ninguém: a atual é a do conjunto inteiro (RN12)."""
    world.sprints(18, 22)

    views = fakes.use_case(ListSprints).execute(number_from=20, number_to=22)

    assert [view.number for view in views] == [20, 21, 22]
    assert all(not view.is_current for view in views)


def test_the_current_sprint_survives_a_calendar_gap() -> None:
    """RN12: uma sprint só termina de verdade quando a próxima começa.

    15/09/2026 cai na folga entre o fim da 18 (11/09) e o começo da 19 (21/09).
    O sistema continua com a 18 como atual, e não fica sem sprint atual.
    """
    fakes = Fakes(clock=FrozenClock(date(2026, 9, 15)))
    fakes.sprints.add(
        Sprint.create(
            number=18, start_date=date(2026, 8, 31), end_date=date(2026, 9, 11)
        )
    )
    fakes.sprints.add(
        Sprint.create(
            number=19, start_date=date(2026, 9, 21), end_date=date(2026, 10, 2)
        )
    )

    views = fakes.use_case(ListSprints).execute()

    assert [view.number for view in views if view.is_current] == [18]


def test_no_sprint_is_current_before_the_first_one_starts() -> None:
    fakes = Fakes(clock=FrozenClock(date(2026, 8, 1)))
    World(fakes=fakes).sprints(18, 19)

    views = fakes.use_case(ListSprints).execute()

    assert all(not view.is_current for view in views)
