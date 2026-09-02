"""Use cases de projeto (§6.1, RN-I1, RN-I2)."""

import pytest

from app.application.dto.projects import CreateProjectInput, UpdateProjectInput
from app.application.use_cases.projects.archive import ArchiveProject
from app.application.use_cases.projects.create import CreateProject
from app.application.use_cases.projects.get import GetProject
from app.application.use_cases.projects.list import ListProjects
from app.application.use_cases.projects.update import UpdateProject
from app.domain.errors import DuplicateName, HasAllocations, ProjectNotFound
from app.domain.value_objects.color import DEFAULT_PROJECT_COLOR
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.priority import Priority
from tests.application.conftest import TODAY, Fakes, World
from tests.domain.conftest import uid


def test_create_project_also_creates_the_first_initiative(fakes: Fakes) -> None:
    """RN-I1: projeto nunca nasce sem iniciativa."""
    view = fakes.use_case(CreateProject).execute(CreateProjectInput(name="CRM"))

    assert len(view.initiatives) == 1
    first = view.initiatives[0]
    assert first.name == "CRM"
    assert first.project_id == view.project.id
    assert first.status is InitiativeStatus.BACKLOG
    assert first.priority is Priority.MEDIUM
    assert first.entered_at == TODAY
    assert fakes.initiatives.count_by_project(view.project.id) == 1


def test_create_project_without_color_keeps_it_null(fakes: Fakes) -> None:
    """A cor gravada é nula; a cor padrão é resolvida na hora de desenhar."""
    view = fakes.use_case(CreateProject).execute(CreateProjectInput(name="SUS"))

    assert view.project.color is None
    stored = fakes.projects.get(view.project.id)
    assert stored is not None
    assert str(stored.effective_color) == DEFAULT_PROJECT_COLOR


def test_create_project_rejects_duplicate_name(fakes: Fakes) -> None:
    create = fakes.use_case(CreateProject)
    create.execute(CreateProjectInput(name="CRM"))

    with pytest.raises(DuplicateName):
        create.execute(CreateProjectInput(name="CRM"))


def test_create_project_normalizes_the_color(fakes: Fakes) -> None:
    view = fakes.use_case(CreateProject).execute(
        CreateProjectInput(name="CRM", color="#0052cc")
    )

    assert view.project.color == "#0052CC"


def test_update_project_touches_only_the_fields_in_the_payload(
    world: World, fakes: Fakes
) -> None:
    project = world.project("CRM", color="#0052CC")

    view = fakes.use_case(UpdateProject).execute(
        project.id, UpdateProjectInput(description="Frentes do CRM")
    )

    assert view.description == "Frentes do CRM"
    assert view.color == "#0052CC"
    assert view.is_capacity_reserve is False


def test_update_project_with_null_color_clears_it(world: World, fakes: Fakes) -> None:
    """`color: null` é diferente de "não falei de cor" (§6.1)."""
    project = world.project("CRM", color="#0052CC")

    view = fakes.use_case(UpdateProject).execute(
        project.id, UpdateProjectInput(color=None)
    )

    assert view.color is None
    stored = fakes.projects.get(project.id)
    assert stored is not None
    assert stored.color is None


def test_update_project_can_toggle_capacity_reserve(world: World, fakes: Fakes) -> None:
    """Reserva de capacidade é configuração, ligável e desligável (§3)."""
    project = world.project("SUS")

    fakes.use_case(UpdateProject).execute(
        project.id, UpdateProjectInput(is_capacity_reserve=True)
    )
    stored = fakes.projects.get(project.id)
    assert stored is not None
    assert stored.is_capacity_reserve is True

    fakes.use_case(UpdateProject).execute(
        project.id, UpdateProjectInput(is_capacity_reserve=False)
    )
    stored = fakes.projects.get(project.id)
    assert stored is not None
    assert stored.is_capacity_reserve is False


def test_update_project_rejects_a_name_that_belongs_to_another(
    world: World, fakes: Fakes
) -> None:
    world.project("CRM")
    bnpl = world.project("BNPL")

    with pytest.raises(DuplicateName):
        fakes.use_case(UpdateProject).execute(bnpl.id, UpdateProjectInput(name="CRM"))


def test_update_project_accepts_its_own_name(world: World, fakes: Fakes) -> None:
    project = world.project("CRM")

    view = fakes.use_case(UpdateProject).execute(
        project.id, UpdateProjectInput(name="CRM", description="mesma coisa")
    )

    assert view.name == "CRM"


def test_update_project_reports_unknown_id(fakes: Fakes) -> None:
    with pytest.raises(ProjectNotFound):
        fakes.use_case(UpdateProject).execute(uid(999), UpdateProjectInput(name="X"))


def test_get_project_includes_the_initiatives_in_queue_order(
    world: World, fakes: Fakes
) -> None:
    project = world.project("CRM")
    world.initiative(project, "Dispatch Service", priority=Priority.LOW)
    world.initiative(project, "Reestruturação V1", priority=Priority.HIGH)
    world.initiative(world.project("BNPL"), "OpenFinance")

    view = fakes.use_case(GetProject).execute(project.id)

    assert [item.name for item in view.initiatives] == [
        "Reestruturação V1",
        "Dispatch Service",
    ]


def test_list_projects_filters_by_active_and_query(world: World, fakes: Fakes) -> None:
    world.project("CRM")
    bnpl = world.project("BNPL")
    bnpl.deactivate()
    fakes.projects.update(bnpl)

    assert [view.name for view in fakes.use_case(ListProjects).execute()] == [
        "BNPL",
        "CRM",
    ]
    assert [
        view.name for view in fakes.use_case(ListProjects).execute(active=True)
    ] == ["CRM"]
    assert [
        view.name for view in fakes.use_case(ListProjects).execute(query="crm")
    ] == ["CRM"]


def test_archive_project_removes_it_with_its_initiatives(
    world: World, fakes: Fakes
) -> None:
    """Projeto sem iniciativa não existe (RN-I2): as dele saem junto."""
    project = world.project("CRM")
    initiative = world.initiative(project, "Reestruturação V1")

    fakes.use_case(ArchiveProject).execute(project.id)

    assert fakes.projects.get(project.id) is None
    assert fakes.initiatives.get(initiative.id) is None


def test_archive_project_refuses_when_an_initiative_has_allocation(
    world: World, fakes: Fakes
) -> None:
    world.sprints(18, 18)
    project = world.project("CRM")
    initiative = world.initiative(project, "Reestruturação V1")
    world.allocate(initiative, 18, squad=world.squad("Dados-A"))

    with pytest.raises(HasAllocations):
        fakes.use_case(ArchiveProject).execute(project.id)

    assert fakes.projects.get(project.id) is not None
    assert fakes.initiatives.get(initiative.id) is not None


def test_archive_project_reports_unknown_id(fakes: Fakes) -> None:
    with pytest.raises(ProjectNotFound):
        fakes.use_case(ArchiveProject).execute(uid(999))
