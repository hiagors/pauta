"""Os quatro alertas do §7.3, nos cenários de aceite do §13.1.

Os nomes são rótulos de fixture. Nada deles é hardcoded no sistema.
"""

from datetime import UTC, datetime

from app.domain.entities.muted_alert import MutedAlert
from app.domain.services.alert_service import evaluate_alerts
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


def of_type(alerts: list[Alert], alert_type: AlertType) -> list[Alert]:
    return [alert for alert in alerts if alert.type is alert_type]


class TestScenarioA:
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

    def test_it_fires_on_sprint_19(self) -> None:
        alerts = of_type(evaluate_alerts(self.snapshot()), AlertType.SQUAD_OVERLOADED)
        assert [alert.sprint_number for alert in alerts] == [19]

    def test_the_severity_is_warning(self) -> None:
        alert = of_type(evaluate_alerts(self.snapshot()), AlertType.SQUAD_OVERLOADED)[0]
        assert alert.severity is Severity.WARNING

    def test_the_message_is_specific(self) -> None:
        alert = of_type(evaluate_alerts(self.snapshot()), AlertType.SQUAD_OVERLOADED)[0]
        assert alert.message == (
            "Squad Alfa está em 2 iniciativas na Sprint 19: "
            "Aurora / Catálogo e Boreal / Portal Externo."
        )

    def test_entity_refs_are_typed_objects(self) -> None:
        alert = of_type(evaluate_alerts(self.snapshot()), AlertType.SQUAD_OVERLOADED)[0]
        assert alert.entity_refs[0].type is EntityRefType.SQUAD
        assert alert.entity_refs[0].id == ALFA
        types = {ref.type for ref in alert.entity_refs}
        assert types == {
            EntityRefType.SQUAD,
            EntityRefType.INITIATIVE,
            EntityRefType.PROJECT,
        }

    def test_the_fingerprint_subject_is_the_squad(self) -> None:
        alert = of_type(evaluate_alerts(self.snapshot()), AlertType.SQUAD_OVERLOADED)[0]
        assert alert.fingerprint == alert_fingerprint(
            AlertType.SQUAD_OVERLOADED, ALFA, 19
        )


class TestScenarioB:
    """A segunda iniciativa é de projeto reserva -> nenhum alerta de sobrecarga."""

    def test_capacity_reserve_does_not_count_towards_squad_overloaded(self) -> None:
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
        alerts = evaluate_alerts(snapshot)
        assert of_type(alerts, AlertType.SQUAD_OVERLOADED) == []
        assert of_type(alerts, AlertType.MEMBER_CONFLICT) == []


class TestScenarioC:
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

    def test_it_fires_on_sprint_19(self) -> None:
        alerts = of_type(evaluate_alerts(self.snapshot()), AlertType.MEMBER_CONFLICT)
        assert [alert.sprint_number for alert in alerts] == [19]
        assert alerts[0].severity is Severity.WARNING

    def test_the_message_is_the_sentence_of_the_spec(self) -> None:
        alert = of_type(evaluate_alerts(self.snapshot()), AlertType.MEMBER_CONFLICT)[0]
        assert alert.message == (
            "Ana está nas squads Alfa e Beta, alocadas na Sprint 19 "
            "em Aurora / Serviço de Envio e Boreal / Catálogo."
        )

    def test_the_fingerprint_subject_is_the_member(self) -> None:
        alert = of_type(evaluate_alerts(self.snapshot()), AlertType.MEMBER_CONFLICT)[0]
        assert alert.subject_id == ANA
        assert alert.fingerprint == alert_fingerprint(
            AlertType.MEMBER_CONFLICT, ANA, 19
        )

    def test_the_squads_behind_it_appear_in_the_refs(self) -> None:
        alert = of_type(evaluate_alerts(self.snapshot()), AlertType.MEMBER_CONFLICT)[0]
        squads = [
            ref.name for ref in alert.entity_refs if ref.type is EntityRefType.SQUAD
        ]
        assert squads == ["Alfa", "Beta"]

    def test_a_direct_allocation_alongside_a_squad_is_also_a_conflict(self) -> None:
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
        alert = of_type(evaluate_alerts(snapshot), AlertType.MEMBER_CONFLICT)[0]
        assert alert.message == (
            "Ana está em 2 iniciativas na Sprint 19: "
            "Aurora / Serviço de Envio e Boreal / Catálogo."
        )


