"""Calendário de sprints, alocação em intervalo e alocação efetiva."""

from datetime import date, timedelta

import pytest

from app.domain.entities.sprint import Sprint
from app.domain.errors import (
    AllocationConflict,
    SprintNotFound,
    SprintNumberGap,
    SprintNumberTaken,
    SprintOverlap,
)
from app.domain.services import planning_rules as rules
from app.domain.value_objects.assignee import Assignee
from app.domain.value_objects.sprint_range import SprintRange
from tests.domain.conftest import (
    make_ref,
    make_sprint,
    member_alloc,
    membership,
    sprint_18_to_22,
    squad_alloc,
    uid,
)

ALFA = uid(1)
BETA = uid(2)
ANA = uid(10)
CARLA = uid(11)
BRUNO = uid(12)

AURORA = make_ref(50, "Catálogo V1", project_seed=90, project_name="Aurora")
ENVIO = make_ref(51, "Serviço de Envio", project_seed=90, project_name="Aurora")
PORTAL = make_ref(52, "Portal Externo", project_seed=91, project_name="Boreal")
PLANTAO = make_ref(
    53, "Sustentação", project_seed=92, project_name="Plantão", reserve=True
)


class TestSequenciaDeSprints:
    def test_o_dado_real_e_valido(self) -> None:
        rules.validate_sprint_sequence(sprint_18_to_22())

    def test_conjunto_vazio_e_valido(self) -> None:
        rules.validate_sprint_sequence([])

    def test_buraco_na_numeracao_e_erro(self) -> None:
        sprints = [
            make_sprint(18, date(2026, 8, 31)),
            make_sprint(20, date(2026, 9, 28)),
        ]
        with pytest.raises(SprintNumberGap) as excinfo:
            rules.validate_sprint_sequence(sprints)
        assert excinfo.value.details == {"expected": 19, "received": 20}

    def test_numero_repetido_e_erro(self) -> None:
        sprints = [
            make_sprint(18, date(2026, 8, 31)),
            Sprint.create(
                number=18,
                start_date=date(2026, 9, 14),
                end_date=date(2026, 9, 25),
                id=uid(999),
            ),
        ]
        with pytest.raises(SprintNumberTaken):
            rules.validate_sprint_sequence(sprints)

    def test_inicio_da_seguinte_precisa_ser_depois_do_fim_da_anterior(self) -> None:
        sprints = [
            make_sprint(18, date(2026, 8, 31)),
            make_sprint(19, date(2026, 9, 7)),
        ]
        with pytest.raises(SprintOverlap):
            rules.validate_sprint_sequence(sprints)

    def test_ordem_de_entrada_nao_importa(self) -> None:
        rules.validate_sprint_sequence(list(reversed(sprint_18_to_22())))

    def test_a_primeira_sprint_nao_precisa_ser_a_de_numero_um(self) -> None:
        """O time cadastra a 18, que é a que existe na vida real."""
        rules.ensure_can_add_sprint([], make_sprint(18, date(2026, 8, 31)))

    def test_a_sprint_nova_precisa_ser_a_seguinte(self) -> None:
        existing = sprint_18_to_22()
        rules.ensure_can_add_sprint(existing, make_sprint(23, date(2026, 11, 9)))
        with pytest.raises(SprintNumberGap):
            rules.ensure_can_add_sprint(existing, make_sprint(24, date(2026, 11, 23)))


class TestSprintAtual:
    def test_e_a_de_maior_inicio_que_ja_passou(self) -> None:
        sprints = sprint_18_to_22()
        atual = rules.current_sprint(sprints, date(2026, 9, 2))
        assert atual is not None
        assert atual.number == 18

    def test_no_primeiro_dia_a_sprint_ja_e_a_atual(self) -> None:
        sprints = sprint_18_to_22()
        atual = rules.current_sprint(sprints, date(2026, 9, 14))
        assert atual is not None
        assert atual.number == 19

    def test_folga_de_calendario_nao_deixa_o_sistema_sem_sprint_atual(self) -> None:
        """RN12: uma sprint só termina de verdade quando a próxima começa."""
        sprints = [
            make_sprint(18, date(2026, 8, 31)),
            make_sprint(19, date(2026, 9, 21)),
        ]
        atual = rules.current_sprint(sprints, date(2026, 9, 16))
        assert atual is not None
        assert atual.number == 18
        assert atual.end_date < date(2026, 9, 16)

    def test_sem_sprint_iniciada_nao_ha_sprint_atual(self) -> None:
        sprints = sprint_18_to_22()
        assert rules.current_sprint(sprints, date(2026, 8, 1)) is None
        assert all(not rules.is_current(s, sprints, date(2026, 8, 1)) for s in sprints)

    def test_is_current_marca_uma_e_so_uma(self) -> None:
        sprints = sprint_18_to_22()
        hoje = date(2026, 9, 20)
        marcadas = [s for s in sprints if rules.is_current(s, sprints, hoje)]
        assert [s.number for s in marcadas] == [19]


