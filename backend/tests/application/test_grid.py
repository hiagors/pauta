"""A grade do Gantt (§8, `planning/grid`; RN13)."""

from app.application.dto.alerts import MuteAlertInput
from app.application.dto.planning import GridQuery
from app.application.use_cases.alerts.mute_alert import MuteAlert
from app.application.use_cases.planning.get_grid import GetGrid
from app.domain.services.fingerprint import alert_fingerprint
from app.domain.value_objects.alert import AlertType
from app.domain.value_objects.assignee import AssigneeKind
from app.domain.value_objects.color import DEFAULT_PROJECT_COLOR
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.priority import Priority
from tests.application.conftest import Fakes, World


def test_the_default_window_is_the_current_quarter(world: World, fakes: Fakes) -> None:
    """RN13: hoje é 02/09/2026, e o trimestre civil vai até 30/09."""
    world.sprints(18, 22)

    view = fakes.use_case(GetGrid).execute()

    assert [sprint.number for sprint in view.sprints] == [18, 19, 20]
    assert [sprint.number for sprint in view.sprints if sprint.is_current] == [18]


def test_an_explicit_window_overrides_the_quarter(world: World, fakes: Fakes) -> None:
    world.sprints(18, 22)

    view = fakes.use_case(GetGrid).execute(GridQuery(sprint_from=21, sprint_to=22))

    assert [sprint.number for sprint in view.sprints] == [21, 22]


def test_rows_come_grouped_by_project_with_the_color_resolved(
    world: World, fakes: Fakes
) -> None:
    world.sprints(18, 20)
    aurora = world.project("Aurora", color="#0052CC")
    boreal = world.project("Boreal")
    reest = world.initiative(aurora, "Catálogo V1", priority=Priority.HIGH)
    envio = world.initiative(aurora, "Serviço de Envio", priority=Priority.LOW)
    portal = world.initiative(boreal, "Portal Externo")
    squad = world.squad("Alfa")
    world.allocate(reest, 18, squad=squad)
    world.allocate(envio, 19, squad=squad)
    world.allocate(portal, 20, squad=squad)

    view = fakes.use_case(GetGrid).execute()

    assert [group.project.name for group in view.groups] == ["Aurora", "Boreal"]
    assert view.groups[0].project.color == "#0052CC"
    assert view.groups[1].project.color == DEFAULT_PROJECT_COLOR
    assert [row.initiative.name for row in view.groups[0].rows] == [
        "Catálogo V1",
        "Serviço de Envio",
    ]


def test_contiguous_sprints_become_one_bar_and_a_pause_opens_another(
    world: World, fakes: Fakes
) -> None:
    """O front desenha barras, não células: quem consolida é o backend."""
    world.sprints(18, 22)
    initiative = world.initiative(
        world.project("Aurora"), "V1", status=InitiativeStatus.IN_PROGRESS
    )
    squad = world.squad("Alfa")
    world.allocate(initiative, 18, 19, 21, 22, squad=squad)

    view = fakes.use_case(GetGrid).execute(GridQuery(sprint_from=18, sprint_to=22))

    bars = view.groups[0].rows[0].bars
    assert [(bar.from_sprint_number, bar.to_sprint_number) for bar in bars] == [
        (18, 19),
        (21, 22),
    ]
    assert bars[0].assignee.kind is AssigneeKind.SQUAD
    assert bars[0].assignee.name == "Alfa"
    assert len(bars[0].allocation_ids) == 2


def test_a_change_of_assignee_opens_a_new_bar(world: World, fakes: Fakes) -> None:
    world.sprints(18, 20)
    initiative = world.initiative(world.project("Aurora"), "V1")
    world.allocate(initiative, 18, squad=world.squad("Alfa"))
    world.allocate(initiative, 19, member=world.member("Ana Martins"))

    view = fakes.use_case(GetGrid).execute()

    bars = view.groups[0].rows[0].bars
    assert [(bar.assignee.kind, bar.assignee.name) for bar in bars] == [
        (AssigneeKind.SQUAD, "Alfa"),
        (AssigneeKind.MEMBER, "Ana"),
    ]


