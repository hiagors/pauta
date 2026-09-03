"""Os quatro alertas do §7.3, nos cenários de aceite do §13.1.

Os nomes são rótulos de fixture. Nada deles é hardcoded no sistema.
"""

from datetime import UTC, datetime

from app.domain.entities.muted_alert import MutedAlert
from app.domain.services.alert_service import AlertService
from app.domain.services.fingerprint import alert_fingerprint
from app.domain.services.planning_rules import PlanningSnapshot
from app.domain.value_objects.alert import Alert, AlertType, EntityRefType, Severity
from tests.domain.conftest import (
    FrozenClock,
    make_ref,
    member_alloc,
    membership,
    squad_alloc,
    uid,
)

ALFA, BETA, GAMA = uid(1), uid(2), uid(3)
ANA, CARLA, BRUNO, DIANA = uid(10), uid(11), uid(12), uid(13)

SQUADS = {ALFA: "Alfa", BETA: "Beta", GAMA: "Gama"}

AURORA_CATALOGO = make_ref(50, "Catálogo", project_seed=90, project_name="Aurora")
AURORA_ENVIO = make_ref(51, "Serviço de Envio", project_seed=90, project_name="Aurora")
BOREAL_PORTAL = make_ref(52, "Portal Externo", project_seed=91, project_name="Boreal")
BOREAL_CATALOGO = make_ref(54, "Catálogo", project_seed=91, project_name="Boreal")
COBRANCA = make_ref(55, "API de Cobrança", project_seed=93, project_name="Pagamentos")
PLANTAO = make_ref(
    53, "Sustentação", project_seed=92, project_name="Plantão", reserve=True
)

service = AlertService()


def of_type(alerts: list[Alert], alert_type: AlertType) -> list[Alert]:
    return [alert for alert in alerts if alert.type is alert_type]


class TestCenarioA:
    """Squad Alfa em duas iniciativas na Sprint 19 -> SQUAD_OVERLOADED na 19."""

    def snapshot(self) -> PlanningSnapshot:
        return PlanningSnapshot(
            sprint_numbers=(18, 19, 20),
            allocations=(
                squad_alloc(19, AURORA_CATALOGO, ALFA),
                squad_alloc(19, BOREAL_PORTAL, ALFA),
            ),
            memberships=(membership(19, ALFA, ANA),),
            squads={ALFA: "Alfa"},
            members={ANA: "Ana"},
            current_sprint_number=18,
        )

    def test_dispara_na_sprint_19(self) -> None:
        alerts = of_type(service.evaluate(self.snapshot()), AlertType.SQUAD_OVERLOADED)
        assert [alert.sprint_number for alert in alerts] == [19]

    def test_severidade_e_warning(self) -> None:
        alerta = of_type(service.evaluate(self.snapshot()), AlertType.SQUAD_OVERLOADED)[
            0
        ]
        assert alerta.severity is Severity.WARNING

    def test_a_mensagem_e_especifica(self) -> None:
        alerta = of_type(service.evaluate(self.snapshot()), AlertType.SQUAD_OVERLOADED)[
            0
        ]
        assert alerta.message == (
            "Squad Alfa está em 2 iniciativas na Sprint 19: "
            "Aurora / Catálogo e Boreal / Portal Externo."
        )

    def test_entity_refs_sao_objetos_tipados(self) -> None:
        alerta = of_type(service.evaluate(self.snapshot()), AlertType.SQUAD_OVERLOADED)[
            0
        ]
        assert alerta.entity_refs[0].type is EntityRefType.SQUAD
        assert alerta.entity_refs[0].id == ALFA
        tipos = {ref.type for ref in alerta.entity_refs}
        assert tipos == {
            EntityRefType.SQUAD,
            EntityRefType.INITIATIVE,
            EntityRefType.PROJECT,
        }

    def test_o_sujeito_do_fingerprint_e_a_squad(self) -> None:
        alerta = of_type(service.evaluate(self.snapshot()), AlertType.SQUAD_OVERLOADED)[
            0
        ]
        assert alerta.fingerprint == alert_fingerprint(
            AlertType.SQUAD_OVERLOADED, ALFA, 19
        )


