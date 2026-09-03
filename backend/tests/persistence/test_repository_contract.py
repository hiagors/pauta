"""A mesma suíte, duas implementações — o critério de aceite da Fase 3.

Cada teste daqui roda duas vezes, pela fixture `repos`: uma com os fakes
in-memory da Fase 2, outra com os repositórios SQLAlchemy sobre um SQLite
migrado. Um teste que passe num lado e falhe no outro é, por definição, uma
divergência de contrato — e é isso que a suíte existe para não deixar passar.

Estes testes eram `tests/application/test_fakes.py`, que já dizia o que "a
mesma suíte" significava: assinaturas iguais às dos `Protocol`, coleção vazia
filtra tudo, e o repositório não compartilha objeto com quem chamou. Aqui eles
valem para as duas implementações, e ganharam a cobertura por porta que a
Fase 2 não tinha por que ter.

O que **não** está aqui: o que só o SQLite tem — constraint, chave estrangeira,
ida e volta ao disco. Isso é `test_persistence.py`, porque não é contrato de
porta e um fake não pode passar.
"""

import inspect
from datetime import UTC, date, datetime, timedelta

import pytest

from app.domain.entities.member import Member
from app.domain.entities.muted_alert import MutedAlert
from app.domain.entities.project import Project
from app.domain.entities.sprint import Sprint
from app.domain.entities.squad import Squad
from app.domain.ports.repositories import (
    AllocationRepository,
    InitiativeRepository,
    MemberRepository,
    MutedAlertRepository,
    ProjectRepository,
    SprintRepository,
    SquadMembershipRepository,
    SquadRepository,
)
from app.domain.ports.snapshot import SnapshotBundle, SnapshotStore
from app.domain.value_objects.alert import AlertType
from app.domain.value_objects.color import Color
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.priority import Priority
from tests.application.conftest import Repositories, World
from tests.domain.conftest import uid

# --------------------------------------------------------------------------- #
# O contrato estrutural
# --------------------------------------------------------------------------- #


#: Cada porta com o campo de `Repositories` que a implementa.
PORTS: tuple[tuple[str, type], ...] = (
    ("store", SnapshotStore),
    ("projects", ProjectRepository),
    ("initiatives", InitiativeRepository),
    ("members", MemberRepository),
    ("squads", SquadRepository),
    ("memberships", SquadMembershipRepository),
    ("sprints", SprintRepository),
    ("allocations", AllocationRepository),
    ("muted_alerts", MutedAlertRepository),
)


def _declared_methods(port: type) -> list[str]:
    """Os métodos que a porta declara, sem os herdados de `Protocol`."""
    return sorted(
        name
        for name, member in inspect.getmembers(port, inspect.isfunction)
        if not name.startswith("_")
    )


@pytest.mark.parametrize(("field", "port"), PORTS, ids=[name for name, _ in PORTS])
def test_every_repository_matches_the_signatures_of_its_port(
    repos: Repositories, field: str, port: type
) -> None:
    """Assinatura por assinatura, e não `isinstance`.

    Este teste já existiu como `isinstance(repos.projects, ProjectRepository)`,
    e passava sem verificar nada: `isinstance` contra `Protocol`
    `runtime_checkable` confere **só nome de atributo**. Uma classe com sete
    métodos de nomes certos e assinaturas todas erradas era aceita.

    O `mypy --strict` fechou metade do buraco quando `Ports` (`http/deps.py`)
    passou a ser tipado com as portas — mas ele só vê `app/`, e os fakes desta
    suíte moram em `tests/`. Esta parametrização é o que cobre os dois lados,
    porque a fixture `repos` roda contra as duas implementações.
    """
    implementation = getattr(repos, field)
    declared = _declared_methods(port)
    assert declared, f"{port.__name__} não declara método nenhum"

    for name in declared:
        assert hasattr(implementation, name), (
            f"{type(implementation).__name__} não tem `{name}`"
        )
        expected = inspect.signature(getattr(port, name))
        actual = inspect.signature(getattr(type(implementation), name))
        assert actual == expected, (
            f"{type(implementation).__name__}.{name} diverge de "
            f"{port.__name__}.{name}: {actual} != {expected}"
        )


