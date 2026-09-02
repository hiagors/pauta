"""O que só o banco tem, e que um fake não pode provar.

A suíte de contrato mostra que as duas implementações se comportam igual. Aqui
o alvo é o que existe **por baixo** dela: as constraints que repetem as
invariantes do §6, a chave estrangeira ligada em cada conexão (RNF1) e o dado
sobrevivendo ao fim da sessão.

Uma violação de constraint chega como `IntegrityError`, não como `DomainError`:
traduzir erro de banco em erro de negócio é trabalho da borda HTTP (§8,
Fase 4). O que a Fase 3 garante é que a violação **acontece**, em vez de gravar
linha inconsistente em silêncio.

Todos os `INSERT` inválidos entram pelo modelo ou por SQL cru, nunca pelo
repositório: o caminho do repositório passa pela entidade, que já recusa esse
estado. O alvo aqui é justamente quem chega por fora — um `UPDATE` à mão no
arquivo, ou uma restauração de snapshot antigo.
"""

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.outbound.persistence.models import (
    AllocationModel,
    InitiativeModel,
    MutedAlertModel,
    ProjectModel,
    SprintModel,
    SquadMembershipModel,
)
from app.adapters.outbound.persistence.repositories import (
    SqlAlchemyMutedAlertRepository,
    SqlAlchemyProjectRepository,
)
from app.domain.entities.allocation import Allocation
from app.domain.entities.initiative import Initiative
from app.domain.entities.member import Member
from app.domain.entities.muted_alert import MutedAlert
from app.domain.entities.project import Project
from app.domain.entities.sprint import Sprint
from app.domain.entities.squad import Squad
from app.domain.entities.squad_membership import SquadMembership
from app.domain.value_objects.alert import AlertType
from app.domain.value_objects.color import Color
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.priority import Priority
from tests.domain.conftest import FrozenClock, uid
from tests.persistence.conftest import SqlRepositories

# --------------------------------------------------------------------------- #
# Apoio: o cenário mínimo para uma alocação existir
# --------------------------------------------------------------------------- #


@pytest.fixture
def repos(session: Session, clock: FrozenClock) -> SqlRepositories:
    """Só a implementação SQLAlchemy: nada aqui é contrato de porta."""
    return SqlRepositories.build(session=session, clock=clock)


def _sprint(repos: SqlRepositories, number: int = 18) -> Sprint:
    start = date(2026, 8, 31) + timedelta(days=14 * (number - 18))
    sprint = Sprint.create(
        number=number,
        start_date=start,
        end_date=start + timedelta(days=11),
        id=uid(1000 + number),
    )
    repos.sprints.add(sprint)
    return sprint


def _project(repos: SqlRepositories, name: str = "CRM", seed: int = 1) -> Project:
    project = Project.create(name=name, id=uid(seed))
    repos.projects.add(project)
    return project


def _initiative(
    repos: SqlRepositories, project: Project, name: str = "V1", seed: int = 2
) -> Initiative:
    initiative = Initiative(
        id=uid(seed),
        project_id=project.id,
        name=name,
        entered_at=date(2026, 9, 2),
    )
    repos.initiatives.add(initiative)
    return initiative


def _squad(repos: SqlRepositories, name: str = "Dados-A", seed: int = 3) -> Squad:
    squad = Squad.create(name=name, id=uid(seed))
    repos.squads.add(squad)
    return squad


def _member(repos: SqlRepositories, name: str = "Bianca", seed: int = 4) -> Member:
    member = Member.create(name=name, short_name=name[:3], id=uid(seed))
    repos.members.add(member)
    return member


# --------------------------------------------------------------------------- #
# Chave estrangeira (RNF1)
# --------------------------------------------------------------------------- #


def test_foreign_keys_are_on_in_every_connection(session: Session) -> None:
    """O SQLite nasce com FK desligada e volta ao default em cada conexão nova
    — por isso o `PRAGMA` é listener do evento `connect`, e não uma chamada
    única na criação da engine."""
    assert session.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_an_allocation_cannot_point_to_a_sprint_that_does_not_exist(
    repos: SqlRepositories, session: Session
) -> None:
    initiative = _initiative(repos, _project(repos))
    squad = _squad(repos)

    session.add(
        AllocationModel(
            id=uuid4(),
            initiative_id=initiative.id,
            sprint_id=uuid4(),
            squad_id=squad.id,
            member_id=None,
        )
    )
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        session.flush()