class TestCenarioB:
    """A segunda iniciativa é de projeto reserva -> nenhum alerta de sobrecarga."""

    def test_reserva_nao_conta_para_squad_overloaded(self) -> None:
        snapshot = PlanningSnapshot(
            sprint_numbers=(19,),
            allocations=(
                squad_alloc(19, AURORA_CATALOGO, ALFA),
                squad_alloc(19, PLANTAO, ALFA),
            ),
            memberships=(membership(19, ALFA, ANA),),
            squads={ALFA: "Alfa"},
            members={ANA: "Ana"},
            current_sprint_number=19,
        )
        alerts = service.evaluate(snapshot)
        assert of_type(alerts, AlertType.SQUAD_OVERLOADED) == []
        assert of_type(alerts, AlertType.MEMBER_CONFLICT) == []


class TestCenarioC:
    """Ana em Alfa e Beta na 19 -> MEMBER_CONFLICT na 19."""

    def snapshot(self) -> PlanningSnapshot:
        return PlanningSnapshot(
            sprint_numbers=(19,),
            allocations=(
                squad_alloc(19, BOREAL_CATALOGO, ALFA),
                squad_alloc(19, AURORA_ENVIO, BETA),
            ),
            memberships=(
                membership(19, ALFA, ANA),
                membership(19, BETA, ANA),
            ),
            squads=SQUADS,
            members={ANA: "Ana"},
            current_sprint_number=19,
        )

    def test_dispara_na_sprint_19(self) -> None:
        alerts = of_type(service.evaluate(self.snapshot()), AlertType.MEMBER_CONFLICT)
        assert [alert.sprint_number for alert in alerts] == [19]
        assert alerts[0].severity is Severity.WARNING

    def test_a_mensagem_e_a_frase_do_spec(self) -> None:
        alerta = of_type(service.evaluate(self.snapshot()), AlertType.MEMBER_CONFLICT)[
            0
        ]
        assert alerta.message == (
            "Ana está nas squads Alfa e Beta, alocadas na Sprint 19 "
            "em Aurora / Serviço de Envio e Boreal / Catálogo."
        )

    def test_o_sujeito_do_fingerprint_e_o_membro(self) -> None:
        alerta = of_type(service.evaluate(self.snapshot()), AlertType.MEMBER_CONFLICT)[
            0
        ]
        assert alerta.subject_id == ANA
        assert alerta.fingerprint == alert_fingerprint(
            AlertType.MEMBER_CONFLICT, ANA, 19
        )

    def test_as_squads_envolvidas_aparecem_nas_refs(self) -> None:
        alerta = of_type(service.evaluate(self.snapshot()), AlertType.MEMBER_CONFLICT)[
            0
        ]
        squads = [
            ref.name for ref in alerta.entity_refs if ref.type is EntityRefType.SQUAD
        ]
        assert squads == ["Alfa", "Beta"]

    def test_alocacao_direta_junto_com_squad_tambem_e_conflito(self) -> None:
        snapshot = PlanningSnapshot(
            sprint_numbers=(19,),
            allocations=(
                squad_alloc(19, BOREAL_CATALOGO, ALFA),
                member_alloc(19, AURORA_ENVIO, ANA),
            ),
            memberships=(membership(19, ALFA, ANA),),
            squads=SQUADS,
            members={ANA: "Ana"},
            current_sprint_number=19,
        )
        alerta = of_type(service.evaluate(snapshot), AlertType.MEMBER_CONFLICT)[0]
        assert alerta.message == (
            "Ana está em 2 iniciativas na Sprint 19: "
            "Aurora / Serviço de Envio e Boreal / Catálogo."
        )