def test_an_empty_id_collection_filters_everything_out(
    world: World, repos: Repositories
) -> None:
    """`sprint_ids=()` é "nenhuma sprint", não "sem filtro".

    É a semântica que os use cases assumem quando a janela está vazia, e a que
    o `WHERE ... IN ()` do adapter precisa ter.
    """
    world.sprints(18, 19)
    initiative = world.initiative(world.project("Aurora"), "V1")
    squad = world.squad("Alfa")
    world.allocate(initiative, 18, squad=squad)
    world.join(squad, world.member("Ana"), 18)

    assert repos.allocations.list_all(sprint_ids=()) == []
    assert repos.allocations.list_all(sprint_ids=None) != []
    assert repos.memberships.list_all(sprint_ids=()) == []
    assert repos.memberships.list_all(sprint_ids=None) != []
    assert repos.initiatives.list_all(statuses=()) == []
    assert repos.initiatives.list_all(priorities=()) == []
    assert repos.projects.list_by_ids(()) == []
    assert repos.allocations.delete_many(()) == 0


def test_the_repository_does_not_share_the_entity_with_the_caller(
    world: World, repos: Repositories
) -> None:
    """Um repositório que devolvesse a referência esconderia um `update()`
    esquecido: a mutação do use case chegaria ao "banco" sozinha."""
    project = world.project("Aurora")

    borrowed = repos.projects.get(project.id)
    assert borrowed is not None
    borrowed.rename("Outro nome")

    stored = repos.projects.get(project.id)
    assert stored is not None
    assert stored.name == "Aurora"


def test_mutating_the_entity_after_add_does_not_reach_the_repository(
    world: World, repos: Repositories
) -> None:
    """O outro lado da mesma regra: a cópia é feita na **entrada** também."""
    project = world.project("Aurora")
    project.deactivate()

    stored = repos.projects.get(project.id)
    assert stored is not None
    assert stored.is_active is True


# --------------------------------------------------------------------------- #
# ProjectRepository
# --------------------------------------------------------------------------- #


def test_a_project_survives_the_round_trip_with_every_field(
    world: World, repos: Repositories
) -> None:
    project = world.project("Plantão", reserve=True, color="#ff8b00")
    project.set_description("  Sustentação sob demanda  ")
    repos.projects.update(project)

    stored = repos.projects.get(project.id)
    assert stored is not None
    assert stored.name == "Plantão"
    assert stored.description == "Sustentação sob demanda"
    #: A cor é normalizada em maiúsculas pelo value object (§10.2).
    assert stored.color == Color("#FF8B00")
    assert stored.is_capacity_reserve is True
    assert stored.is_active is True


def test_a_project_without_color_comes_back_without_color(
    world: World, repos: Repositories
) -> None:
    """Nulo é nulo: quem resolve a cor padrão é `effective_color` (§6.1)."""
    project = world.project("Aurora")

    stored = repos.projects.get(project.id)
    assert stored is not None
    assert stored.color is None
    assert stored.effective_color == Color.default_project()


def test_an_unknown_project_id_is_none_not_an_error(repos: Repositories) -> None:
    assert repos.projects.get(uid(999)) is None
    assert repos.projects.get_by_name("Não existe") is None


def test_projects_are_filtered_by_active_and_by_name_fragment(
    world: World, repos: Repositories
) -> None:
    """`?q=` é pedaço do nome, sem diferenciar maiúscula (§8)."""
    world.project("Aurora")
    envio = world.project("Serviço de Envio")
    archived = world.project("Antigo")
    archived.deactivate()
    repos.projects.update(archived)

    assert {item.name for item in repos.projects.list_all()} == {
        "Aurora",
        "Serviço de Envio",
        "Antigo",
    }
    assert {item.name for item in repos.projects.list_all(active=True)} == {
        "Aurora",
        "Serviço de Envio",
    }
    assert [item.name for item in repos.projects.list_all(active=False)] == ["Antigo"]
    assert [item.id for item in repos.projects.list_all(query="envio")] == [envio.id]
    assert [item.id for item in repos.projects.list_all(query="SERV")] == [envio.id]
    assert repos.projects.list_all(active=False, query="Aurora") == []