def test_a_membership_cannot_point_to_a_member_that_does_not_exist(
    repos: SqlRepositories, session: Session
) -> None:
    sprint = _sprint(repos)
    squad = _squad(repos)

    session.add(
        SquadMembershipModel(
            id=uuid4(),
            squad_id=squad.id,
            member_id=uuid4(),
            sprint_id=sprint.id,
        )
    )
    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        session.flush()


# --------------------------------------------------------------------------- #
# Constraints que repetem as invariantes do §6
# --------------------------------------------------------------------------- #


def test_an_allocation_needs_exactly_one_assignee(
    repos: SqlRepositories, session: Session
) -> None:
    """§6.7. A entidade não representa "nenhum" nem "os dois"; o `CHECK` é o
    que impede um `INSERT` vindo de fora de chegar lá."""
    sprint = _sprint(repos)
    initiative = _initiative(repos, _project(repos))
    squad = _squad(repos)
    member = _member(repos)
    session.commit()

    for squad_id, member_id in ((None, None), (squad.id, member.id)):
        session.add(
            AllocationModel(
                id=uuid4(),
                initiative_id=initiative.id,
                sprint_id=sprint.id,
                squad_id=squad_id,
                member_id=member_id,
            )
        )
        with pytest.raises(IntegrityError, match="exactly_one_assignee"):
            session.flush()
        session.rollback()


def test_an_initiative_has_one_assignee_per_sprint(
    repos: SqlRepositories, session: Session
) -> None:
    """RN8: unicidade `(initiative_id, sprint_id)`.

    Duas squads na mesma frente ao mesmo tempo deveriam ser uma squad só — e é
    isso que elimina barra empilhada na grade.
    """
    sprint = _sprint(repos)
    initiative = _initiative(repos, _project(repos))
    first = _squad(repos, "Dados-A", seed=3)
    second = _squad(repos, "Dados-B", seed=4)
    repos.allocations.add_many(
        [
            Allocation.create_from_ids(
                initiative_id=initiative.id, sprint_id=sprint.id, squad_id=first.id
            )
        ]
    )

    session.add(
        AllocationModel(
            id=uuid4(),
            initiative_id=initiative.id,
            sprint_id=sprint.id,
            squad_id=second.id,
            member_id=None,
        )
    )
    with pytest.raises(IntegrityError, match="UNIQUE"):
        session.flush()


def test_the_same_person_is_not_twice_in_the_same_squad_and_sprint(
    repos: SqlRepositories, session: Session
) -> None:
    """§6.5: unicidade `(squad_id, member_id, sprint_id)`."""
    sprint = _sprint(repos)
    squad = _squad(repos)
    member = _member(repos)
    repos.memberships.add_many(
        [
            SquadMembership.create(
                squad_id=squad.id, member_id=member.id, sprint_id=sprint.id
            )
        ]
    )

    session.add(
        SquadMembershipModel(
            id=uuid4(),
            squad_id=squad.id,
            member_id=member.id,
            sprint_id=sprint.id,
        )
    )
    with pytest.raises(IntegrityError, match="UNIQUE"):
        session.flush()


def test_a_project_name_is_unique(repos: SqlRepositories, session: Session) -> None:
    """§6.1. O use case checa antes e devolve 409; a constraint é a rede."""
    _project(repos, "CRM")

    session.add(
        ProjectModel(
            id=uuid4(),
            name="CRM",
            description="",
            color=None,
            is_capacity_reserve=False,
            is_active=True,
        )
    )
    with pytest.raises(IntegrityError, match="UNIQUE"):
        session.flush()


def test_an_initiative_name_repeats_across_projects_but_not_inside_one(
    repos: SqlRepositories, session: Session
) -> None:
    """§6.2: a unicidade é `(project_id, name)`, não `name`."""
    crm = _project(repos, "CRM", seed=1)
    bnpl = _project(repos, "BNPL", seed=2)
    _initiative(repos, crm, "Dados", seed=3)
    #: Mesmo nome, outro projeto: entra.
    _initiative(repos, bnpl, "Dados", seed=4)

    session.add(
        InitiativeModel(
            id=uuid4(),
            project_id=crm.id,
            name="Dados",
            layer=None,
            description="",
            priority=Priority.MEDIUM,
            estimated_sprints=None,
            status=InitiativeStatus.BACKLOG,
            entered_at=date(2026, 9, 2),
        )
    )
    with pytest.raises(IntegrityError, match="UNIQUE"):
        session.flush()