class TestScenarioD:
    """Carla em Beta nas 18-19 e em Alfa da 20 em diante -> nenhum alerta."""

    def test_a_composition_that_changes_between_sprints_is_not_a_conflict(self) -> None:
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
        alerts = evaluate_alerts(snapshot)
        assert of_type(alerts, AlertType.MEMBER_CONFLICT) == []
        assert of_type(alerts, AlertType.MEMBER_IDLE) == []
        assert of_type(alerts, AlertType.EMPTY_SQUAD) == []
        assert of_type(alerts, AlertType.SQUAD_OVERLOADED) == []


class TestScenarioE:
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

    def test_it_fires_from_the_current_sprint_onwards(self) -> None:
        alerts = of_type(evaluate_alerts(self.snapshot()), AlertType.MEMBER_IDLE)
        assert [(a.sprint_number, a.subject_id) for a in alerts] == [
            (19, DIANA),
            (20, DIANA),
        ]

    def test_it_does_not_look_at_the_past(self) -> None:
        """Sprint 18 já passou: quem não estava em nada lá não é notícia."""
        alerts = of_type(evaluate_alerts(self.snapshot()), AlertType.MEMBER_IDLE)
        assert 18 not in {alert.sprint_number for alert in alerts}

    def test_the_severity_is_info(self) -> None:
        alert = of_type(evaluate_alerts(self.snapshot()), AlertType.MEMBER_IDLE)[0]
        assert alert.severity is Severity.INFO
        assert alert.message == "Diana não está em nenhuma frente na Sprint 19."

    def test_whoever_has_a_front_does_not_appear(self) -> None:
        alerts = of_type(evaluate_alerts(self.snapshot()), AlertType.MEMBER_IDLE)
        assert ANA not in {alert.subject_id for alert in alerts}

    def test_an_inactive_member_does_not_appear(self) -> None:
        """Premissa A3: inativo só desaparece."""
        snapshot = self.snapshot()
        without_diana = PlanningSnapshot(
            sprint_numbers=snapshot.sprint_numbers,
            allocations=snapshot.allocations,
            memberships=snapshot.memberships,
            squads=snapshot.squads,
            members={ANA: "Ana"},
            current_sprint_number=19,
        )
        assert of_type(evaluate_alerts(without_diana), AlertType.MEMBER_IDLE) == []

    def test_whoever_is_only_in_capacity_reserve_is_idle(self) -> None:
        """N3: reserva não consome capacidade, então não preenche a sprint.

        A flag existe para a sustentação não travar a pessoa (§3, §15). Quem
        está só nela tem capacidade livre — que é a pergunta do MEMBER_IDLE.
        """
        snapshot = PlanningSnapshot(
            sprint_numbers=(20,),
            allocations=(member_alloc(20, PLANTAO, DIANA),),
            squads={},
            members={DIANA: "Diana"},
            current_sprint_number=20,
        )
        alerts = of_type(evaluate_alerts(snapshot), AlertType.MEMBER_IDLE)
        assert [alert.subject_id for alert in alerts] == [DIANA]

    def test_the_message_of_someone_only_in_capacity_reserve_says_so(self) -> None:
        """Dizer "não está em nenhuma frente" para quem está de plantão seria
        falso, e alerta que mente é alerta que se aprende a ignorar."""
        snapshot = PlanningSnapshot(
            sprint_numbers=(20,),
            allocations=(member_alloc(20, PLANTAO, DIANA),),
            squads={},
            members={DIANA: "Diana"},
            current_sprint_number=20,
        )
        (alert,) = of_type(evaluate_alerts(snapshot), AlertType.MEMBER_IDLE)
        assert alert.message == (
            "Diana está só em reserva de capacidade na Sprint 20: "
            "Plantão / Sustentação."
        )
        refs = [
            ref.name
            for ref in alert.entity_refs
            if ref.type is EntityRefType.INITIATIVE
        ]
        assert refs == ["Sustentação"]

    def test_with_no_sprint_started_the_whole_window_is_future(self) -> None:
        snapshot = PlanningSnapshot(
            sprint_numbers=(18, 19),
            members={DIANA: "Diana"},
            current_sprint_number=None,
        )
        alerts = of_type(evaluate_alerts(snapshot), AlertType.MEMBER_IDLE)
        assert [alert.sprint_number for alert in alerts] == [18, 19]