class TestProximaSprint:
    def test_proposta_segue_o_padrao_do_rn10(self) -> None:
        proposta = rules.propose_next_sprint(sprint_18_to_22())
        assert proposta.number == 23
        assert proposta.start_date == date(2026, 11, 9)
        assert proposta.start_date.weekday() == 0
        assert (proposta.end_date - proposta.start_date).days == 11
        assert proposta.end_date.weekday() == 4

    def test_a_segunda_seguinte_e_estritamente_depois(self) -> None:
        assert rules.next_monday_after(date(2026, 9, 11)) == date(2026, 9, 14)
        assert rules.next_monday_after(date(2026, 9, 14)) == date(2026, 9, 21)

    def test_a_proposta_nao_se_sobrepoe_a_ultima(self) -> None:
        sprints = sprint_18_to_22()
        proposta = rules.propose_next_sprint(sprints)
        rules.ensure_can_add_sprint(
            sprints,
            Sprint.create(
                number=proposta.number,
                start_date=proposta.start_date,
                end_date=proposta.end_date,
                id=uid(777),
            ),
        )

    def test_sem_sprint_cadastrada_nao_ha_o_que_propor(self) -> None:
        with pytest.raises(SprintNotFound):
            rules.propose_next_sprint([])


class TestJanelaDaGrade:
    def test_trimestre_civil_da_data_de_hoje(self) -> None:
        assert rules.civil_quarter_bounds(date(2026, 9, 2)) == (
            date(2026, 7, 1),
            date(2026, 9, 30),
        )
        assert rules.civil_quarter_bounds(date(2026, 1, 1)) == (
            date(2026, 1, 1),
            date(2026, 3, 31),
        )
        assert rules.civil_quarter_bounds(date(2026, 12, 31)) == (
            date(2026, 10, 1),
            date(2026, 12, 31),
        )

    def test_a_grade_default_traz_quem_intersecta_o_trimestre(self) -> None:
        sprints = sprint_18_to_22()
        janela = rules.sprints_in_quarter(sprints, date(2026, 9, 2))
        assert [s.number for s in janela] == [18, 19, 20]

    def test_sprint_que_atravessa_a_virada_do_trimestre_entra_nos_dois(self) -> None:
        atravessa = make_sprint(21, date(2026, 9, 28))
        assert atravessa.end_date == date(2026, 10, 9)
        assert rules.sprints_in_quarter([atravessa], date(2026, 9, 2))
        assert rules.sprints_in_quarter([atravessa], date(2026, 10, 15))


class TestPlanoDeAlocacao:
    def make_range(self) -> SprintRange:
        return SprintRange(18, 22)

    def test_intervalo_inteiro_livre(self) -> None:
        plano = rules.plan_allocation(
            initiative_id=AURORA.id,
            sprint_range=self.make_range(),
            assignee=Assignee.for_squad(ALFA),
            existing_sprint_numbers={18, 19, 20, 21, 22},
            occupied={},
        )
        assert plano.to_create == (18, 19, 20, 21, 22)
        assert plano.already_existing == ()
        assert plano.missing_sprint_numbers == ()

    def test_rn1_alocar_e_idempotente(self) -> None:
        squad = Assignee.for_squad(ALFA)
        plano = rules.plan_allocation(
            initiative_id=AURORA.id,
            sprint_range=self.make_range(),
            assignee=squad,
            existing_sprint_numbers={18, 19, 20, 21, 22},
            occupied={19: squad, 20: squad},
        )
        assert plano.to_create == (18, 21, 22)
        assert plano.already_existing == (19, 20)

    def test_rn5_sprint_inexistente_nao_derruba_a_operacao(self) -> None:
        plano = rules.plan_allocation(
            initiative_id=AURORA.id,
            sprint_range=self.make_range(),
            assignee=Assignee.for_squad(ALFA),
            existing_sprint_numbers={18, 19, 20},
            occupied={},
        )
        assert plano.to_create == (18, 19, 20)
        assert plano.missing_sprint_numbers == (21, 22)

    def test_rn8_outro_responsavel_na_mesma_celula_e_conflito(self) -> None:
        with pytest.raises(AllocationConflict) as excinfo:
            rules.plan_allocation(
                initiative_id=AURORA.id,
                sprint_range=SprintRange(18, 20),
                assignee=Assignee.for_squad(ALFA),
                existing_sprint_numbers={18, 19, 20},
                occupied={19: Assignee.for_squad(BETA)},
            )
        detalhes = excinfo.value.details
        assert detalhes["sprint_number"] == 19
        assert detalhes["occupant_kind"] == "squad"
        assert detalhes["occupant_id"] == str(BETA)

    def test_membro_ocupando_a_celula_de_uma_squad_tambem_e_conflito(self) -> None:
        with pytest.raises(AllocationConflict) as excinfo:
            rules.plan_allocation(
                initiative_id=AURORA.id,
                sprint_range=SprintRange(19, 19),
                assignee=Assignee.for_squad(ALFA),
                existing_sprint_numbers={19},
                occupied={19: Assignee.for_member(BRUNO)},
            )
        assert excinfo.value.details["occupant_kind"] == "member"


