"""Os quatro alertas e o silenciamento, pelos use cases (§7.3, §13.1).

Os cenários A a G do §13.1 aparecem aqui como fixtures de teste, do jeito que
o spec manda — não existe `seed`, e nada disso é dado pré-cadastrado.

As asserções filtram por tipo de alerta de propósito: `MEMBER_IDLE` fala de
toda pessoa ativa sem frente em toda sprint da atual em diante (premissa A2 do
§16), então quase todo cenário produz alguns, e checar a lista inteira faria o
teste falar de outra regra que não a dele.
"""

import pytest

from app.application.dto.alerts import AlertsQuery, MuteAlertInput
from app.application.use_cases.alerts.list_alerts import ListAlerts
from app.application.use_cases.alerts.mute_alert import MuteAlert
from app.application.use_cases.alerts.unmute_alert import UnmuteAlert
from app.domain.errors import (
    AlertAlreadyMuted,
    MutedAlertNotFound,
    MuteReasonRequired,
)
from app.domain.services.fingerprint import alert_fingerprint
from app.domain.value_objects.alert import Alert, AlertType, EntityRefType, Severity
from tests.application.conftest import Fakes, World
from tests.domain.conftest import uid


def sprints_with(alerts: tuple[Alert, ...], alert_type: AlertType) -> list[int]:
    return sorted(alert.sprint_number for alert in alerts if alert.type is alert_type)


def only(alerts: tuple[Alert, ...], alert_type: AlertType) -> Alert:
    found = [alert for alert in alerts if alert.type is alert_type]
    assert len(found) == 1, f"esperava um {alert_type}, veio {len(found)}"
    return found[0]


def test_scenario_a_squad_in_two_initiatives_is_overloaded(
    world: World, fakes: Fakes
) -> None:
    world.sprints(18, 22)
    dados_a = world.squad("Dados-A")
    world.join(dados_a, world.member("Bianca"), 19)
    world.allocate(
        world.initiative(world.project("CRM"), "Reestruturação"), 19, squad=dados_a
    )
    world.allocate(
        world.initiative(world.project("BNPL"), "OpenFinance"), 19, squad=dados_a
    )

    view = fakes.use_case(ListAlerts).execute()

    assert sprints_with(view.items, AlertType.SQUAD_OVERLOADED) == [19]
    alert = only(view.items, AlertType.SQUAD_OVERLOADED)
    assert alert.severity is Severity.WARNING
    assert "Dados-A" in alert.message
    assert "Sprint 19" in alert.message
    assert "CRM / Reestruturação" in alert.message
    assert alert.entity_refs[0].type is EntityRefType.SQUAD
    assert alert.entity_refs[0].id == dados_a.id


def test_scenario_b_a_capacity_reserve_initiative_does_not_overload(
    world: World, fakes: Fakes
) -> None:
    """Quem está na sustentação sob demanda não fica travado (§3)."""
    world.sprints(18, 22)
    dados_a = world.squad("Dados-A")
    world.join(dados_a, world.member("Bianca"), 19)
    world.allocate(
        world.initiative(world.project("CRM"), "Reestruturação"), 19, squad=dados_a
    )
    world.allocate(
        world.initiative(world.project("SUS", reserve=True), "Sustentação"),
        19,
        squad=dados_a,
    )

    view = fakes.use_case(ListAlerts).execute()

    assert sprints_with(view.items, AlertType.SQUAD_OVERLOADED) == []
    assert sprints_with(view.items, AlertType.MEMBER_CONFLICT) == []


def test_scenario_c_a_member_in_two_squads_is_a_conflict(
    world: World, fakes: Fakes
) -> None:
    world.sprints(18, 22)
    dados_a = world.squad("Dados-A")
    dados_b = world.squad("Dados-B")
    bianca = world.member("Bianca")
    world.join(dados_a, bianca, 19)
    world.join(dados_b, bianca, 19)
    world.allocate(
        world.initiative(world.project("BNPL"), "Reestruturação"), 19, squad=dados_a
    )
    world.allocate(
        world.initiative(world.project("CRM"), "Dispatch Service"), 19, squad=dados_b
    )

    view = fakes.use_case(ListAlerts).execute()

    assert sprints_with(view.items, AlertType.MEMBER_CONFLICT) == [19]
    alert = only(view.items, AlertType.MEMBER_CONFLICT)
    assert alert.subject_id == bianca.id
    assert "Bianca" in alert.message
    assert "Dados-A e Dados-B" in alert.message
    assert sprints_with(view.items, AlertType.SQUAD_OVERLOADED) == []


