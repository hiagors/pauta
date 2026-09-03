"""O contrato de erro que o handler único do §8 consome."""

import inspect

import pytest

from app.domain import errors
from app.domain.errors import ConflictError, DomainError, NotFoundError

CONCRETE_ERRORS = [
    obj
    for _, obj in inspect.getmembers(errors, inspect.isclass)
    if issubclass(obj, DomainError)
    and obj not in {DomainError, NotFoundError, ConflictError}
]


def test_there_are_concrete_errors_to_sweep() -> None:
    assert len(CONCRETE_ERRORS) > 20


@pytest.mark.parametrize("error", CONCRETE_ERRORS, ids=lambda cls: cls.__name__)
def test_every_errorhas_a_code(error: type[DomainError]) -> None:
    assert error.code
    assert error.code == error.code.upper()


def test_the_codes_are_unique() -> None:
    codes = [error.code for error in CONCRETE_ERRORS]
    assert len(codes) == len(set(codes))


def test_the_hierarchy_gives_the_http_status() -> None:
    """404 e 409 são subclasses; todo o resto é 422."""
    assert issubclass(errors.SprintNotFound, NotFoundError)
    assert issubclass(errors.AllocationConflict, ConflictError)
    assert issubclass(errors.InvalidStatusTransition, DomainError)
    assert not issubclass(errors.InvalidStatusTransition, NotFoundError)
    assert not issubclass(errors.InvalidStatusTransition, ConflictError)


def test_the_message_is_the_one_the_spec_writes() -> None:
    assert errors.SprintNotFound(number=25).message == "Sprint 25 não existe."


def test_details_carries_what_the_ui_needs() -> None:
    error = errors.SprintNumberGap(19, 20)
    assert error.details == {"expected": 19, "received": 20}


def test_domain_erroris_an_exception() -> None:
    with pytest.raises(DomainError, match="Sprint 25 não existe."):
        raise errors.SprintNotFound(number=25)
