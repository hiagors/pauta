"""Invariantes de uma sprint (§6.6)."""

from datetime import date

import pytest

from app.domain.entities.sprint import Sprint
from app.domain.errors import InvalidSprintDates, InvalidSprintNumber


def test_o_padrao_do_dado_real_tem_onze_dias() -> None:
    """Sprint 18: segunda 31/08/2026 a sexta 11/09/2026."""
    sprint = Sprint.create(
        number=18, start_date=date(2026, 8, 31), end_date=date(2026, 9, 11)
    )
    assert (sprint.end_date - sprint.start_date).days == 11
    assert sprint.start_date.weekday() == 0
    assert sprint.end_date.weekday() == 4


def test_fim_precisa_ser_posterior_ao_inicio() -> None:
    with pytest.raises(InvalidSprintDates):
        Sprint.create(
            number=18, start_date=date(2026, 8, 31), end_date=date(2026, 8, 31)
        )


def test_numero_precisa_ser_positivo() -> None:
    with pytest.raises(InvalidSprintNumber):
        Sprint.create(
            number=0, start_date=date(2026, 8, 31), end_date=date(2026, 9, 11)
        )


def test_intersects_a_janela_da_grade() -> None:
    sprint = Sprint.create(
        number=18, start_date=date(2026, 8, 31), end_date=date(2026, 9, 11)
    )
    assert sprint.intersects(date(2026, 7, 1), date(2026, 9, 30))
    assert sprint.intersects(date(2026, 9, 11), date(2026, 12, 31))
    assert not sprint.intersects(date(2026, 9, 12), date(2026, 12, 31))


def test_nao_existe_forma_de_excluir_uma_sprint() -> None:
    """D13, do lado do domínio: nada aqui remove sprint."""
    assert not [nome for nome in dir(Sprint) if nome in {"delete", "remove", "archive"}]
