"""A grade do Gantt (§8, `planning/grid`; RN13)."""

from app.application.dto.alerts import MuteAlertInput
from app.application.dto.allocations import AllocateRangeInput
from app.application.dto.planning import GridQuery
from app.application.use_cases.alerts.mute_alert import MuteAlert
from app.application.use_cases.planning.allocate_range import AllocateRange
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


class TestRowsWithoutBars:
    """C3: iniciativa viva sem barra na janela também vira linha.

    Uma célula vazia com o `+` (§10.3) pressupõe uma linha. Sem isso, uma
    iniciativa em andamento que perdeu todas as alocações some da grade e não
    há como realocá-la de lá.
    """

    def test_a_live_initiative_without_allocation_becomes_an_empty_row(
        self, world: World, fakes: Fakes
    ) -> None:
        world.sprints(18, 20)
        project = world.project("Aurora")
        world.initiative(project, "Catálogo V1", status=InitiativeStatus.IN_PROGRESS)

        view = fakes.use_case(GetGrid).execute()

        assert [group.project.name for group in view.groups] == ["Aurora"]
        (row,) = view.groups[0].rows
        assert row.initiative.name == "Catálogo V1"
        assert row.bars == ()

    def test_allocations_outside_the_window_still_leave_an_empty_row(
        self, world: World, fakes: Fakes
    ) -> None:
        world.sprints(18, 22)
        initiative = world.initiative(
            world.project("Aurora"), "Catálogo V1", status=InitiativeStatus.PLANNED
        )
        world.allocate(initiative, 21, 22, squad=world.squad("Alfa"))

        view = fakes.use_case(GetGrid).execute(GridQuery(sprint_from=18, sprint_to=19))

        (row,) = view.groups[0].rows
        assert row.bars == ()

    def test_backlog_stays_out(self, world: World, fakes: Fakes) -> None:
        """O caminho dela é o botão "Alocar" do backlog (§10.3)."""
        world.sprints(18, 20)
        world.initiative(world.project("Aurora"), "Catálogo V1")

        assert fakes.use_case(GetGrid).execute().groups == ()

    def test_backlog_of_a_capacity_reserve_project_comes_in(
        self, world: World, fakes: Fakes
    ) -> None:
        """A grade é a única porta de entrada da reserva.

        O `/backlog` exclui iniciativa de projeto de reserva por regra, e só a
        alocação tira do `BACKLOG` (RN2). Sem esta linha, a iniciativa que
        nasce com o projeto (RN-I1) não teria onde receber a primeira.
        """
        world.sprints(18, 20)
        world.initiative(world.project("Plantão", reserve=True), "Plantão")

        (group,) = fakes.use_case(GetGrid).execute().groups
        assert group.project.is_capacity_reserve
        (row,) = group.rows
        assert row.initiative.status is InitiativeStatus.BACKLOG
        assert row.bars == ()

    def test_allocating_from_the_reserve_row_closes_the_loop(
        self, world: World, fakes: Fakes
    ) -> None:
        """O `+` da célula é o caminho inteiro: aloca, RN2 move para `PLANNED`
        e a linha continua uma só, agora com barra."""
        world.sprints(18, 20)
        initiative = world.initiative(world.project("Plantão", reserve=True), "Plantão")
        squad = world.squad("Alfa")

        fakes.use_case(AllocateRange).execute(
            AllocateRangeInput(
                initiative_id=initiative.id,
                squad_id=squad.id,
                from_sprint_number=18,
                to_sprint_number=18,
            )
        )

        (group,) = fakes.use_case(GetGrid).execute().groups
        (row,) = group.rows
        assert row.initiative.status is InitiativeStatus.PLANNED
        assert len(row.bars) == 1

    def test_terminal_statuses_stay_out_of_a_reserve_project_too(
        self, world: World, fakes: Fakes
    ) -> None:
        """A exceção é do `BACKLOG`, não da reserva: RN7 continua valendo."""
        world.sprints(18, 20)
        project = world.project("Plantão", reserve=True)
        world.initiative(project, "Concluída", status=InitiativeStatus.DONE)
        world.initiative(project, "Cancelada", status=InitiativeStatus.CANCELLED)

        assert fakes.use_case(GetGrid).execute().groups == ()

    def test_an_assignee_filter_suppresses_the_reserve_row_as_well(
        self, world: World, fakes: Fakes
    ) -> None:
        """A linha vazia da reserva segue a mesma regra das outras."""
        world.sprints(18, 20)
        allocated = world.initiative(
            world.project("Aurora"), "Catálogo V1", status=InitiativeStatus.PLANNED
        )
        world.initiative(world.project("Plantão", reserve=True), "Plantão")
        squad = world.squad("Alfa")
        world.allocate(allocated, 18, squad=squad)

        view = fakes.use_case(GetGrid).execute(GridQuery(squad_id=squad.id))

        assert [group.project.name for group in view.groups] == ["Aurora"]

    def test_terminal_statuses_stay_out(self, world: World, fakes: Fakes) -> None:
        """RN7: `DONE` e `CANCELLED` não aceitam alocação, então uma célula com
        `+` só saberia devolver 422."""
        world.sprints(18, 20)
        project = world.project("Aurora")
        world.initiative(project, "Concluída", status=InitiativeStatus.DONE)
        world.initiative(project, "Cancelada", status=InitiativeStatus.CANCELLED)

        assert fakes.use_case(GetGrid).execute().groups == ()

    def test_a_deprioritized_initiative_comes_back_as_a_row(
        self, world: World, fakes: Fakes
    ) -> None:
        """É o trabalho parado, que o §10.3 quer revisitável."""
        world.sprints(18, 20)
        world.initiative(
            world.project("Aurora"),
            "Catálogo V1",
            status=InitiativeStatus.DEPRIORITIZED,
        )

        (group,) = fakes.use_case(GetGrid).execute().groups
        assert [row.initiative.status for row in group.rows] == [
            InitiativeStatus.DEPRIORITIZED
        ]

    def test_an_assignee_filter_suppresses_the_empty_rows(
        self, world: World, fakes: Fakes
    ) -> None:
        """Pedir a grade de uma squad e receber linha de iniciativa que ela não
        toca contradiz o filtro."""
        world.sprints(18, 20)
        project = world.project("Aurora")
        allocated = world.initiative(
            project, "Catálogo V1", status=InitiativeStatus.IN_PROGRESS
        )
        world.initiative(project, "Portal Externo", status=InitiativeStatus.PLANNED)
        squad = world.squad("Alfa")
        world.allocate(allocated, 18, squad=squad)

        view = fakes.use_case(GetGrid).execute(GridQuery(squad_id=squad.id))

        assert [row.initiative.name for row in view.groups[0].rows] == ["Catálogo V1"]

    def test_the_project_filter_still_applies_to_the_empty_rows(
        self, world: World, fakes: Fakes
    ) -> None:
        """O filtro de projeto é sobre a iniciativa, não sobre quem a executa."""
        world.sprints(18, 20)
        aurora = world.project("Aurora")
        boreal = world.project("Boreal")
        world.initiative(aurora, "Catálogo V1", status=InitiativeStatus.PLANNED)
        world.initiative(boreal, "Portal Externo", status=InitiativeStatus.PLANNED)

        view = fakes.use_case(GetGrid).execute(GridQuery(project_id=aurora.id))

        assert [group.project.name for group in view.groups] == ["Aurora"]

    def test_an_allocated_initiative_is_not_duplicated(
        self, world: World, fakes: Fakes
    ) -> None:
        world.sprints(18, 20)
        initiative = world.initiative(
            world.project("Aurora"), "Catálogo V1", status=InitiativeStatus.IN_PROGRESS
        )
        world.allocate(initiative, 18, 19, squad=world.squad("Alfa"))

        (group,) = fakes.use_case(GetGrid).execute().groups
        assert len(group.rows) == 1
        assert len(group.rows[0].bars) == 1
