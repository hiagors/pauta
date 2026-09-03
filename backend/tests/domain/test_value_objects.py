"""Value objects: prioridade, cor, intervalo de sprints e responsável."""

import pytest

from app.domain.errors import (
    AmbiguousAssignee,
    AssigneeRequired,
    InvalidColor,
    InvalidSprintNumber,
    InvalidSprintRange,
)
from app.domain.value_objects.assignee import Assignee, AssigneeKind
from app.domain.value_objects.color import DEFAULT_PROJECT_COLOR, Color
from app.domain.value_objects.priority import Priority
from app.domain.value_objects.sprint_range import SprintRange
from tests.domain.conftest import uid


class TestPriority:
    def test_it_sorts_from_the_most_to_the_least_priority(self) -> None:
        ordered = sorted(Priority, key=lambda priority: priority.rank)
        assert ordered == [Priority.HIGH, Priority.MEDIUM, Priority.LOW]

    def test_it_travels_as_an_english_string(self) -> None:
        assert Priority.HIGH == "HIGH"


class TestColor:
    def test_it_normalizes_to_uppercase(self) -> None:
        assert Color("#0052cc").value == "#0052CC"

    @pytest.mark.parametrize("raw", ["0052CC", "#0052C", "#GGGGGG", "", "azul"])
    def test_it_refuses_an_invalid_format(self, raw: str) -> None:
        with pytest.raises(InvalidColor):
            Color(raw)

    def test_parsing_empty_or_none_returns_none(self) -> None:
        assert Color.parse(None) is None
        assert Color.parse("   ") is None

    def test_the_default_project_color(self) -> None:
        assert Color.default_project().value == DEFAULT_PROJECT_COLOR


class TestSprintRange:
    def test_the_range_is_inclusive_on_both_ends(self) -> None:
        interval = SprintRange(18, 22)
        assert interval.numbers == (18, 19, 20, 21, 22)
        assert list(interval) == [18, 19, 20, 21, 22]
        # `in` continua funcionando pelo `__iter__`: o `__contains__` explícito
        # que existia aqui dizia a mesma coisa e não tinha chamador nenhum.
        assert 18 in interval
        assert 23 not in interval

    def test_a_range_of_a_single_sprint(self) -> None:
        assert SprintRange(19, 19).numbers == (19,)

    def test_it_refuses_an_end_before_the_start(self) -> None:
        with pytest.raises(InvalidSprintRange):
            SprintRange(22, 18)

    def test_it_refuses_a_number_below_one(self) -> None:
        with pytest.raises(InvalidSprintNumber):
            SprintRange(0, 3)


class TestAssignee:
    def test_a_squad_assignee(self) -> None:
        assignee = Assignee.for_squad(uid(1))
        assert assignee.kind is AssigneeKind.SQUAD
        assert assignee.squad_id == uid(1)
        assert assignee.member_id is None

    def test_a_member_assignee(self) -> None:
        assignee = Assignee.for_member(uid(2))
        assert assignee.kind is AssigneeKind.MEMBER
        assert assignee.member_id == uid(2)
        assert assignee.squad_id is None

    def test_the_kind_travels_lowercase_in_the_json(self) -> None:
        assert AssigneeKind.SQUAD == "squad"
        assert AssigneeKind.MEMBER == "member"

    def test_neither_of_the_two_is_an_error(self) -> None:
        with pytest.raises(AssigneeRequired):
            Assignee.from_ids()

    def test_both_of_the_two_is_an_error(self) -> None:
        with pytest.raises(AmbiguousAssignee):
            Assignee.from_ids(squad_id=uid(1), member_id=uid(2))

    def test_equality_is_by_value(self) -> None:
        assert Assignee.for_squad(uid(1)) == Assignee.for_squad(uid(1))
        assert Assignee.for_squad(uid(1)) != Assignee.for_member(uid(1))