class TestScenarioF:
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

    def test_it_fires_on_sprint_21(self) -> None:
        alerts = of_type(evaluate_alerts(self.snapshot()), AlertType.EMPTY_SQUAD)
        assert [alert.sprint_number for alert in alerts] == [21]
        assert alerts[0].severity is Severity.INFO

    def test_the_message_says_where_the_hole_is(self) -> None:
        alert = of_type(evaluate_alerts(self.snapshot()), AlertType.EMPTY_SQUAD)[0]
        assert alert.message == (
            "Squad Gama está alocada em Pagamentos / API de Cobrança na Sprint 21, "
            "mas não tem ninguém na composição dessa sprint."
        )

    def test_a_squad_with_a_composition_does_not_fire(self) -> None:
        snapshot = PlanningSnapshot(
            sprint_numbers=(21,),
            allocations=(squad_alloc(21, COBRANCA, GAMA),),
            memberships=(membership(21, GAMA, BRUNO),),
            squads={GAMA: "Gama"},
            members={BRUNO: "Bruno"},
            current_sprint_number=21,
        )
        assert of_type(evaluate_alerts(snapshot), AlertType.EMPTY_SQUAD) == []

    def test_a_squad_without_allocation_does_not_fire(self) -> None:
        """D16: squad sem frente não é problema; pessoa sem frente é."""
        snapshot = PlanningSnapshot(
            sprint_numbers=(21,),
            squads={GAMA: "Gama"},
            current_sprint_number=21,
        )
        assert of_type(evaluate_alerts(snapshot), AlertType.EMPTY_SQUAD) == []

    def test_a_direct_member_allocation_does_not_fire_empty_squad(self) -> None:
        snapshot = PlanningSnapshot(
            sprint_numbers=(21,),
            allocations=(member_alloc(21, COBRANCA, BRUNO),),
            squads={GAMA: "Gama"},
            members={BRUNO: "Bruno"},
            current_sprint_number=21,
        )
        assert of_type(evaluate_alerts(snapshot), AlertType.EMPTY_SQUAD) == []

    def test_an_inactive_squad_does_not_fire(self) -> None:
        """N1: o §7.3 escreve "squad ativa" aqui, e só aqui do lado da squad.

        Cobrar composição de um agrupamento que acabou é pedir contratação para
        um time que não existe mais.
        """
        snapshot = PlanningSnapshot(
            sprint_numbers=(21,),
            allocations=(squad_alloc(21, COBRANCA, GAMA),),
            squads={GAMA: "Gama"},
            inactive_squad_ids=frozenset({GAMA}),
            current_sprint_number=21,
        )
        assert of_type(evaluate_alerts(snapshot), AlertType.EMPTY_SQUAD) == []


