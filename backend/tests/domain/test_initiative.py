"""Iniciativa: os dois caminhos de status não se contaminam (§6.3, RN2, RN7)."""

from datetime import date

import pytest

from app.domain.entities.initiative import Initiative
from app.domain.entities.project import Project
from app.domain.errors import (
    InitiativeNotAllocatable,
    InvalidEstimate,
    InvalidName,
    InvalidStatusTransition,
)
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.priority import Priority
from tests.domain.conftest import FrozenClock, uid

S = InitiativeStatus


def make(clock: FrozenClock, status: InitiativeStatus = S.BACKLOG) -> Initiative:
    initiative = Initiative.create(
        project_id=uid(1), name="Reestruturação V1", clock=clock
    )
    initiative.status = status
    return initiative


class TestCriacao:
    def test_nasce_em_backlog_com_prioridade_media(self, clock: FrozenClock) -> None:
        initiative = Initiative.create(project_id=uid(1), name="CRM", clock=clock)
        assert initiative.status is S.BACKLOG
        assert initiative.priority is Priority.MEDIUM

    def test_entered_at_vem_do_clock_e_nao_do_relogio_do_sistema(self) -> None:
        clock = FrozenClock(date(2026, 1, 15))
        initiative = Initiative.create(project_id=uid(1), name="CRM", clock=clock)
        assert initiative.entered_at == date(2026, 1, 15)

    def test_nome_e_obrigatorio(self, clock: FrozenClock) -> None:
        with pytest.raises(InvalidName):
            Initiative.create(project_id=uid(1), name="  ", clock=clock)

    def test_camada_vazia_vira_none(self, clock: FrozenClock) -> None:
        initiative = Initiative.create(
            project_id=uid(1), name="CRM", clock=clock, layer="  "
        )
        assert initiative.layer is None

    @pytest.mark.parametrize("estimate", [0, -1])
    def test_estimativa_precisa_ser_maior_que_zero(
        self, clock: FrozenClock, estimate: int
    ) -> None:
        with pytest.raises(InvalidEstimate):
            Initiative.create(
                project_id=uid(1),
                name="CRM",
                clock=clock,
                estimated_sprints=estimate,
            )

    def test_estimativa_ausente_e_valida(self, clock: FrozenClock) -> None:
        initiative = Initiative.create(project_id=uid(1), name="CRM", clock=clock)
        assert initiative.estimated_sprints is None

    def test_a_iniciativa_nao_tem_a_flag_de_reserva(self) -> None:
        """§6.2: `is_capacity_reserve` é herdado do projeto."""
        assert "is_capacity_reserve" not in Initiative.__dataclass_fields__


class TestPrimeiraIniciativaDoProjeto:
    def test_rn_i1_herda_o_nome_do_projeto(self, clock: FrozenClock) -> None:
        project = Project.create(name="Dispatch Service")
        initiative = Initiative.create_first_for_project(project, clock)
        assert initiative.project_id == project.id
        assert initiative.name == "Dispatch Service"
        assert initiative.priority is Priority.MEDIUM
        assert initiative.status is S.BACKLOG

    def test_o_nome_e_editavel_em_seguida(self, clock: FrozenClock) -> None:
        project = Project.create(name="CRM")
        initiative = Initiative.create_first_for_project(project, clock)
        initiative.rename("Reestruturação V1")
        assert initiative.name == "Reestruturação V1"
        assert project.name == "CRM"