def test_the_search_ignores_case_even_with_accents(
    world: World, repos: Repositories
) -> None:
    """Todo nome deste sistema é em português.

    O `lower()` nativo do SQLite só dobra ASCII, então "Ç" e "Ã" passariam
    intactos e a busca divergiria do fake, que usa `casefold()`. É o que
    `session._register_casefold` existe para consertar.
    """
    project = world.project("Catálogo Aurora")
    initiative = world.initiative(project, "Manutenção Corretiva")

    assert [item.id for item in repos.projects.list_all(query="CATÁLOGO")] == [
        project.id
    ]
    assert [item.id for item in repos.projects.list_all(query="tálog")] == [project.id]
    assert [item.id for item in repos.initiatives.list_all(query="CORRETIVA")] == [
        initiative.id
    ]


def test_the_search_treats_the_sql_wildcards_as_text(
    world: World, repos: Repositories
) -> None:
    """`%` não é curinga na busca da UI: é um caractere que alguém digitou."""
    world.project("Aurora")

    assert repos.projects.list_all(query="%") == []
    assert repos.projects.list_all(query="_RM") == []


def test_list_by_ids_keeps_the_requested_order_and_skips_the_unknown(
    world: World, repos: Repositories
) -> None:
    first = world.project("Aurora")
    second = world.project("Boreal")

    found = repos.projects.list_by_ids([second.id, uid(999), first.id])
    assert [item.name for item in found] == ["Boreal", "Aurora"]


def test_deleting_a_project_that_is_not_there_is_a_no_op(
    world: World, repos: Repositories
) -> None:
    project = world.project("Aurora")
    repos.projects.delete(project.id)
    repos.projects.delete(project.id)

    assert repos.projects.get(project.id) is None


# --------------------------------------------------------------------------- #
# InitiativeRepository
# --------------------------------------------------------------------------- #


def test_an_initiative_survives_the_round_trip_with_every_field(
    world: World, repos: Repositories
) -> None:
    project = world.project("Aurora")
    initiative = world.initiative(
        project,
        "Catálogo V1",
        priority=Priority.HIGH,
        status=InitiativeStatus.IN_PROGRESS,
        estimated_sprints=5,
        layer="Backend",
    )

    stored = repos.initiatives.get(initiative.id)
    assert stored == initiative
    assert stored is not None
    assert stored.entered_at == date(2026, 9, 2)


def test_an_initiative_name_is_unique_only_inside_its_project(
    world: World, repos: Repositories
) -> None:
    """§6.2: dois projetos podem ter uma frente com o mesmo nome."""
    aurora = world.project("Aurora")
    boreal = world.project("Boreal")
    here = world.initiative(aurora, "Dados")
    there = world.initiative(boreal, "Dados")

    assert repos.initiatives.get_by_name(project_id=aurora.id, name="Dados") == here
    assert repos.initiatives.get_by_name(project_id=boreal.id, name="Dados") == there
    assert repos.initiatives.get_by_name(project_id=aurora.id, name="Outra") is None


def test_initiatives_are_filtered_by_project_status_priority_and_layer(
    world: World, repos: Repositories
) -> None:
    aurora = world.project("Aurora")
    boreal = world.project("Boreal")
    planned = world.initiative(
        aurora,
        "Catálogo",
        status=InitiativeStatus.PLANNED,
        priority=Priority.HIGH,
        layer="Backend",
    )
    backlog = world.initiative(aurora, "V2", status=InitiativeStatus.BACKLOG)
    other = world.initiative(boreal, "Portal Externo", priority=Priority.LOW)

    assert {item.id for item in repos.initiatives.list_all(project_id=aurora.id)} == {
        planned.id,
        backlog.id,
    }
    assert [
        item.id
        for item in repos.initiatives.list_all(statuses=(InitiativeStatus.PLANNED,))
    ] == [planned.id]
    assert {
        item.id
        for item in repos.initiatives.list_all(priorities=(Priority.HIGH, Priority.LOW))
    } == {planned.id, other.id}
    assert [item.id for item in repos.initiatives.list_all(layer="Backend")] == [
        planned.id
    ]
    assert [item.id for item in repos.initiatives.list_all(query="atál")] == [
        planned.id
    ]


def test_counting_initiatives_by_project_is_what_guards_rn_i2(
    world: World, repos: Repositories
) -> None:
    """RN-I2: é esta contagem que impede o projeto de ficar sem iniciativa."""
    aurora = world.project("Aurora")
    world.project("Boreal")
    first = world.initiative(aurora, "V1")
    world.initiative(aurora, "V2")

    assert repos.initiatives.count_by_project(aurora.id) == 2
    repos.initiatives.delete(first.id)
    assert repos.initiatives.count_by_project(aurora.id) == 1
    assert repos.initiatives.count_by_project(uid(999)) == 0