def test_scenario_d_moving_between_squads_between_sprints_is_not_a_conflict(
    world: World, fakes: Fakes
) -> None:
    """Emilie no BNPL nas 18-19 e no CRM da 20 em diante (§6.5)."""
    world.sprints(18, 22)
    dados_a = world.squad("Dados-A")
    dados_b = world.squad("Dados-B")
    emilie = world.member("Emilie")
    world.join(dados_b, emilie, 18, 19)
    world.join(dados_a, emilie, 20, 21, 22)
    bnpl_front = world.initiative(world.project("BNPL"), "Reestruturação")
    crm_front = world.initiative(world.project("CRM"), "Dispatch Service")
    world.allocate(bnpl_front, 18, 19, 20, 21, 22, squad=dados_b)
    world.allocate(crm_front, 18, 19, 20, 21, 22, squad=dados_a)

    view = fakes.use_case(ListAlerts).execute()

    assert sprints_with(view.items, AlertType.MEMBER_CONFLICT) == []
    assert sprints_with(view.items, AlertType.MEMBER_IDLE) == []


def test_scenario_e_a_member_without_a_front_in_a_future_sprint_is_idle(
    world: World, fakes: Fakes
) -> None:
    world.sprints(18, 22)
    squad = world.squad("Dados-A")
    thalita = world.member("Thalita")
    world.join(squad, thalita, 18, 19, 21, 22)
    world.allocate(
        world.initiative(world.project("CRM"), "Reestruturação"),
        18,
        19,
        20,
        21,
        22,
        squad=squad,
    )

    view = fakes.use_case(ListAlerts).execute()

    assert sprints_with(view.items, AlertType.MEMBER_IDLE) == [20]
    alert = only(view.items, AlertType.MEMBER_IDLE)
    assert alert.severity is Severity.INFO
    assert alert.subject_id == thalita.id
    assert "Thalita" in alert.message


def test_an_inactive_member_is_never_idle(world: World, fakes: Fakes) -> None:
    """Premissa A3 do §16: quem é inativado só desaparece."""
    world.sprints(18, 19)
    world.member("Ana", active=False)

    view = fakes.use_case(ListAlerts).execute()

    assert view.items == ()


def test_scenario_f_a_squad_with_allocation_and_nobody_in_it(
    world: World, fakes: Fakes
) -> None:
    """RN-S2: informativo, nunca bloqueio — planejar antes de contratar vale."""
    world.sprints(18, 22)
    dados_c = world.squad("Dados-C")
    world.allocate(world.initiative(world.project("PIX"), "API PIX"), 21, squad=dados_c)

    view = fakes.use_case(ListAlerts).execute()

    assert sprints_with(view.items, AlertType.EMPTY_SQUAD) == [21]
    alert = only(view.items, AlertType.EMPTY_SQUAD)
    assert alert.severity is Severity.INFO
    assert alert.subject_id == dados_c.id


def test_scenario_g_muting_survives_a_third_initiative(
    world: World, fakes: Fakes
) -> None:
    """O `fingerprint` é ancorado no sujeito, nunca nas iniciativas (§7.3)."""
    world.sprints(18, 22)
    dados_a = world.squad("Dados-A")
    dados_b = world.squad("Dados-B")
    bianca = world.member("Bianca")
    world.join(dados_a, bianca, 19)
    world.join(dados_b, bianca, 19)
    crm = world.project("CRM")
    world.allocate(world.initiative(crm, "Reestruturação"), 19, squad=dados_a)
    world.allocate(world.initiative(crm, "Dispatch Service"), 19, squad=dados_b)
    before = only(fakes.use_case(ListAlerts).execute().items, AlertType.MEMBER_CONFLICT)
    fakes.use_case(MuteAlert).execute(
        MuteAlertInput(
            fingerprint=before.fingerprint,
            alert_type=AlertType.MEMBER_CONFLICT,
            reason="Conflito conhecido e intencional da Bianca.",
        )
    )

    world.allocate(world.initiative(crm, "Terceira frente"), 19, squad=dados_a)
    view = fakes.use_case(ListAlerts).execute(AlertsQuery(include_muted=True))

    after = only(view.items, AlertType.MEMBER_CONFLICT)
    assert after.fingerprint == before.fingerprint
    assert after.is_muted is True
    assert after.mute_reason == "Conflito conhecido e intencional da Bianca."
    assert after.mute_id is not None


