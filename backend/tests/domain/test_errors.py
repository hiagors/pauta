"""O contrato de erro que o handler único do §8 consome."""

import inspect

import pytest

from app.domain import errors
from app.domain.errors import ConflictError, DomainError, NotFoundError

CONCRETAS = [
    obj
    for _, obj in inspect.getmembers(errors, inspect.isclass)
    if issubclass(obj, DomainError)
    and obj not in {DomainError, NotFoundError, ConflictError}
]


def test_ha_erros_concretos_para_varrer() -> None:
    assert len(CONCRETAS) > 20


@pytest.mark.parametrize("erro", CONCRETAS, ids=lambda cls: cls.__name__)
def test_todo_erro_tem_code(erro: type[DomainError]) -> None:
    assert erro.code
    assert erro.code == erro.code.upper()


def test_os_codes_sao_unicos() -> None:
    codes = [erro.code for erro in CONCRETAS]
    assert len(codes) == len(set(codes))


def test_a_hierarquia_da_o_status_http() -> None:
    """404 e 409 são subclasses; todo o resto é 422."""
    assert issubclass(errors.SprintNotFound, NotFoundError)
    assert issubclass(errors.AllocationConflict, ConflictError)
    assert issubclass(errors.InvalidStatusTransition, DomainError)
    assert not issubclass(errors.InvalidStatusTransition, NotFoundError)
    assert not issubclass(errors.InvalidStatusTransition, ConflictError)


def test_a_mensagem_do_spec_e_a_que_sai() -> None:
    assert errors.SprintNotFound(number=25).message == "Sprint 25 não existe."


def test_details_carrega_o_que_a_ui_precisa() -> None:
    erro = errors.SprintNumberGap(19, 20)
    assert erro.details == {"expected": 19, "received": 20}


def test_domain_error_e_excecao() -> None:
    with pytest.raises(DomainError, match="Sprint 25 não existe."):
        raise errors.SprintNotFound(number=25)