def test_filtering_by_member_shows_what_reaches_him_through_the_squad(
    world: World, fakes: Fakes
) -> None:
    """§6.8: a alocação efetiva é o que interessa numa leitura de capacidade."""
    world.sprints(18, 20)
    aurora = world.project("Aurora")
    through_squad = world.initiative(aurora, "Catálogo")
    direct = world.initiative(aurora, "Ajuste pequeno")
    other = world.initiative(aurora, "Frente de outra squad")
    squad = world.squad("Alfa")
    ana = world.member("Ana")
    world.join(squad, ana, 18)
    world.allocate(through_squad, 18, squad=squad)
    world.allocate(direct, 19, member=ana)
    world.allocate(other, 18, squad=world.squad("Beta"))

    view = fakes.use_case(GetGrid).execute(GridQuery(member_id=ana.id))

    assert sorted(row.initiative.name for row in view.groups[0].rows) == [
        "Ajuste pequeno",
        "Catálogo",
    ]


def test_filtering_by_squad_and_project(world: World, fakes: Fakes) -> None:
    world.sprints(18, 20)
    aurora = world.project("Aurora")
    boreal = world.project("Boreal")
    mine = world.initiative(aurora, "Catálogo")
    theirs = world.initiative(boreal, "Portal Externo")
    alfa = world.squad("Alfa")
    world.allocate(mine, 18, squad=alfa)
    world.allocate(theirs, 18, squad=world.squad("Beta"))

    by_squad = fakes.use_case(GetGrid).execute(GridQuery(squad_id=alfa.id))
    assert [group.project.name for group in by_squad.groups] == ["Aurora"]

    by_project = fakes.use_case(GetGrid).execute(GridQuery(project_id=boreal.id))
    assert [group.project.name for group in by_project.groups] == ["Boreal"]


def test_alerts_by_sprint_ignores_the_row_filters(world: World, fakes: Fakes) -> None:
    """§8: o ícone do cabeçalho reporta a sprint inteira.

    Filtrar por uma squad e perder o aviso da outra esconderia justamente o
    conflito que se quer ver.
    """
    world.sprints(18, 20)
    aurora = world.project("Aurora")
    first = world.initiative(aurora, "Catálogo")
    second = world.initiative(aurora, "Envio")
    overloaded = world.squad("Beta")
    world.join(overloaded, world.member("Ana"), 19)
    world.allocate(first, 19, squad=overloaded)
    world.allocate(second, 19, squad=overloaded)
    quiet = world.squad("Alfa")
    world.join(quiet, world.member("Bruno"), 19)
    world.allocate(world.initiative(aurora, "Sozinha"), 19, squad=quiet)

    view = fakes.use_case(GetGrid).execute(GridQuery(squad_id=quiet.id))

    assert [group.project.name for group in view.groups] == ["Aurora"]
    assert [row.initiative.name for row in view.groups[0].rows] == ["Sozinha"]
    assert AlertType.SQUAD_OVERLOADED in view.alerts_by_sprint[19]


def test_a_muted_alert_does_not_light_the_column_header(
    world: World, fakes: Fakes
) -> None:
    """Se o ícone continuasse aceso, silenciar não silenciaria nada."""
    world.sprints(18, 20)
    aurora = world.project("Aurora")
    squad = world.squad("Alfa")
    world.join(squad, world.member("Ana"), 19)
    world.allocate(world.initiative(aurora, "Catálogo"), 19, squad=squad)
    world.allocate(world.initiative(aurora, "Envio"), 19, squad=squad)
    fakes.use_case(MuteAlert).execute(
        MuteAlertInput(
            fingerprint=alert_fingerprint(AlertType.SQUAD_OVERLOADED, squad.id, 19),
            alert_type=AlertType.SQUAD_OVERLOADED,
            reason="Conflito conhecido e intencional.",
        )
    )

    view = fakes.use_case(GetGrid).execute()

    assert AlertType.SQUAD_OVERLOADED not in view.alerts_by_sprint.get(19, ())


def test_an_initiative_without_allocation_is_not_a_row(
    world: World, fakes: Fakes
) -> None:
    """A grade é o plano; o que não está alocado está no backlog."""
    world.sprints(18, 20)
    world.initiative(world.project("Aurora"), "V1")

    view = fakes.use_case(GetGrid).execute()

    assert view.groups == ()


def test_an_empty_grid_has_no_sprints_and_no_groups(fakes: Fakes) -> None:
    view = fakes.use_case(GetGrid).execute()

    assert view.sprints == ()
    assert view.groups == ()
    assert view.alerts_by_sprint == {}
