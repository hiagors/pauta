"""Projeto: agrupador, sem status, sem prioridade, sem alocação (§6.1)."""

import pytest

from app.domain.entities.project import Project
from app.domain.errors import InvalidName
from app.domain.value_objects.color import DEFAULT_PROJECT_COLOR, Color


def test_a_project_is_created_with_the_minimum() -> None:
    project = Project.create(name="Aurora")
    assert project.name == "Aurora"
    assert project.description == ""
    assert project.color is None
    assert project.is_capacity_reserve is False
    assert project.is_active is True


def test_the_name_is_required() -> None:
    with pytest.raises(InvalidName):
        Project.create(name="   ")


def test_the_name_is_normalized() -> None:
    assert Project.create(name="  Aurora  ").name == "Aurora"


def test_a_project_without_a_color_uses_the_neutral_default() -> None:
    assert Project.create(name="Aurora").effective_color.value == DEFAULT_PROJECT_COLOR


def test_a_project_with_a_color_uses_its_own() -> None:
    project = Project.create(name="Aurora", color=Color("#0052CC"))
    assert project.effective_color.value == "#0052CC"


def test_capacity_reserve_can_be_turned_on_and_off() -> None:
    project = Project.create(name="Plantão", is_capacity_reserve=True)
    assert project.is_capacity_reserve
    project.set_capacity_reserve(False)
    assert not project.is_capacity_reserve


def test_a_project_has_no_status_no_priority_and_no_allocation() -> None:
    fields = set(Project.__dataclass_fields__)
    assert not fields & {"status", "priority", "allocations", "squad_id", "member_id"}