class TestAlocacaoEfetiva:
    def snapshot(self) -> rules.PlanningSnapshot:
        return rules.PlanningSnapshot(
            sprint_numbers=(18, 19, 20),
            allocations=(
                squad_alloc(19, AURORA, ALFA),
                squad_alloc(19, PORTAL, BETA),
                member_alloc(19, ENVIO, BRUNO),
                squad_alloc(20, PLANTAO, ALFA),
            ),
            memberships=(
                membership(19, ALFA, ANA),
                membership(19, BETA, ANA),
                membership(19, ALFA, CARLA),
                membership(20, ALFA, CARLA),
            ),
            squads={ALFA: "Alfa", BETA: "Beta"},
            members={ANA: "Ana", CARLA: "Carla", BRUNO: "Bruno"},
            current_sprint_number=19,
        )

    def test_uniao_de_direta_e_via_squad(self) -> None:
        efetivas = rules.effective_initiatives(
            self.snapshot(),
            member_id=ANA,
            sprint_number=19,
            include_capacity_reserve=False,
        )
        assert {ref.id for ref in efetivas} == {AURORA.id, PORTAL.id}

    def test_alocacao_direta_conta(self) -> None:
        efetivas = rules.effective_initiatives(
            self.snapshot(),
            member_id=BRUNO,
            sprint_number=19,
            include_capacity_reserve=False,
        )
        assert [ref.id for ref in efetivas] == [ENVIO.id]

    def test_a_composicao_e_por_sprint_e_nao_vaza(self) -> None:
        efetivas = rules.effective_initiatives(
            self.snapshot(),
            member_id=ANA,
            sprint_number=18,
            include_capacity_reserve=False,
        )
        assert efetivas == ()

    def test_reserva_sai_do_conjunto_antes_da_verificacao_de_conflito(self) -> None:
        snapshot = self.snapshot()
        sem_reserva = rules.effective_initiatives(
            snapshot,
            member_id=CARLA,
            sprint_number=20,
            include_capacity_reserve=False,
        )
        com_reserva = rules.effective_initiatives(
            snapshot,
            member_id=CARLA,
            sprint_number=20,
            include_capacity_reserve=True,
        )
        assert sem_reserva == ()
        assert [ref.id for ref in com_reserva] == [PLANTAO.id]

    def test_iniciativas_da_squad(self) -> None:
        iniciativas = rules.squad_initiatives(
            self.snapshot(),
            squad_id=ALFA,
            sprint_number=19,
            include_capacity_reserve=False,
        )
        assert [ref.id for ref in iniciativas] == [AURORA.id]

    def test_a_saida_e_ordenada_e_sem_repeticao(self) -> None:
        snapshot = rules.PlanningSnapshot(
            sprint_numbers=(19,),
            allocations=(
                squad_alloc(19, PORTAL, ALFA),
                squad_alloc(19, AURORA, BETA),
                member_alloc(19, AURORA, ANA),
            ),
            memberships=(
                membership(19, ALFA, ANA),
                membership(19, BETA, ANA),
            ),
            squads={ALFA: "Alfa", BETA: "Beta"},
            members={ANA: "Ana"},
        )
        efetivas = rules.effective_initiatives(
            snapshot, member_id=ANA, sprint_number=19, include_capacity_reserve=False
        )
        assert [ref.label for ref in efetivas] == [
            "Aurora / Catálogo V1",
            "Boreal / Portal Externo",
        ]


class TestIdleFrom:
    def test_comeca_na_sprint_atual(self) -> None:
        snapshot = rules.PlanningSnapshot(
            sprint_numbers=(18, 19, 20), current_sprint_number=19
        )
        assert snapshot.idle_from == 19

    def test_sem_sprint_atual_toda_a_janela_e_futura(self) -> None:
        snapshot = rules.PlanningSnapshot(sprint_numbers=(18, 19, 20))
        assert snapshot.idle_from == 18

    def test_janela_vazia(self) -> None:
        assert rules.PlanningSnapshot(sprint_numbers=()).idle_from is None


def test_o_padrao_de_duracao_bate_com_o_dado_real() -> None:
    start = date(2026, 8, 31)
    assert start + timedelta(days=rules.DEFAULT_SPRINT_LENGTH_DAYS) == date(2026, 9, 11)
