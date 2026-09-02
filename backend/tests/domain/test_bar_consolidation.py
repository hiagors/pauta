"""Consolidação de células em barras do Gantt."""

from app.domain.services.bar_consolidation import AllocationCell, consolidate_bars
from app.domain.value_objects.assignee import Assignee
from tests.domain.conftest import uid

DADOS_A = Assignee.for_squad(uid(1))
DADOS_B = Assignee.for_squad(uid(2))
GABRIEL = Assignee.for_member(uid(10))


def cell(sprint_number: int, assignee: Assignee) -> AllocationCell:
    return AllocationCell(
        allocation_id=uid(100 + sprint_number),
        sprint_number=sprint_number,
        assignee=assignee,
    )


def test_sprints_contiguas_do_mesmo_responsavel_viram_uma_barra() -> None:
    bars = consolidate_bars([cell(n, DADOS_A) for n in (18, 19, 20, 21, 22)])
    assert len(bars) == 1
    assert (bars[0].from_sprint_number, bars[0].to_sprint_number) == (18, 22)
    assert len(bars[0].allocation_ids) == 5


def test_a_ordem_de_entrada_nao_importa() -> None:
    bars = consolidate_bars([cell(n, DADOS_A) for n in (20, 18, 22, 19, 21)])
    assert len(bars) == 1
    assert bars[0].allocation_ids == tuple(uid(100 + n) for n in (18, 19, 20, 21, 22))


def test_pausa_no_meio_gera_duas_barras() -> None:
    bars = consolidate_bars([cell(n, DADOS_A) for n in (18, 19, 21, 22)])
    assert [(bar.from_sprint_number, bar.to_sprint_number) for bar in bars] == [
        (18, 19),
        (21, 22),
    ]


def test_troca_de_responsavel_gera_duas_barras() -> None:
    """RN3: uma iniciativa pode ter responsáveis diferentes em sprints diferentes."""
    bars = consolidate_bars([cell(18, DADOS_A), cell(19, DADOS_A), cell(20, DADOS_B)])
    assert len(bars) == 2
    assert bars[0].assignee == DADOS_A
    assert (bars[0].from_sprint_number, bars[0].to_sprint_number) == (18, 19)
    assert bars[1].assignee == DADOS_B
    assert (bars[1].from_sprint_number, bars[1].to_sprint_number) == (20, 20)


def test_squad_e_membro_nunca_se_fundem() -> None:
    bars = consolidate_bars([cell(18, DADOS_A), cell(19, GABRIEL)])
    assert len(bars) == 2


def test_uma_celula_so() -> None:
    bars = consolidate_bars([cell(19, GABRIEL)])
    assert (bars[0].from_sprint_number, bars[0].to_sprint_number) == (19, 19)


def test_sem_celula_nao_ha_barra() -> None:
    assert consolidate_bars([]) == []


def test_as_barras_de_uma_linha_nunca_se_sobrepoem() -> None:
    bars = consolidate_bars([cell(18, DADOS_A), cell(19, DADOS_B), cell(20, DADOS_A)])
    limites = [(bar.from_sprint_number, bar.to_sprint_number) for bar in bars]
    for anterior, seguinte in zip(limites, limites[1:], strict=False):
        assert anterior[1] < seguinte[0]