class TestCenarioD:
    """Carla em Beta nas 18-19 e em Alfa da 20 em diante -> nenhum alerta."""

    def test_composicao_por_sprint_nao_gera_conflito(self) -> None:
        snapshot = PlanningSnapshot(
            sprint_numbers=(18, 19, 20, 21),
            allocations=(
                squad_alloc(18, BOREAL_PORTAL, BETA),
                squad_alloc(19, BOREAL_PORTAL, BETA),
                squad_alloc(20, AURORA_CATALOGO, ALFA),
                squad_alloc(21, AURORA_CATALOGO, ALFA),
            ),
            memberships=(
                membership(18, BETA, CARLA),
                membership(19, BETA, CARLA),
                membership(20, ALFA, CARLA),
                membership(21, ALFA, CARLA),
            ),
            squads=SQUADS,
            members={CARLA: "Carla"},
            current_sprint_number=18,
        )
        alerts = service.evaluate(snapshot)
        assert of_type(alerts, AlertType.MEMBER_CONFLICT) == []
        assert of_type(alerts, AlertType.MEMBER_IDLE) == []
        assert of_type(alerts, AlertType.EMPTY_SQUAD) == []
        assert of_type(alerts, AlertType.SQUAD_OVERLOADED) == []


class TestCenarioE:
    """Diana ativa, sem nada na Sprint 20 (futura) -> MEMBER_IDLE na 20."""

    def snapshot(self) -> PlanningSnapshot:
        return PlanningSnapshot(
            sprint_numbers=(18, 19, 20),
            allocations=(
                squad_alloc(18, AURORA_CATALOGO, ALFA),
                squad_alloc(19, AURORA_CATALOGO, ALFA),
                squad_alloc(20, AURORA_CATALOGO, ALFA),
            ),
            memberships=(
                membership(18, ALFA, ANA),
                membership(19, ALFA, ANA),
                membership(20, ALFA, ANA),
            ),
            squads={ALFA: "Alfa"},
            members={ANA: "Ana", DIANA: "Diana"},
            current_sprint_number=19,
        )

    def test_dispara_da_sprint_atual_em_diante(self) -> None:
        alerts = of_type(service.evaluate(self.snapshot()), AlertType.MEMBER_IDLE)
        assert [(a.sprint_number, a.subject_id) for a in alerts] == [
            (19, DIANA),
            (20, DIANA),
        ]

    def test_nao_olha_para_o_passado(self) -> None:
        """Sprint 18 já passou: quem não estava em nada lá não é notícia."""
        alerts = of_type(service.evaluate(self.snapshot()), AlertType.MEMBER_IDLE)
        assert 18 not in {alert.sprint_number for alert in alerts}

    def test_severidade_e_info(self) -> None:
        alerta = of_type(service.evaluate(self.snapshot()), AlertType.MEMBER_IDLE)[0]
        assert alerta.severity is Severity.INFO
        assert alerta.message == "Diana não está em nenhuma frente na Sprint 19."

    def test_quem_tem_frente_nao_aparece(self) -> None:
        alerts = of_type(service.evaluate(self.snapshot()), AlertType.MEMBER_IDLE)
        assert ANA not in {alert.subject_id for alert in alerts}

    def test_membro_inativo_nao_aparece(self) -> None:
        """Premissa A3: inativo só desaparece."""
        snapshot = self.snapshot()
        sem_diana = PlanningSnapshot(
            sprint_numbers=snapshot.sprint_numbers,
            allocations=snapshot.allocations,
            memberships=snapshot.memberships,
            squads=snapshot.squads,
            members={ANA: "Ana"},
            current_sprint_number=19,
        )
        assert of_type(service.evaluate(sem_diana), AlertType.MEMBER_IDLE) == []

    def test_quem_esta_so_na_reserva_nao_e_ocioso(self) -> None:
        """§3 lista três efeitos da flag e MEMBER_IDLE não é um deles."""
        snapshot = PlanningSnapshot(
            sprint_numbers=(20,),
            allocations=(member_alloc(20, PLANTAO, DIANA),),
            squads={},
            members={DIANA: "Diana"},
            current_sprint_number=20,
        )
        assert of_type(service.evaluate(snapshot), AlertType.MEMBER_IDLE) == []

    def test_sem_sprint_iniciada_toda_a_janela_e_futura(self) -> None:
        snapshot = PlanningSnapshot(
            sprint_numbers=(18, 19),
            members={DIANA: "Diana"},
            current_sprint_number=None,
        )
        alerts = of_type(service.evaluate(snapshot), AlertType.MEMBER_IDLE)
        assert [alert.sprint_number for alert in alerts] == [18, 19]


