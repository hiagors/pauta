"""Use cases de iniciativa (§6.2, §6.3)."""

import pytest

from app.application.dto.initiatives import (
    CreateInitiativeInput,
    InitiativeFilter,
    UpdateInitiativeInput,
)
from app.application.use_cases.initiatives.archive import ArchiveInitiative
from app.application.use_cases.initiatives.change_status import ChangeInitiativeStatus
from app.application.use_cases.initiatives.create import CreateInitiative
from app.application.use_cases.initiatives.get import GetInitiative
from app.application.use_cases.initiatives.list import ListInitiatives
from app.application.use_cases.initiatives.update import UpdateInitiative
from app.domain.errors import (
    DuplicateName,
    HasAllocations,
    InitiativeNotFound,
    InvalidEstimate,
    InvalidStatusTransition,
    LastInitiativeOfProject,
    ProjectNotFound,
)
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.priority import Priority
from tests.application.conftest import TODAY, Fakes, World
from tests.domain.conftest import uid


def test_create_initiative_starts_in_backlog_with_today(
    world: World, fakes: Fakes
) -> None:
    project = world.project("CRM")

    view = fakes.use_case(CreateInitiative).execute(
        CreateInitiativeInput(
            project_id=project.id,
            name="Dispatch Service",
            layer="Backend",
            priority=Priority.HIGH,
            estimated_sprints=3,
        )
    )

    assert view.status is InitiativeStatus.BACKLOG
    assert view.entered_at == TODAY
    assert view.layer == "Backend"
    assert view.estimated_sprints == 3


def test_create_initiative_requires_an_existing_project(fakes: Fakes) -> None:
    with pytest.raises(ProjectNotFound):
        fakes.use_case(CreateInitiative).execute(
            CreateInitiativeInput(project_id=uid(999), name="Órfã")
        )


def test_initiative_name_is_unique_inside_the_project_only(
    world: World, fakes: Fakes
) -> None:
    """Uma "Reestruturação" no CRM e outra no BNPL são normais (§6.2)."""
    crm = world.project("CRM")
    bnpl = world.project("BNPL")
    create = fakes.use_case(CreateInitiative)
    create.execute(CreateInitiativeInput(project_id=crm.id, name="Reestruturação"))

    create.execute(CreateInitiativeInput(project_id=bnpl.id, name="Reestruturação"))

    with pytest.raises(DuplicateName):
        create.execute(CreateInitiativeInput(project_id=crm.id, name="Reestruturação"))


def test_create_initiative_rejects_a_non_positive_estimate(
    world: World, fakes: Fakes
) -> None:
    project = world.project("CRM")

    with pytest.raises(InvalidEstimate):
        fakes.use_case(CreateInitiative).execute(
            CreateInitiativeInput(
                project_id=project.id, name="Sem tamanho", estimated_sprints=0
            )
        )


def test_update_initiative_clears_the_layer_with_null(
    world: World, fakes: Fakes
) -> None:
    initiative = world.initiative(world.project("CRM"), "V1", layer="Dados")

    view = fakes.use_case(UpdateInitiative).execute(
        initiative.id, UpdateInitiativeInput(layer=None)
    )

    assert view.layer is None
    stored = fakes.initiatives.get(initiative.id)
    assert stored is not None
    assert stored.layer is None


def test_update_initiative_keeps_the_status_out_of_reach(
    world: World, fakes: Fakes
) -> None:
    """Status só muda pelo endpoint próprio: `UpdateInitiativeInput` não o tem."""
    initiative = world.initiative(
        world.project("CRM"), "V1", status=InitiativeStatus.IN_PROGRESS
    )

    view = fakes.use_case(UpdateInitiative).execute(
        initiative.id, UpdateInitiativeInput(priority=Priority.HIGH)
    )

    assert view.status is InitiativeStatus.IN_PROGRESS
    assert view.priority is Priority.HIGH