def test_a_sprint_number_is_unique_and_the_dates_are_ordered(
    repos: SqlRepositories, session: Session
) -> None:
    """§6.6. `end_date > start_date` é invariante da entidade; o `CHECK` é o
    que impede um `UPDATE` à mão de contorná-la."""
    _sprint(repos, 18)
    session.commit()

    session.add(
        SprintModel(
            id=uuid4(),
            number=18,
            start_date=date(2026, 10, 5),
            end_date=date(2026, 10, 16),
        )
    )
    with pytest.raises(IntegrityError, match="UNIQUE"):
        session.flush()
    session.rollback()

    session.add(
        SprintModel(
            id=uuid4(),
            number=19,
            start_date=date(2026, 10, 16),
            end_date=date(2026, 10, 5),
        )
    )
    with pytest.raises(IntegrityError, match="dates_ordered"):
        session.flush()


def test_a_status_outside_the_enum_does_not_get_in(
    repos: SqlRepositories, session: Session
) -> None:
    """O `CHECK ... IN (...)` é gerado do próprio enum: um valor que o domínio
    não conhece não entra nem por `INSERT` cru."""
    project = _project(repos)
    session.commit()

    with pytest.raises(IntegrityError, match="status_known"):
        session.execute(
            text(
                "INSERT INTO initiatives (id, project_id, name, layer, description, "
                "priority, estimated_sprints, status, entered_at) VALUES "
                "(:id, :project_id, 'V1', NULL, '', 'MEDIUM', NULL, 'ARQUIVADA', "
                "'2026-09-02')"
            ),
            {"id": uuid4().hex, "project_id": project.id.hex},
        )


def test_a_mute_is_unique_by_fingerprint(
    repos: SqlRepositories, session: Session, clock: FrozenClock
) -> None:
    """§6.9: a unicidade do `fingerprint` é o que faz "já está silenciado" ser
    409 em vez de duas linhas para o mesmo alerta."""
    repos.muted_alerts.add(
        MutedAlert.create(
            alert_type=AlertType.MEMBER_CONFLICT,
            fingerprint="a" * 32,
            reason="Conhecido e intencional.",
            clock=clock,
            id=uid(1),
        )
    )

    session.add(
        MutedAlertModel(
            id=uuid4(),
            alert_type=AlertType.MEMBER_CONFLICT,
            fingerprint="a" * 32,
            reason="De novo.",
            created_at=clock.now(),
        )
    )
    with pytest.raises(IntegrityError, match="UNIQUE"):
        session.flush()


# --------------------------------------------------------------------------- #
# Ida e volta ao disco
# --------------------------------------------------------------------------- #


def test_the_data_survives_the_session_that_wrote_it(
    session_factory: sessionmaker[Session], clock: FrozenClock
) -> None:
    """O único teste que faz `commit`, e ele existe por um motivo específico.

    Dentro da mesma sessão a leitura pode vir do *identity map*, não do banco.
    Reabrir é o que prova que a cor, o booleano e o `datetime` foram escritos e
    relidos de verdade — inclusive o `created_at`, que o SQLite guarda sem
    offset e que o mapper devolve com `UTC`.
    """
    with session_factory() as writer:
        repos = SqlRepositories.build(session=writer, clock=clock)
        repos.projects.add(
            Project.create(
                name="SUS",
                description="Sustentação sob demanda",
                color=Color("#ff8b00"),
                is_capacity_reserve=True,
                id=uid(1),
            )
        )
        repos.muted_alerts.add(
            MutedAlert.create(
                alert_type=AlertType.EMPTY_SQUAD,
                fingerprint="c" * 32,
                reason="A squad ainda vai ser montada.",
                clock=clock,
                id=uid(2),
            )
        )
        writer.commit()

    with session_factory() as reader:
        project = SqlAlchemyProjectRepository(reader).get(uid(1))
        assert project is not None
        assert project.color == Color("#FF8B00")
        assert project.is_capacity_reserve is True
        assert project.description == "Sustentação sob demanda"

        mute = SqlAlchemyMutedAlertRepository(reader).get(uid(2))
        assert mute is not None
        assert mute.created_at == clock.now()
        assert mute.created_at.tzinfo is not None
        assert mute.alert_type is AlertType.EMPTY_SQUAD
