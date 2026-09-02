"""Um snapshot de exemplo, com todas as formas que o §6 permite.

Serve às duas metades da fase: o writer tem de escrever cada uma delas e o
reader tem de trazê-las de volta idênticas. O que está aqui não é um cenário de
negócio bonito — é a lista de casos que costumam se perder num roundtrip:

- projeto **sem** cor (usa a padrão, §6.1) e projeto com cor;
- iniciativa sem `layer` e sem estimativa, e outra com as duas;
- membro inativo (§6.4) e squad inativa, que continuam no dado como histórico;
- squad com representante e squad sem (RN-S1);
- alocação de squad e alocação **direta** de membro (§6.7);
- `MutedAlert`, cujo `created_at` a RNF4 preserva verbatim.

Ids determinísticos, via `uid`, para o diff de um teste que falha ser legível.
"""

from datetime import UTC, date, datetime

from app.domain.entities.allocation import Allocation
from app.domain.entities.initiative import Initiative
from app.domain.entities.member import Member
from app.domain.entities.muted_alert import MutedAlert
from app.domain.entities.project import Project
from app.domain.entities.sprint import Sprint
from app.domain.entities.squad import Squad
from app.domain.entities.squad_membership import SquadMembership
from app.domain.ports.snapshot import SnapshotBundle
from app.domain.value_objects.alert import AlertType
from app.domain.value_objects.assignee import Assignee
from app.domain.value_objects.color import Color
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.priority import Priority
from tests.domain.conftest import uid

#: As duas sprints do exemplo: a 18 começa na segunda 31/08/2026 (§6.6).
SPRINT_18 = Sprint(
    id=uid(101), number=18, start_date=date(2026, 8, 31), end_date=date(2026, 9, 11)
)
SPRINT_19 = Sprint(
    id=uid(102), number=19, start_date=date(2026, 9, 14), end_date=date(2026, 9, 25)
)


def full_bundle() -> SnapshotBundle:
    crm = Project(
        id=uid(1),
        name="CRM",
        description="Frente de relacionamento",
        color=Color("#0052CC"),
    )
    reserva = Project(
        id=uid(2),
        name="Reserva de capacidade",
        is_capacity_reserve=True,
    )
    bianca = Member(id=uid(11), name="Bianca Alves", short_name="Bianca", role="Dados")
    thalita = Member(
        id=uid(12), name="Thalita Souza", short_name="Thalita", is_active=False
    )
    dados_a = Squad(id=uid(21), name="Dados-A", representative_member_id=bianca.id)
    dados_b = Squad(id=uid(22), name="Dados-B", is_active=False)
    reestruturacao = Initiative(
        id=uid(31),
        project_id=crm.id,
        name="Reestruturação V1",
        entered_at=date(2026, 7, 1),
        layer="Dados",
        description="Modelo novo | com pipe no texto",
        priority=Priority.HIGH,
        estimated_sprints=5,
        status=InitiativeStatus.IN_PROGRESS,
    )
    suporte = Initiative(
        id=uid(32),
        project_id=reserva.id,
        name="Suporte e imprevistos",
        entered_at=date(2026, 8, 15),
    )
    return SnapshotBundle(
        projects=(crm, reserva),
        initiatives=(reestruturacao, suporte),
        members=(bianca, thalita),
        squads=(dados_a, dados_b),
        squad_memberships=(
            SquadMembership(
                id=uid(41),
                squad_id=dados_a.id,
                member_id=bianca.id,
                sprint_id=SPRINT_18.id,
            ),
            SquadMembership(
                id=uid(42),
                squad_id=dados_a.id,
                member_id=bianca.id,
                sprint_id=SPRINT_19.id,
            ),
        ),
        sprints=(SPRINT_18, SPRINT_19),
        allocations=(
            Allocation(
                id=uid(51),
                initiative_id=reestruturacao.id,
                sprint_id=SPRINT_18.id,
                assignee=Assignee.for_squad(dados_a.id),
            ),
            Allocation(
                id=uid(52),
                initiative_id=reestruturacao.id,
                sprint_id=SPRINT_19.id,
                assignee=Assignee.for_squad(dados_a.id),
            ),
            Allocation(
                id=uid(53),
                initiative_id=suporte.id,
                sprint_id=SPRINT_19.id,
                assignee=Assignee.for_member(thalita.id),
            ),
        ),
        muted_alerts=(
            MutedAlert(
                id=uid(61),
                alert_type=AlertType.MEMBER_CONFLICT,
                fingerprint="member:00000000-0000-0000-0000-00000000000b:19",
                reason="Combinado com a Bianca: metade do tempo em cada squad.",
                created_at=datetime(2026, 9, 1, 13, 30, tzinfo=UTC),
            ),
        ),
    )
