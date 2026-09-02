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

from datetime import UTC, date, datetime, timedelta

import pytest

from app.domain.entities.member import Member
from app.domain.entities.muted_alert import MutedAlert
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
from app.domain.value_objects.alert import AlertType
from app.domain.value_objects.color import Color
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.priority import Priority
from tests.application.conftest import Repositories, World
from tests.domain.conftest import uid

# --------------------------------------------------------------------------- #
# O contrato estrutural
# --------------------------------------------------------------------------- #


def test_every_repository_satisfies_its_port(repos: Repositories) -> None:
    assert isinstance(repos.projects, ProjectRepository)
    assert isinstance(repos.initiatives, InitiativeRepository)
    assert isinstance(repos.members, MemberRepository)
    assert isinstance(repos.squads, SquadRepository)
    assert isinstance(repos.memberships, SquadMembershipRepository)
    assert isinstance(repos.sprints, SprintRepository)
    assert isinstance(repos.allocations, AllocationRepository)
    assert isinstance(repos.muted_alerts, MutedAlertRepository)


def test_an_empty_id_collection_filters_everything_out(
    world: World, repos: Repositories
) -> None:
    """`sprint_ids=()` é "nenhuma sprint", não "sem filtro".

    É a semântica que os use cases assumem quando a janela está vazia, e a que
    o `WHERE ... IN ()` do adapter precisa ter.
    """
    world.sprints(18, 19)
    initiative = world.initiative(world.project("CRM"), "V1")
    squad = world.squad("Dados-A")
    world.allocate(initiative, 18, squad=squad)
    world.join(squad, world.member("Bianca"), 18)

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
    project = world.project("CRM")

    borrowed = repos.projects.get(project.id)
    assert borrowed is not None
    borrowed.rename("Outro nome")

    stored = repos.projects.get(project.id)
    assert stored is not None
    assert stored.name == "CRM"


def test_mutating_the_entity_after_add_does_not_reach_the_repository(
    world: World, repos: Repositories
) -> None:
    """O outro lado da mesma regra: a cópia é feita na **entrada** também."""
    project = world.project("CRM")
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
    project = world.project("SUS", reserve=True, color="#ff8b00")
    project.set_description("  Sustentação sob demanda  ")
    repos.projects.update(project)

    stored = repos.projects.get(project.id)
    assert stored is not None
    assert stored.name == "SUS"
    assert stored.description == "Sustentação sob demanda"
    #: A cor é normalizada em maiúsculas pelo value object (§10.2).
    assert stored.color == Color("#FF8B00")
    assert stored.is_capacity_reserve is True
    assert stored.is_active is True


def test_a_project_without_color_comes_back_without_color(
    world: World, repos: Repositories
) -> None:
    """Nulo é nulo: quem resolve a cor padrão é `effective_color` (§6.1)."""
    project = world.project("CRM")

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
    world.project("CRM")
    dispatch = world.project("Dispatch Service")
    archived = world.project("Antigo")
    archived.deactivate()
    repos.projects.update(archived)

    assert {item.name for item in repos.projects.list_all()} == {
        "CRM",
        "Dispatch Service",
        "Antigo",
    }
    assert {item.name for item in repos.projects.list_all(active=True)} == {
        "CRM",
        "Dispatch Service",
    }
    assert [item.name for item in repos.projects.list_all(active=False)] == ["Antigo"]
    assert [item.id for item in repos.projects.list_all(query="dispatch")] == [
        dispatch.id
    ]
    assert [item.id for item in repos.projects.list_all(query="SERV")] == [dispatch.id]
    assert repos.projects.list_all(active=False, query="CRM") == []


def test_the_search_ignores_case_even_with_accents(
    world: World, repos: Repositories
) -> None:
    """Todo nome deste sistema é em português.

    O `lower()` nativo do SQLite só dobra ASCII, então "Ç" e "Ã" passariam
    intactos e a busca divergiria do fake, que usa `casefold()`. É o que
    `session._register_casefold` existe para consertar.
    """
    project = world.project("Reestruturação CRM")
    initiative = world.initiative(project, "Manutenção Corretiva")

    assert [item.id for item in repos.projects.list_all(query="REESTRUTURAÇÃO")] == [
        project.id
    ]
    assert [item.id for item in repos.projects.list_all(query="turaçã")] == [project.id]
    assert [item.id for item in repos.initiatives.list_all(query="CORRETIVA")] == [
        initiative.id
    ]


def test_the_search_treats_the_sql_wildcards_as_text(
    world: World, repos: Repositories
) -> None:
    """`%` não é curinga na busca da UI: é um caractere que alguém digitou."""
    world.project("CRM")

    assert repos.projects.list_all(query="%") == []
    assert repos.projects.list_all(query="_RM") == []