def test_updating_an_initiative_persists_the_new_status(
    world: World, repos: Repositories
) -> None:
    initiative = world.initiative(world.project("Aurora"), "V1")
    initiative.recalculate_status(has_allocations=True)
    repos.initiatives.update(initiative)

    stored = repos.initiatives.get(initiative.id)
    assert stored is not None
    assert stored.status is InitiativeStatus.PLANNED


# --------------------------------------------------------------------------- #
# MemberRepository — sem `delete`: §6.4
# --------------------------------------------------------------------------- #


def test_a_member_is_deactivated_never_deleted(
    world: World, repos: Repositories
) -> None:
    member = world.member("Ana")
    member.set_role("Analista de dados")
    member.deactivate()
    repos.members.update(member)

    stored = repos.members.get(member.id)
    assert stored is not None
    assert stored.is_active is False
    assert stored.role == "Analista de dados"
    assert repos.members.list_all(active=True) == []
    assert [item.id for item in repos.members.list_all(active=False)] == [member.id]
    assert [item.id for item in repos.members.list_all()] == [member.id]


def test_members_come_back_by_id_in_the_requested_order(
    world: World, repos: Repositories
) -> None:
    diana = world.member("Diana")
    carla = world.member("Carla")

    found = repos.members.list_by_ids([diana.id, carla.id])
    assert [item.name for item in found] == ["Diana", "Carla"]
    assert repos.members.list_by_ids([]) == []


def test_a_short_name_is_stored_as_its_own_field(
    repos: Repositories,
) -> None:
    """§6.4: `short_name` é o rótulo do avatar na grade, não um derivado."""
    member = Member.create(
        name="Ana Martins", short_name="Aninha", role="Dados", id=uid(41)
    )
    repos.members.add(member)

    assert repos.members.get(member.id) == member


# --------------------------------------------------------------------------- #
# SquadRepository — sem `delete`: §8
# --------------------------------------------------------------------------- #


def test_a_squad_keeps_its_representative_and_can_lose_it(
    world: World, repos: Repositories
) -> None:
    """RN-S1: o representante é só uma referência a um membro existente."""
    member = world.member("Carla")
    squad = Squad.create(name="Alfa", representative_member_id=member.id, id=uid(51))
    repos.squads.add(squad)

    stored = repos.squads.get(squad.id)
    assert stored is not None
    assert stored.representative_member_id == member.id

    stored.set_representative(None)
    repos.squads.update(stored)
    again = repos.squads.get(squad.id)
    assert again is not None
    assert again.representative_member_id is None


def test_squads_are_found_by_name_and_filtered_by_active(
    world: World, repos: Repositories
) -> None:
    active = world.squad("Alfa")
    retired = world.squad("Beta", active=False)

    assert repos.squads.get_by_name("Alfa") == active
    assert repos.squads.get_by_name("Delta") is None
    assert [item.id for item in repos.squads.list_all(active=True)] == [active.id]
    assert [item.id for item in repos.squads.list_all(active=False)] == [retired.id]
    assert {item.id for item in repos.squads.list_by_ids([active.id, retired.id])} == {
        active.id,
        retired.id,
    }


# --------------------------------------------------------------------------- #
# SquadMembershipRepository — a composição por sprint (§6.5)
# --------------------------------------------------------------------------- #


def test_the_composition_is_per_sprint_and_carla_is_not_a_conflict(
    world: World, repos: Repositories
) -> None:
    """Cenário D do §13.1, do ponto de vista do repositório.

    Carla na Beta nas sprints 18-19 e na Alfa da 20 em diante: nenhuma
    sprint a tem nas duas squads.
    """
    world.sprints(18, 21)
    carla = world.member("Carla")
    boreal = world.squad("Beta")
    aurora = world.squad("Alfa")
    world.join(boreal, carla, 18, 19)
    world.join(aurora, carla, 20, 21)

    by_squad = {
        18: boreal.id,
        19: boreal.id,
        20: aurora.id,
        21: aurora.id,
    }
    for number, expected in by_squad.items():
        rows = repos.memberships.list_all(sprint_ids=(world.sprint(number).id,))
        assert [row.squad_id for row in rows] == [expected]

    assert len(repos.memberships.list_all(member_id=carla.id)) == 4
    assert len(repos.memberships.list_all(squad_id=boreal.id)) == 2