def test_change_status_follows_the_manual_table(world: World, fakes: Fakes) -> None:
    initiative = world.initiative(
        world.project("CRM"), "V1", status=InitiativeStatus.PLANNED
    )
    change = fakes.use_case(ChangeInitiativeStatus)

    view = change.execute(initiative.id, InitiativeStatus.IN_PROGRESS)
    assert view.status is InitiativeStatus.IN_PROGRESS

    view = change.execute(initiative.id, InitiativeStatus.DEPRIORITIZED)
    assert view.status is InitiativeStatus.DEPRIORITIZED

    stored = fakes.initiatives.get(initiative.id)
    assert stored is not None
    assert stored.status is InitiativeStatus.DEPRIORITIZED


def test_change_status_refuses_a_forbidden_transition(
    world: World, fakes: Fakes
) -> None:
    """`BACKLOG -> IN_PROGRESS` não existe: entra em PLANNED por alocação."""
    initiative = world.initiative(world.project("CRM"), "V1")

    with pytest.raises(InvalidStatusTransition):
        fakes.use_case(ChangeInitiativeStatus).execute(
            initiative.id, InitiativeStatus.IN_PROGRESS
        )


def test_change_status_refuses_to_leave_a_terminal_status(
    world: World, fakes: Fakes
) -> None:
    initiative = world.initiative(
        world.project("CRM"), "V1", status=InitiativeStatus.DONE
    )

    with pytest.raises(InvalidStatusTransition):
        fakes.use_case(ChangeInitiativeStatus).execute(
            initiative.id, InitiativeStatus.IN_PROGRESS
        )


def test_list_initiatives_filters_and_orders_by_priority(
    world: World, fakes: Fakes
) -> None:
    crm = world.project("CRM")
    world.initiative(crm, "Dispatch", priority=Priority.LOW, layer="Backend")
    world.initiative(crm, "Reestruturação", priority=Priority.HIGH)
    world.initiative(
        crm, "V2", priority=Priority.MEDIUM, status=InitiativeStatus.CANCELLED
    )
    world.initiative(world.project("BNPL"), "OpenFinance", priority=Priority.HIGH)

    listing = fakes.use_case(ListInitiatives)

    assert [view.name for view in listing.execute()] == [
        "OpenFinance",
        "Reestruturação",
        "V2",
        "Dispatch",
    ]
    assert [
        view.name
        for view in listing.execute(
            InitiativeFilter(project_id=crm.id, layer="Backend")
        )
    ] == ["Dispatch"]
    assert [
        view.name
        for view in listing.execute(
            InitiativeFilter(statuses=(InitiativeStatus.BACKLOG,), query="reestru")
        )
    ] == ["Reestruturação"]


def test_get_initiative_reports_unknown_id(fakes: Fakes) -> None:
    with pytest.raises(InitiativeNotFound):
        fakes.use_case(GetInitiative).execute(uid(999))


def test_archive_initiative_removes_it_when_the_project_keeps_another(
    world: World, fakes: Fakes
) -> None:
    project = world.project("CRM")
    first = world.initiative(project, "V1")
    world.initiative(project, "V2")

    fakes.use_case(ArchiveInitiative).execute(first.id)

    assert fakes.initiatives.get(first.id) is None
    assert fakes.initiatives.count_by_project(project.id) == 1


def test_archive_initiative_refuses_the_last_of_the_project(
    world: World, fakes: Fakes
) -> None:
    """RN-I2: um projeto não pode ficar sem iniciativa."""
    project = world.project("CRM")
    only = world.initiative(project, "V1")

    with pytest.raises(LastInitiativeOfProject):
        fakes.use_case(ArchiveInitiative).execute(only.id)


def test_archive_initiative_refuses_when_it_has_allocation(
    world: World, fakes: Fakes
) -> None:
    world.sprints(18, 18)
    project = world.project("CRM")
    first = world.initiative(project, "V1")
    world.initiative(project, "V2")
    world.allocate(first, 18, squad=world.squad("Dados-A"))

    with pytest.raises(HasAllocations):
        fakes.use_case(ArchiveInitiative).execute(first.id)