def test_list_by_ids_keeps_the_requested_order_and_skips_the_unknown(
    world: World, repos: Repositories
) -> None:
    first = world.project("CRM")
    second = world.project("BNPL")

    found = repos.projects.list_by_ids([second.id, uid(999), first.id])
    assert [item.name for item in found] == ["BNPL", "CRM"]


def test_deleting_a_project_that_is_not_there_is_a_no_op(
    world: World, repos: Repositories
) -> None:
    project = world.project("CRM")
    repos.projects.delete(project.id)
    repos.projects.delete(project.id)

    assert repos.projects.get(project.id) is None


# --------------------------------------------------------------------------- #
# InitiativeRepository
# --------------------------------------------------------------------------- #


def test_an_initiative_survives_the_round_trip_with_every_field(
    world: World, repos: Repositories
) -> None:
    project = world.project("CRM")
    initiative = world.initiative(
        project,
        "Reestruturação V1",
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
    crm = world.project("CRM")
    bnpl = world.project("BNPL")
    here = world.initiative(crm, "Dados")
    there = world.initiative(bnpl, "Dados")

    assert repos.initiatives.get_by_name(project_id=crm.id, name="Dados") == here
    assert repos.initiatives.get_by_name(project_id=bnpl.id, name="Dados") == there
    assert repos.initiatives.get_by_name(project_id=crm.id, name="Outra") is None


def test_initiatives_are_filtered_by_project_status_priority_and_layer(
    world: World, repos: Repositories
) -> None:
    crm = world.project("CRM")
    bnpl = world.project("BNPL")
    planned = world.initiative(
        crm,
        "Reestruturação",
        status=InitiativeStatus.PLANNED,
        priority=Priority.HIGH,
        layer="Backend",
    )
    backlog = world.initiative(crm, "V2", status=InitiativeStatus.BACKLOG)
    other = world.initiative(bnpl, "OpenFinance", priority=Priority.LOW)

    assert {item.id for item in repos.initiatives.list_all(project_id=crm.id)} == {
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
    assert [item.id for item in repos.initiatives.list_all(query="rees")] == [
        planned.id
    ]


def test_counting_initiatives_by_project_is_what_guards_rn_i2(
    world: World, repos: Repositories
) -> None:
    """RN-I2: é esta contagem que impede o projeto de ficar sem iniciativa."""
    crm = world.project("CRM")
    world.project("BNPL")
    first = world.initiative(crm, "V1")
    world.initiative(crm, "V2")

    assert repos.initiatives.count_by_project(crm.id) == 2
    repos.initiatives.delete(first.id)
    assert repos.initiatives.count_by_project(crm.id) == 1
    assert repos.initiatives.count_by_project(uid(999)) == 0


def test_updating_an_initiative_persists_the_new_status(
    world: World, repos: Repositories
) -> None:
    initiative = world.initiative(world.project("CRM"), "V1")
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
    member = world.member("Bianca")
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
    thalita = world.member("Thalita")
    emilie = world.member("Emilie")

    found = repos.members.list_by_ids([thalita.id, emilie.id])
    assert [item.name for item in found] == ["Thalita", "Emilie"]
    assert repos.members.list_by_ids([]) == []


def test_a_short_name_is_stored_as_its_own_field(
    repos: Repositories,
) -> None:
    """§6.4: `short_name` é o rótulo do avatar na grade, não um derivado."""
    member = Member.create(
        name="Bianca Souza", short_name="Bia", role="Dados", id=uid(41)
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
    member = world.member("Emilie")
    squad = Squad.create(name="Dados-A", representative_member_id=member.id, id=uid(51))
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
    active = world.squad("Dados-A")
    retired = world.squad("Dados-B", active=False)

    assert repos.squads.get_by_name("Dados-A") == active
    assert repos.squads.get_by_name("Dados-Z") is None
    assert [item.id for item in repos.squads.list_all(active=True)] == [active.id]
    assert [item.id for item in repos.squads.list_all(active=False)] == [retired.id]
    assert {item.id for item in repos.squads.list_by_ids([active.id, retired.id])} == {
        active.id,
        retired.id,
    }


# --------------------------------------------------------------------------- #
# SquadMembershipRepository — a composição por sprint (§6.5)
# --------------------------------------------------------------------------- #


def test_the_composition_is_per_sprint_and_emilie_is_not_a_conflict(
    world: World, repos: Repositories
) -> None:
    """Cenário D do §13.1, do ponto de vista do repositório.

    Emilie na Dados-B nas sprints 18-19 e na Dados-A da 20 em diante: nenhuma
    sprint a tem nas duas squads.
    """
    world.sprints(18, 21)
    emilie = world.member("Emilie")
    bnpl = world.squad("Dados-B")
    crm = world.squad("Dados-A")
    world.join(bnpl, emilie, 18, 19)
    world.join(crm, emilie, 20, 21)

    by_squad = {
        18: bnpl.id,
        19: bnpl.id,
        20: crm.id,
        21: crm.id,
    }
    for number, expected in by_squad.items():
        rows = repos.memberships.list_all(sprint_ids=(world.sprint(number).id,))
        assert [row.squad_id for row in rows] == [expected]

    assert len(repos.memberships.list_all(member_id=emilie.id)) == 4
    assert len(repos.memberships.list_all(squad_id=bnpl.id)) == 2


def test_membership_existence_is_asked_by_the_full_triple(
    world: World, repos: Repositories
) -> None:
    world.sprints(18, 19)
    squad = world.squad("Dados-A")
    member = world.member("Bianca")
    world.join(squad, member, 18)

    assert repos.memberships.exists(
        squad_id=squad.id, member_id=member.id, sprint_id=world.sprint(18).id
    )
    assert not repos.memberships.exists(
        squad_id=squad.id, member_id=member.id, sprint_id=world.sprint(19).id
    )


def test_deleting_memberships_returns_how_many_rows_left(
    world: World, repos: Repositories
) -> None:
    """`PUT /memberships` apaga o intervalo antes de inserir: a contagem é o
    que diz à UI que a composição mudou."""
    world.sprints(18, 20)
    squad = world.squad("Dados-A")
    bianca = world.member("Bianca")
    emilie = world.member("Emilie")
    world.join(squad, bianca, 18, 19, 20)
    world.join(squad, emilie, 18, 19, 20)
    sprints = [world.sprint(number).id for number in (18, 19)]

    #: Com `member_ids`, só quem está na lista sai.
    assert (
        repos.memberships.delete(
            squad_id=squad.id, sprint_ids=sprints, member_ids=[bianca.id]
        )
        == 2
    )
    assert len(repos.memberships.list_all(member_id=bianca.id)) == 1

    #: Sem `member_ids`, sai todo mundo do intervalo.
    assert repos.memberships.delete(squad_id=squad.id, sprint_ids=sprints) == 2
    assert repos.memberships.delete(squad_id=squad.id, sprint_ids=sprints) == 0
    assert len(repos.memberships.list_all(squad_id=squad.id)) == 2


def test_deleting_memberships_of_an_empty_sprint_range_touches_nothing(
    world: World, repos: Repositories
) -> None:
    world.sprints(18, 18)
    squad = world.squad("Dados-A")
    world.join(squad, world.member("Bianca"), 18)

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


def test_the_last_sprint_is_the_one_with_the_highest_number(
    world: World, repos: Repositories
) -> None:
    """RN10: `create_next_sprint` parte dela."""
    assert repos.sprints.last() is None

    world.sprints(18, 20)
    last = repos.sprints.last()
    assert last is not None
    assert last.number == 20
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
    initiative = world.initiative(world.project("CRM"), "V1")
    other = world.initiative(world.project("BNPL"), "OpenFinance")
    squad = world.squad("Dados-A")
    member = world.member("Bianca")
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
    crm = world.initiative(world.project("CRM"), "Reestruturação")
    bnpl = world.initiative(world.project("BNPL"), "OpenFinance")
    squad = world.squad("Dados-A")
    member = world.member("Bianca")
    world.allocate(crm, 18, 19, squad=squad)
    world.allocate(bnpl, 19, member=member)

    assert len(repos.allocations.list_all()) == 3
    assert len(repos.allocations.list_all(sprint_ids=(world.sprint(19).id,))) == 2
    assert len(repos.allocations.list_all(initiative_ids=(crm.id,))) == 2
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
    initiative = world.initiative(world.project("CRM"), "V1")
    cells = world.allocate(initiative, 18, 19, 20, squad=world.squad("Dados-A"))

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
    initiative = world.initiative(world.project("CRM"), "V1")
    cell = world.allocate(initiative, 18, squad=world.squad("Dados-A"))[0]

    assert repos.allocations.delete_many([cell.id, uid(999)]) == 1
    repos.allocations.delete(uid(999))
    assert repos.allocations.list_all() == []


# --------------------------------------------------------------------------- #
# MutedAlertRepository (§6.9)
# --------------------------------------------------------------------------- #


@pytest.fixture
def mute(repos: Repositories) -> MutedAlert:
    """Silenciamento do cenário C do §13.1: a Bianca na Sprint 19."""
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