def test_deleting_memberships_returns_how_many_rows_left(
    world: World, repos: Repositories
) -> None:
    """`PUT /memberships` apaga o intervalo antes de inserir: a contagem é o
    que diz à UI que a composição mudou."""
    world.sprints(18, 20)
    squad = world.squad("Alfa")
    ana = world.member("Ana")
    carla = world.member("Carla")
    world.join(squad, ana, 18, 19, 20)
    world.join(squad, carla, 18, 19, 20)
    sprints = [world.sprint(number).id for number in (18, 19)]

    #: Com `member_ids`, só quem está na lista sai.
    assert (
        repos.memberships.delete(
            squad_id=squad.id, sprint_ids=sprints, member_ids=[ana.id]
        )
        == 2
    )
    assert len(repos.memberships.list_all(member_id=ana.id)) == 1

    #: Sem `member_ids`, sai todo mundo do intervalo.
    assert repos.memberships.delete(squad_id=squad.id, sprint_ids=sprints) == 2
    assert repos.memberships.delete(squad_id=squad.id, sprint_ids=sprints) == 0
    assert len(repos.memberships.list_all(squad_id=squad.id)) == 2


def test_deleting_memberships_of_an_empty_sprint_range_touches_nothing(
    world: World, repos: Repositories
) -> None:
    world.sprints(18, 18)
    squad = world.squad("Alfa")
    world.join(squad, world.member("Ana"), 18)

    assert repos.memberships.delete(squad_id=squad.id, sprint_ids=[]) == 0
    assert len(repos.memberships.list_all(squad_id=squad.id)) == 1


# --------------------------------------------------------------------------- #
# SprintRepository — sem `delete`: D13
# --------------------------------------------------------------------------- #


def test_sprints_come_ordered_by_number(repos: Repositories) -> None:
    """A porta promete ordem crescente: a consolidação de barras conta com ela."""
    for number, start in ((20, date(2026, 9, 28)), (18, date(2026, 8, 31))):
        repos.sprints.add(
            Sprint.create(
                number=number,
                start_date=start,
                end_date=start + timedelta(days=11),
                id=uid(1000 + number),
            )
        )

    assert [sprint.number for sprint in repos.sprints.list_all()] == [18, 20]


def test_the_sprint_window_is_closed_on_both_ends(
    world: World, repos: Repositories
) -> None:
    world.sprints(18, 22)

    assert [
        sprint.number for sprint in repos.sprints.list_all(number_from=19, number_to=21)
    ] == [19, 20, 21]
    assert [sprint.number for sprint in repos.sprints.list_all(number_from=21)] == [
        21,
        22,
    ]
    assert [sprint.number for sprint in repos.sprints.list_all(number_to=19)] == [
        18,
        19,
    ]
    assert repos.sprints.list_all(number_from=30) == []


def test_a_sprint_is_found_by_its_number(world: World, repos: Repositories) -> None:
    world.sprints(18, 20)
    assert repos.sprints.get_by_number(19) == world.sprint(19)
    assert repos.sprints.get_by_number(99) is None
    assert repos.sprints.get(uid(999)) is None


# --------------------------------------------------------------------------- #
# AllocationRepository (§6.7)
# --------------------------------------------------------------------------- #


def test_an_allocation_keeps_which_kind_of_assignee_it_has(
    world: World, repos: Repositories
) -> None:
    """§6.7: o par de colunas vira um `Assignee`, que não representa "nenhum"
    nem "os dois"."""
    world.sprints(18, 19)
    initiative = world.initiative(world.project("Aurora"), "V1")
    other = world.initiative(world.project("Boreal"), "Portal Externo")
    squad = world.squad("Alfa")
    member = world.member("Ana")
    by_squad = world.allocate(initiative, 18, squad=squad)[0]
    by_member = world.allocate(other, 18, member=member)[0]

    stored_squad = repos.allocations.get(by_squad.id)
    assert stored_squad == by_squad
    assert stored_squad is not None
    assert stored_squad.squad_id == squad.id
    assert stored_squad.member_id is None
    assert stored_squad.assignee.is_squad

    stored_member = repos.allocations.get(by_member.id)
    assert stored_member is not None
    assert stored_member.member_id == member.id
    assert stored_member.squad_id is None
    assert stored_member.assignee.is_member