class TestInactiveSquad:
    """N1: a assimetria do §7.3 entre os dois alertas de squad."""

    def snapshot(self) -> PlanningSnapshot:
        return PlanningSnapshot(
            sprint_numbers=(19,),
            allocations=(
                squad_alloc(19, AURORA_CATALOGO, ALFA),
                squad_alloc(19, BOREAL_PORTAL, ALFA),
            ),
            squads={ALFA: "Alfa"},
            inactive_squad_ids=frozenset({ALFA}),
            current_sprint_number=19,
        )

    def test_an_inactive_squad_is_still_overloaded(self) -> None:
        """`SQUAD_OVERLOADED` é o único dos quatro que o §7.3 não qualifica com
        "ativa": inativar a squad não apaga as duas frentes que ela deixou."""
        alerts = of_type(evaluate_alerts(self.snapshot()), AlertType.SQUAD_OVERLOADED)
        assert [alert.subject_id for alert in alerts] == [ALFA]

    def test_an_active_squad_keeps_firing(self) -> None:
        active_squad = PlanningSnapshot(
            sprint_numbers=(19,),
            allocations=self.snapshot().allocations,
            squads={ALFA: "Alfa"},
            current_sprint_number=19,
        )
        alerts = of_type(evaluate_alerts(active_squad), AlertType.SQUAD_OVERLOADED)
        assert [alert.subject_id for alert in alerts] == [ALFA]


class TestScenarioG:
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

    def test_a_muted_alert_comes_marked_and_does_not_disappear(self) -> None:
        mute = self.mute()
        alert = of_type(
            evaluate_alerts(self.snapshot(terceira=False), {mute.fingerprint: mute}),
            AlertType.MEMBER_CONFLICT,
        )[0]
        assert alert.is_muted
        assert alert.mute_id == mute.id
        assert alert.mute_reason == mute.reason

    def test_the_mute_survives_a_third_initiative(self) -> None:
        mute = self.mute()
        alert = of_type(
            evaluate_alerts(self.snapshot(terceira=True), {mute.fingerprint: mute}),
            AlertType.MEMBER_CONFLICT,
        )[0]
        assert alert.is_muted
        assert alert.fingerprint == mute.fingerprint

    def test_a_mute_on_one_sprint_does_not_apply_to_another(self) -> None:
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
            evaluate_alerts(snapshot, {mute.fingerprint: mute}),
            AlertType.MEMBER_CONFLICT,
        )
        assert [(a.sprint_number, a.is_muted) for a in alerts] == [
            (19, True),
            (20, False),
        ]

    def test_an_unmuted_alert_stays_intact(self) -> None:
        alert = of_type(
            evaluate_alerts(self.snapshot(terceira=False)), AlertType.MEMBER_CONFLICT
        )[0]
        assert not alert.is_muted
        assert alert.mute_id is None
        assert alert.mute_reason is None


class TestOrderAndOutput:
    def test_it_sorts_by_sprint_and_then_by_type(self) -> None:
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
        alerts = evaluate_alerts(snapshot)
        assert [(a.sprint_number, a.type) for a in alerts] == [
            (19, AlertType.SQUAD_OVERLOADED),
            (19, AlertType.MEMBER_CONFLICT),
            (19, AlertType.MEMBER_IDLE),
            (20, AlertType.MEMBER_IDLE),
            (20, AlertType.MEMBER_IDLE),
            (20, AlertType.EMPTY_SQUAD),
        ]

    def test_it_is_deterministic_across_runs(self) -> None:
        snapshot = PlanningSnapshot(
            sprint_numbers=(19,),
            members={DIANA: "Diana", ANA: "Ana", BRUNO: "Bruno"},
            current_sprint_number=19,
        )
        first = [a.fingerprint for a in evaluate_alerts(snapshot)]
        second = [a.fingerprint for a in evaluate_alerts(snapshot)]
        assert first == second
        assert [a.subject_id for a in evaluate_alerts(snapshot)] == [
            ANA,
            BRUNO,
            DIANA,
        ]

    def test_an_empty_plan_generates_no_alert(self) -> None:
        assert evaluate_alerts(PlanningSnapshot(sprint_numbers=())) == []

    def test_an_alert_never_blocks_anything(self) -> None:
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
        assert evaluate_alerts(snapshot)
