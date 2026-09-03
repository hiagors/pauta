"""Consolidação de células em barras do Gantt."""

from app.domain.services.bar_consolidation import AllocationCell, consolidate_bars
from app.domain.value_objects.assignee import Assignee
from tests.domain.conftest import uid

ALFA = Assignee.for_squad(uid(1))
BETA = Assignee.for_squad(uid(2))
BRUNO = Assignee.for_member(uid(10))


def cell(sprint_number: int, assignee: Assignee) -> AllocationCell:
    return AllocationCell(
        allocation_id=uid(100 + sprint_number),
        sprint_number=sprint_number,
        assignee=assignee,
    )


def test_contiguous_sprints_of_the_same_assignee_become_one_bar() -> None:
    bars = consolidate_bars([cell(n, ALFA) for n in (18, 19, 20, 21, 22)])
    assert len(bars) == 1
    assert (bars[0].from_sprint_number, bars[0].to_sprint_number) == (18, 22)
    assert len(bars[0].allocation_ids) == 5


def test_the_input_order_does_not_matter() -> None:
    bars = consolidate_bars([cell(n, ALFA) for n in (20, 18, 22, 19, 21)])
    assert len(bars) == 1
    assert bars[0].allocation_ids == tuple(uid(100 + n) for n in (18, 19, 20, 21, 22))


def test_a_pause_in_the_middle_yields_two_bars() -> None:
    bars = consolidate_bars([cell(n, ALFA) for n in (18, 19, 21, 22)])
    assert [(bar.from_sprint_number, bar.to_sprint_number) for bar in bars] == [
        (18, 19),
        (21, 22),
    ]


def test_a_change_of_assignee_yields_two_bars() -> None:
    """RN3: uma iniciativa pode ter responsáveis diferentes em sprints diferentes."""
    bars = consolidate_bars([cell(18, ALFA), cell(19, ALFA), cell(20, BETA)])
    assert len(bars) == 2
    assert bars[0].assignee == ALFA
    assert (bars[0].from_sprint_number, bars[0].to_sprint_number) == (18, 19)
    assert bars[1].assignee == BETA
    assert (bars[1].from_sprint_number, bars[1].to_sprint_number) == (20, 20)


def test_a_squad_and_a_member_never_merge() -> None:
    bars = consolidate_bars([cell(18, ALFA), cell(19, BRUNO)])
    assert len(bars) == 2


def test_a_single_cell() -> None:
    bars = consolidate_bars([cell(19, BRUNO)])
    assert (bars[0].from_sprint_number, bars[0].to_sprint_number) == (19, 19)


def test_without_a_cell_there_is_no_bar() -> None:
    assert consolidate_bars([]) == []


def test_the_bars_of_one_row_never_overlap() -> None:
    bars = consolidate_bars([cell(18, ALFA), cell(19, BETA), cell(20, ALFA)])
    bounds = [(bar.from_sprint_number, bar.to_sprint_number) for bar in bars]
    for anterior, seguinte in zip(bounds, bounds[1:], strict=False):
        assert anterior[1] < seguinte[0]