def test_allocations_are_filtered_by_sprint_initiative_and_assignee(
    world: World, repos: Repositories
) -> None:
    world.sprints(18, 20)
    aurora = world.initiative(world.project("Aurora"), "Catálogo")
    boreal = world.initiative(world.project("Boreal"), "Portal Externo")
    squad = world.squad("Alfa")
    member = world.member("Ana")
    world.allocate(aurora, 18, 19, squad=squad)
    world.allocate(boreal, 19, member=member)

    assert len(repos.allocations.list_all()) == 3
    assert len(repos.allocations.list_all(sprint_ids=(world.sprint(19).id,))) == 2
    assert len(repos.allocations.list_all(initiative_ids=(aurora.id,))) == 2
    assert len(repos.allocations.list_all(squad_id=squad.id)) == 2
    assert len(repos.allocations.list_all(member_id=member.id)) == 1
    assert (
        repos.allocations.list_all(
            sprint_ids=(world.sprint(18).id,), member_id=member.id
        )
        == []
    )


def test_counting_allocations_by_initiative_is_what_moves_the_status(
    world: World, repos: Repositories
) -> None:
    """RN2: é esta contagem que decide BACKLOG ⇄ PLANNED."""
    world.sprints(18, 20)
    initiative = world.initiative(world.project("Aurora"), "V1")
    cells = world.allocate(initiative, 18, 19, 20, squad=world.squad("Alfa"))

    assert repos.allocations.count_by_initiative(initiative.id) == 3
    repos.allocations.delete(cells[0].id)
    assert repos.allocations.count_by_initiative(initiative.id) == 2
    assert repos.allocations.delete_many([cells[1].id, cells[2].id]) == 2
    assert repos.allocations.count_by_initiative(initiative.id) == 0
    assert repos.allocations.get(cells[0].id) is None


def test_deleting_allocations_counts_only_what_existed(
    world: World, repos: Repositories
) -> None:
    world.sprints(18, 18)
    initiative = world.initiative(world.project("Aurora"), "V1")
    cell = world.allocate(initiative, 18, squad=world.squad("Alfa"))[0]

    assert repos.allocations.delete_many([cell.id, uid(999)]) == 1
    repos.allocations.delete(uid(999))
    assert repos.allocations.list_all() == []


# --------------------------------------------------------------------------- #
# MutedAlertRepository (§6.9)
# --------------------------------------------------------------------------- #


@pytest.fixture
def mute(repos: Repositories) -> MutedAlert:
    """Silenciamento do cenário C do §13.1: a Ana na Sprint 19."""
    created = MutedAlert.create(
        alert_type=AlertType.MEMBER_CONFLICT,
        fingerprint="a" * 32,
        reason="Conflito conhecido e intencional.",
        clock=repos.clock,
        id=uid(61),
    )
    repos.muted_alerts.add(created)
    return created


def test_a_mute_is_found_by_id_and_by_fingerprint(
    repos: Repositories, mute: MutedAlert
) -> None:
    """O `fingerprint` é a chave de consulta: o painel calcula o alerta e
    pergunta se aquele hash está silenciado (§7.3)."""
    assert repos.muted_alerts.get(mute.id) == mute
    assert repos.muted_alerts.get_by_fingerprint(mute.fingerprint) == mute
    assert repos.muted_alerts.get_by_fingerprint("b" * 32) is None
    assert repos.muted_alerts.get(uid(999)) is None
    assert repos.muted_alerts.list_all() == [mute]


def test_a_mute_keeps_its_reason_and_an_aware_timestamp(
    repos: Repositories, mute: MutedAlert
) -> None:
    """Silenciar exige motivo (§6.9), e `created_at` é UTC com timezone."""
    stored = repos.muted_alerts.get(mute.id)
    assert stored is not None
    assert stored.reason == "Conflito conhecido e intencional."
    assert stored.alert_type is AlertType.MEMBER_CONFLICT
    assert stored.created_at.tzinfo is not None
    assert stored.created_at == datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


def test_unmuting_removes_the_row(repos: Repositories, mute: MutedAlert) -> None:
    """Reativar é apagar: não existe silenciamento inativo (§7.3)."""
    repos.muted_alerts.delete(mute.id)

    assert repos.muted_alerts.get(mute.id) is None
    assert repos.muted_alerts.list_all() == []
    repos.muted_alerts.delete(mute.id)