class TestCenarioF:
    """Gama alocada em API de Cobrança na 21, sem composição na 21 -> EMPTY_SQUAD."""

    def snapshot(self) -> PlanningSnapshot:
        return PlanningSnapshot(
            sprint_numbers=(20, 21),
            allocations=(squad_alloc(21, COBRANCA, GAMA),),
            memberships=(membership(20, GAMA, BRUNO),),
            squads={GAMA: "Gama"},
            members={},
            current_sprint_number=20,
        )

    def test_dispara_na_sprint_21(self) -> None:
        alerts = of_type(service.evaluate(self.snapshot()), AlertType.EMPTY_SQUAD)
        assert [alert.sprint_number for alert in alerts] == [21]
        assert alerts[0].severity is Severity.INFO

    def test_a_mensagem_diz_onde_e_o_furo(self) -> None:
        alerta = of_type(service.evaluate(self.snapshot()), AlertType.EMPTY_SQUAD)[0]
        assert alerta.message == (
            "Squad Gama está alocada em Pagamentos / API de Cobrança na Sprint 21, "
            "mas não tem ninguém na composição dessa sprint."
        )

    def test_squad_com_composicao_nao_dispara(self) -> None:
        snapshot = PlanningSnapshot(
            sprint_numbers=(21,),
            allocations=(squad_alloc(21, COBRANCA, GAMA),),
            memberships=(membership(21, GAMA, BRUNO),),
            squads={GAMA: "Gama"},
            members={BRUNO: "Bruno"},
            current_sprint_number=21,
        )
        assert of_type(service.evaluate(snapshot), AlertType.EMPTY_SQUAD) == []

    def test_squad_sem_alocacao_nao_dispara(self) -> None:
        """D16: squad sem frente não é problema; pessoa sem frente é."""
        snapshot = PlanningSnapshot(
            sprint_numbers=(21,),
            squads={GAMA: "Gama"},
            current_sprint_number=21,
        )
        assert of_type(service.evaluate(snapshot), AlertType.EMPTY_SQUAD) == []

    def test_alocacao_direta_a_membro_nao_dispara_empty_squad(self) -> None:
        snapshot = PlanningSnapshot(
            sprint_numbers=(21,),
            allocations=(member_alloc(21, COBRANCA, BRUNO),),
            squads={GAMA: "Gama"},
            members={BRUNO: "Bruno"},
            current_sprint_number=21,
        )
        assert of_type(service.evaluate(snapshot), AlertType.EMPTY_SQUAD) == []