def test_muted_alerts_leave_the_list_but_stay_counted(
    world: World, fakes: Fakes
) -> None:
    """O painel mostra os não silenciados atrás de um contador (§7.3)."""
    world.sprints(18, 22)
    squad = world.squad("Dados-A")
    world.join(squad, world.member("Bianca"), 19)
    crm = world.project("CRM")
    world.allocate(world.initiative(crm, "Reestruturação"), 19, squad=squad)
    world.allocate(world.initiative(crm, "Dispatch"), 19, squad=squad)
    fakes.use_case(MuteAlert).execute(
        MuteAlertInput(
            fingerprint=alert_fingerprint(AlertType.SQUAD_OVERLOADED, squad.id, 19),
            alert_type=AlertType.SQUAD_OVERLOADED,
            reason="Combinado com o time.",
        )
    )

    view = fakes.use_case(ListAlerts).execute()

    assert sprints_with(view.items, AlertType.SQUAD_OVERLOADED) == []
    assert view.muted_count == 1


def test_unmuting_brings_the_alert_back(world: World, fakes: Fakes) -> None:
    world.sprints(18, 22)
    squad = world.squad("Dados-A")
    world.join(squad, world.member("Bianca"), 19)
    crm = world.project("CRM")
    world.allocate(world.initiative(crm, "Reestruturação"), 19, squad=squad)
    world.allocate(world.initiative(crm, "Dispatch"), 19, squad=squad)
    mute = fakes.use_case(MuteAlert).execute(
        MuteAlertInput(
            fingerprint=alert_fingerprint(AlertType.SQUAD_OVERLOADED, squad.id, 19),
            alert_type=AlertType.SQUAD_OVERLOADED,
            reason="Combinado com o time.",
        )
    )

    fakes.use_case(UnmuteAlert).execute(mute.id)

    view = fakes.use_case(ListAlerts).execute()
    assert sprints_with(view.items, AlertType.SQUAD_OVERLOADED) == [19]
    assert view.muted_count == 0


def test_muting_the_same_fingerprint_twice_is_a_conflict(fakes: Fakes) -> None:
    payload = MuteAlertInput(
        fingerprint="abc123",
        alert_type=AlertType.MEMBER_CONFLICT,
        reason="Sabemos.",
    )
    mute = fakes.use_case(MuteAlert)
    mute.execute(payload)

    with pytest.raises(AlertAlreadyMuted):
        mute.execute(payload)


def test_muting_requires_a_reason(fakes: Fakes) -> None:
    with pytest.raises(MuteReasonRequired):
        fakes.use_case(MuteAlert).execute(
            MuteAlertInput(
                fingerprint="abc123",
                alert_type=AlertType.MEMBER_CONFLICT,
                reason="   ",
            )
        )


def test_unmuting_an_unknown_id_is_not_found(fakes: Fakes) -> None:
    with pytest.raises(MutedAlertNotFound):
        fakes.use_case(UnmuteAlert).execute(uid(999))


def test_the_default_window_starts_at_the_current_sprint(
    world: World, fakes: Fakes
) -> None:
    """§8: da sprint atual (RN12) até a última cadastrada.

    O passado já aconteceu: um conflito na Sprint 17 não é acionável.
    """
    world.sprints(16, 20)
    dados_a = world.squad("Dados-A")
    world.join(dados_a, world.member("Bianca"), 17)
    crm = world.project("CRM")
    world.allocate(world.initiative(crm, "Reestruturação"), 17, squad=dados_a)
    world.allocate(world.initiative(crm, "Dispatch"), 17, squad=dados_a)

    default = fakes.use_case(ListAlerts).execute()
    widened = fakes.use_case(ListAlerts).execute(AlertsQuery(sprint_from=16))

    assert sprints_with(default.items, AlertType.SQUAD_OVERLOADED) == []
    assert sprints_with(widened.items, AlertType.SQUAD_OVERLOADED) == [17]


def test_without_any_sprint_there_is_nothing_to_alert(fakes: Fakes) -> None:
    view = fakes.use_case(ListAlerts).execute()

    assert view.items == ()
    assert view.muted_count == 0
