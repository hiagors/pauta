"""O backlog (§8, `planning/backlog`)."""

from datetime import date

from app.application.dto.planning import BacklogOrder, BacklogQuery
from app.application.use_cases.planning.get_backlog import GetBacklog
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.priority import Priority
from tests.application.conftest import Fakes, World


def test_the_backlog_is_by_status(world: World, fakes: Fakes) -> None:
    """`DEPRIORITIZED` não aparece aqui: é outro lugar (§8)."""
    crm = world.project("CRM")
    world.initiative(crm, "Fila")
    world.initiative(crm, "Planejada", status=InitiativeStatus.PLANNED)
    world.initiative(crm, "Despriorizada", status=InitiativeStatus.DEPRIORITIZED)
    world.initiative(crm, "Cancelada", status=InitiativeStatus.CANCELLED)

    view = fakes.use_case(GetBacklog).execute()

    assert [item.initiative.name for item in view.items] == ["Fila"]


def test_capacity_reserve_projects_stay_out(world: World, fakes: Fakes) -> None:
    """Sustentação sob demanda não é fila de trabalho (§3)."""
    world.initiative(world.project("CRM"), "Fila")
    world.initiative(world.project("SUS", reserve=True), "Sustentação")

    view = fakes.use_case(GetBacklog).execute()

    assert [item.initiative.name for item in view.items] == ["Fila"]
    assert view.summary.count == 1


def test_the_summary_counts_only_who_has_an_estimate(
    world: World, fakes: Fakes
) -> None:
    crm = world.project("CRM")
    world.initiative(crm, "A", estimated_sprints=5)
    world.initiative(crm, "B", estimated_sprints=2)
    world.initiative(crm, "C")

    view = fakes.use_case(GetBacklog).execute()

    assert view.summary.count == 3
    assert view.summary.estimated_sprints_total == 7
    assert view.summary.items_without_estimate == 1


def test_ordering_by_priority_is_the_default(world: World, fakes: Fakes) -> None:
    crm = world.project("CRM")
    world.initiative(crm, "Baixa", priority=Priority.LOW)
    world.initiative(crm, "Alta", priority=Priority.HIGH)
    world.initiative(crm, "Média", priority=Priority.MEDIUM)

    view = fakes.use_case(GetBacklog).execute()

    assert [item.initiative.name for item in view.items] == ["Alta", "Média", "Baixa"]


def test_ordering_by_size_keeps_the_unknown_last_in_both_directions(
    world: World, fakes: Fakes
) -> None:
    """§8: nulos por último em qualquer direção.

    "Sem estimativa" não é "estimativa zero": inverter a ordem não pode
    promover o desconhecido ao topo da fila.
    """
    crm = world.project("CRM")
    world.initiative(crm, "Grande", estimated_sprints=8)
    world.initiative(crm, "Pequena", estimated_sprints=1)
    world.initiative(crm, "Sem tamanho")

    ascending = fakes.use_case(GetBacklog).execute(
        BacklogQuery(order_by=BacklogOrder.SIZE)
    )
    descending = fakes.use_case(GetBacklog).execute(
        BacklogQuery(order_by=BacklogOrder.SIZE, descending=True)
    )

    assert [item.initiative.name for item in ascending.items] == [
        "Pequena",
        "Grande",
        "Sem tamanho",
    ]
    assert [item.initiative.name for item in descending.items] == [
        "Grande",
        "Pequena",
        "Sem tamanho",
    ]


def test_ordering_by_entered_at(world: World, fakes: Fakes) -> None:
    crm = world.project("CRM")
    old = world.initiative(crm, "Antiga")
    old.entered_at = date(2026, 1, 5)
    fakes.initiatives.update(old)
    world.initiative(crm, "Nova")

    view = fakes.use_case(GetBacklog).execute(
        BacklogQuery(order_by=BacklogOrder.ENTERED_AT)
    )

    assert [item.initiative.name for item in view.items] == ["Antiga", "Nova"]


def test_the_item_carries_the_project_with_the_color_resolved(
    world: World, fakes: Fakes
) -> None:
    crm = world.project("CRM", color="#0052cc")
    world.initiative(crm, "Fila")

    view = fakes.use_case(GetBacklog).execute()

    assert view.items[0].project.name == "CRM"
    assert view.items[0].project.color == "#0052CC"


def test_an_empty_backlog_has_a_zeroed_summary(fakes: Fakes) -> None:
    view = fakes.use_case(GetBacklog).execute()

    assert view.items == ()
    assert view.summary.count == 0
    assert view.summary.estimated_sprints_total == 0
    assert view.summary.items_without_estimate == 0