class TestRecalculateStatus:
    def test_primeira_alocacao_leva_backlog_para_planned(
        self, clock: FrozenClock
    ) -> None:
        initiative = make(clock, S.BACKLOG)
        initiative.recalculate_status(has_allocations=True)
        assert initiative.status is S.PLANNED

    def test_perder_todas_leva_planned_de_volta_para_backlog(
        self, clock: FrozenClock
    ) -> None:
        initiative = make(clock, S.PLANNED)
        initiative.recalculate_status(has_allocations=False)
        assert initiative.status is S.BACKLOG

    @pytest.mark.parametrize(
        "status", [S.IN_PROGRESS, S.DEPRIORITIZED, S.DONE, S.CANCELLED]
    )
    @pytest.mark.parametrize("has_allocations", [True, False])
    def test_os_outros_quatro_status_nao_sao_tocados(
        self, clock: FrozenClock, status: InitiativeStatus, has_allocations: bool
    ) -> None:
        initiative = make(clock, status)
        initiative.recalculate_status(has_allocations=has_allocations)
        assert initiative.status is status

    def test_em_progresso_que_perde_tudo_continua_em_progresso(
        self, clock: FrozenClock
    ) -> None:
        """§6.3: se é para parar, o caminho é DEPRIORITIZED, à mão."""
        initiative = make(clock, S.IN_PROGRESS)
        initiative.recalculate_status(has_allocations=False)
        assert initiative.status is S.IN_PROGRESS

    def test_e_idempotente(self, clock: FrozenClock) -> None:
        initiative = make(clock, S.BACKLOG)
        initiative.recalculate_status(has_allocations=True)
        initiative.recalculate_status(has_allocations=True)
        assert initiative.status is S.PLANNED


class TestChangeStatus:
    def test_transicao_valida(self, clock: FrozenClock) -> None:
        initiative = make(clock, S.PLANNED)
        initiative.change_status(S.IN_PROGRESS)
        assert initiative.status is S.IN_PROGRESS

    def test_transicao_para_o_mesmo_status_e_no_op(self, clock: FrozenClock) -> None:
        initiative = make(clock, S.DONE)
        initiative.change_status(S.DONE)
        assert initiative.status is S.DONE

    @pytest.mark.parametrize(
        ("current", "requested"),
        [
            (S.PLANNED, S.BACKLOG),
            (S.IN_PROGRESS, S.BACKLOG),
            (S.BACKLOG, S.PLANNED),
            (S.DONE, S.IN_PROGRESS),
            (S.CANCELLED, S.PLANNED),
            (S.BACKLOG, S.DONE),
        ],
    )
    def test_transicao_invalida_e_erro(
        self, clock: FrozenClock, current: InitiativeStatus, requested: InitiativeStatus
    ) -> None:
        initiative = make(clock, current)
        with pytest.raises(InvalidStatusTransition) as excinfo:
            initiative.change_status(requested)
        assert excinfo.value.details["current"] == current.value
        assert excinfo.value.details["requested"] == requested.value
        assert initiative.status is current

    def test_retomar_do_deprioritizado_e_manual(self, clock: FrozenClock) -> None:
        initiative = make(clock, S.DEPRIORITIZED)
        initiative.change_status(S.IN_PROGRESS)
        assert initiative.status is S.IN_PROGRESS


class TestAceitaAlocacao:
    @pytest.mark.parametrize(
        "status", [S.BACKLOG, S.PLANNED, S.IN_PROGRESS, S.DEPRIORITIZED]
    )
    def test_aceita(self, clock: FrozenClock, status: InitiativeStatus) -> None:
        make(clock, status).ensure_accepts_allocation()

    @pytest.mark.parametrize("status", [S.DONE, S.CANCELLED])
    def test_terminal_recusa(
        self, clock: FrozenClock, status: InitiativeStatus
    ) -> None:
        initiative = make(clock, status)
        with pytest.raises(InitiativeNotAllocatable):
            initiative.ensure_accepts_allocation()

    def test_deprioritizado_aceita_e_continua_deprioritizado(
        self, clock: FrozenClock
    ) -> None:
        """RN7: retomar é decisão manual, não efeito de arrastar uma barra."""
        initiative = make(clock, S.DEPRIORITIZED)
        initiative.ensure_accepts_allocation()
        initiative.recalculate_status(has_allocations=True)
        assert initiative.status is S.DEPRIORITIZED
