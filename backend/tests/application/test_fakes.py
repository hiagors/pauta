"""Os fakes são contrato, não conveniência.

A Fase 3 vai reimplementar estas mesmas portas com SQLAlchemy e passar pela
mesma suíte. O que este arquivo fixa é o que "a mesma suíte" quer dizer: as
assinaturas são as dos `Protocol` do domínio, coleção vazia filtra tudo, e o
repositório não compartilha objeto com quem chamou.
"""

from datetime import date, timedelta

from app.domain.entities.sprint import Sprint
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
from tests.application.conftest import Fakes, World


def test_every_fake_satisfies_its_port(fakes: Fakes) -> None:
    assert isinstance(fakes.projects, ProjectRepository)
    assert isinstance(fakes.initiatives, InitiativeRepository)
    assert isinstance(fakes.members, MemberRepository)
    assert isinstance(fakes.squads, SquadRepository)
    assert isinstance(fakes.memberships, SquadMembershipRepository)
    assert isinstance(fakes.sprints, SprintRepository)
    assert isinstance(fakes.allocations, AllocationRepository)
    assert isinstance(fakes.muted_alerts, MutedAlertRepository)


def test_an_empty_id_collection_filters_everything_out(
    world: World, fakes: Fakes
) -> None:
    """`sprint_ids=()` é "nenhuma sprint", não "sem filtro".

    É a semântica que os use cases assumem quando a janela está vazia — e a que
    o `WHERE ... IN ()` do adapter precisa ter na Fase 3.
    """
    world.sprints(18, 19)
    initiative = world.initiative(world.project("CRM"), "V1")
    world.allocate(initiative, 18, squad=world.squad("Dados-A"))

    assert fakes.allocations.list_all(sprint_ids=()) == []
    assert fakes.allocations.list_all(sprint_ids=None) != []
    assert fakes.memberships.list_all(sprint_ids=()) == []


def test_the_repository_does_not_share_the_entity_with_the_caller(
    world: World, fakes: Fakes
) -> None:
    """Um fake que devolvesse a referência esconderia um `update()` esquecido."""
    project = world.project("CRM")

    borrowed = fakes.projects.get(project.id)
    assert borrowed is not None
    borrowed.rename("Outro nome")

    stored = fakes.projects.get(project.id)
    assert stored is not None
    assert stored.name == "CRM"


def test_sprints_come_ordered_by_number(fakes: Fakes) -> None:
    """A porta promete ordem crescente: a consolidação de barras conta com ela."""
    for number, start in ((20, date(2026, 9, 28)), (18, date(2026, 8, 31))):
        fakes.sprints.add(
            Sprint.create(
                number=number,
                start_date=start,
                end_date=start + timedelta(days=11),
            )
        )

    assert [sprint.number for sprint in fakes.sprints.list_all()] == [18, 20]