# --------------------------------------------------------------------------- #
# SnapshotStore (§9)
# --------------------------------------------------------------------------- #
#
# A porta da Fase 5 entra na suíte de contrato como as outras: o fake e o
# SQLAlchemy têm de se comportar igual, senão o teste de use case passa contra
# um store que não é o que roda.


def test_the_dump_brings_what_the_repositories_wrote(
    repos: Repositories, world: World
) -> None:
    world.sprints(18, 19)
    project = world.project("Aurora")
    initiative = world.initiative(project, "Catálogo")
    squad = world.squad("Alfa")
    member = world.member("Ana Ribeiro")
    world.join(squad, member, 18)
    world.allocate(initiative, 18, 19, squad=squad)

    bundle = repos.store.dump()

    assert bundle.projects == (project,)
    assert bundle.initiatives == (initiative,)
    assert bundle.members == (member,)
    assert bundle.squads == (squad,)
    assert len(bundle.squad_memberships) == 1
    assert len(bundle.sprints) == 2
    assert len(bundle.allocations) == 2


def test_the_dump_of_an_empty_database_is_an_empty_bundle(
    repos: Repositories,
) -> None:
    assert repos.store.dump() == SnapshotBundle()


def test_the_dump_is_ordered_by_id(repos: Repositories) -> None:
    """§9: as listas do snapshot saem ordenadas por `id`, e é a ordenação que
    faz dois exports do mesmo dado darem o mesmo arquivo."""
    for seed in (9, 1, 5):
        repos.members.add(
            Member.create(name=f"Membro {seed}", short_name=f"M{seed}", id=uid(seed))
        )

    ids = [member.id for member in repos.store.dump().members]

    assert ids == [uid(1), uid(5), uid(9)]


def test_replace_erases_what_was_there_and_writes_the_bundle(
    repos: Repositories, world: World
) -> None:
    world.sprints(18, 18)
    doomed = world.project("Vai embora")
    kept = Project.create(name="Vem do snapshot", id=uid(500))

    repos.store.replace(SnapshotBundle(projects=(kept,)))

    assert repos.projects.get(doomed.id) is None
    assert repos.projects.get(kept.id) == kept
    assert repos.sprints.list_all() == [], "sprint também sai no replace (RNF4)"


def test_replace_with_an_empty_bundle_empties_everything(
    repos: Repositories, world: World
) -> None:
    world.sprints(18, 19)
    project = world.project("Aurora")
    world.allocate(world.initiative(project, "Catálogo"), 18, squad=world.squad("Alfa"))

    repos.store.replace(SnapshotBundle())

    assert repos.store.dump() == SnapshotBundle()


def test_what_replace_wrote_comes_back_by_the_repositories(
    repos: Repositories,
) -> None:
    """O store e os repositórios falam do mesmo dado, não de duas cópias."""
    sprint = Sprint.create(
        number=18, start_date=date(2026, 8, 31), end_date=date(2026, 9, 11), id=uid(600)
    )

    repos.store.replace(SnapshotBundle(sprints=(sprint,)))

    assert repos.sprints.get_by_number(18) == sprint


def test_replace_does_not_share_the_entity_with_the_caller(
    repos: Repositories,
) -> None:
    """Mesma regra dos outros repositórios: mutar depois de gravar não muda o
    que está gravado."""
    project = Project.create(name="Original", id=uid(700))
    repos.store.replace(SnapshotBundle(projects=(project,)))

    project.rename("Mudou depois")

    assert repos.store.dump().projects[0].name == "Original"


def test_the_dump_survives_a_replace_round_trip(
    repos: Repositories, world: World
) -> None:
    """É o roundtrip da fase, no nível da porta: o que sai do `dump` volta pelo
    `replace` sem perder nem inventar nada."""
    world.sprints(18, 20)
    project = world.project("Aurora", color="#0052CC")
    initiative = world.initiative(project, "Catálogo", estimated_sprints=3)
    member = world.member("Ana Ribeiro")
    squad = world.squad("Alfa")
    world.join(squad, member, 18, 19)
    world.allocate(initiative, 18, 19, squad=squad)
    world.allocate(world.initiative(project, "Ajustes"), 20, member=member)
    before = repos.store.dump()

    repos.store.replace(before)

    assert repos.store.dump() == before