class TestCenarioG:
    """Silenciar o conflito da Ana e depois mexer nas iniciativas."""

    def snapshot(self, *, terceira: bool) -> PlanningSnapshot:
        allocations = [
            squad_alloc(19, BOREAL_CATALOGO, ALFA),
            squad_alloc(19, AURORA_ENVIO, BETA),
        ]
        if terceira:
            allocations.append(squad_alloc(19, COBRANCA, ALFA))
        return PlanningSnapshot(
            sprint_numbers=(19,),
            allocations=tuple(allocations),
            memberships=(
                membership(19, ALFA, ANA),
                membership(19, BETA, ANA),
            ),
            squads=SQUADS,
            members={ANA: "Ana"},
            current_sprint_number=19,
        )

    def mute(self) -> MutedAlert:
        return MutedAlert.create(
            alert_type=AlertType.MEMBER_CONFLICT,
            fingerprint=alert_fingerprint(AlertType.MEMBER_CONFLICT, ANA, 19),
            reason="Conflito conhecido e intencional até o fim do trimestre.",
            clock=FrozenClock(datetime.now(UTC).date()),
        )

    def test_silenciado_vem_marcado_e_nao_desaparece(self) -> None:
        mute = self.mute()
        alerta = of_type(
            service.evaluate(self.snapshot(terceira=False), {mute.fingerprint: mute}),
            AlertType.MEMBER_CONFLICT,
        )[0]
        assert alerta.is_muted
        assert alerta.mute_id == mute.id
        assert alerta.mute_reason == mute.reason

    def test_o_silenciamento_sobrevive_a_uma_terceira_iniciativa(self) -> None:
        mute = self.mute()
        alerta = of_type(
            service.evaluate(self.snapshot(terceira=True), {mute.fingerprint: mute}),
            AlertType.MEMBER_CONFLICT,
        )[0]
        assert alerta.is_muted
        assert alerta.fingerprint == mute.fingerprint

    def test_o_silenciamento_de_uma_sprint_nao_vale_para_outra(self) -> None:
        mute = self.mute()
        snapshot = PlanningSnapshot(
            sprint_numbers=(19, 20),
            allocations=(
                squad_alloc(19, BOREAL_CATALOGO, ALFA),
                squad_alloc(19, AURORA_ENVIO, BETA),
                squad_alloc(20, BOREAL_CATALOGO, ALFA),
                squad_alloc(20, AURORA_ENVIO, BETA),
            ),
            memberships=(
                membership(19, ALFA, ANA),
                membership(19, BETA, ANA),
                membership(20, ALFA, ANA),
                membership(20, BETA, ANA),
            ),
            squads=SQUADS,
            members={ANA: "Ana"},
            current_sprint_number=19,
        )
        alerts = of_type(
            service.evaluate(snapshot, {mute.fingerprint: mute}),
            AlertType.MEMBER_CONFLICT,
        )
        assert [(a.sprint_number, a.is_muted) for a in alerts] == [
            (19, True),
            (20, False),
        ]

    def test_alerta_nao_silenciado_fica_intacto(self) -> None:
        alerta = of_type(
            service.evaluate(self.snapshot(terceira=False)), AlertType.MEMBER_CONFLICT
        )[0]
        assert not alerta.is_muted
        assert alerta.mute_id is None
        assert alerta.mute_reason is None


class TestOrdemESaida:
    def test_ordena_por_sprint_e_depois_por_tipo(self) -> None:
        snapshot = PlanningSnapshot(
            sprint_numbers=(19, 20),
            allocations=(
                squad_alloc(19, AURORA_CATALOGO, ALFA),
                squad_alloc(19, BOREAL_PORTAL, ALFA),
                squad_alloc(20, COBRANCA, GAMA),
            ),
            memberships=(membership(19, ALFA, ANA),),
            squads={ALFA: "Alfa", GAMA: "Gama"},
            members={ANA: "Ana", DIANA: "Diana"},
            current_sprint_number=19,
        )
        alerts = service.evaluate(snapshot)
        assert [(a.sprint_number, a.type) for a in alerts] == [
            (19, AlertType.SQUAD_OVERLOADED),
            (19, AlertType.MEMBER_CONFLICT),
            (19, AlertType.MEMBER_IDLE),
            (20, AlertType.MEMBER_IDLE),
            (20, AlertType.MEMBER_IDLE),
            (20, AlertType.EMPTY_SQUAD),
        ]

    def test_e_deterministico_entre_execucoes(self) -> None:
        snapshot = PlanningSnapshot(
            sprint_numbers=(19,),
            members={DIANA: "Diana", ANA: "Ana", BRUNO: "Bruno"},
            current_sprint_number=19,
        )
        primeiro = [a.fingerprint for a in service.evaluate(snapshot)]
        segundo = [a.fingerprint for a in service.evaluate(snapshot)]
        assert primeiro == segundo
        assert [a.subject_id for a in service.evaluate(snapshot)] == [
            ANA,
            BRUNO,
            DIANA,
        ]

    def test_plano_vazio_nao_gera_alerta(self) -> None:
        assert service.evaluate(PlanningSnapshot(sprint_numbers=())) == []

    def test_alerta_nunca_bloqueia_nada(self) -> None:
        """Todos são aviso visual: o serviço não levanta exceção."""
        snapshot = PlanningSnapshot(
            sprint_numbers=(19,),
            allocations=(
                squad_alloc(19, AURORA_CATALOGO, ALFA),
                squad_alloc(19, BOREAL_PORTAL, ALFA),
            ),
            memberships=(
                membership(19, ALFA, ANA),
                membership(19, BETA, ANA),
            ),
            squads=SQUADS,
            members={ANA: "Ana"},
            current_sprint_number=19,
        )
        assert service.evaluate(snapshot)
