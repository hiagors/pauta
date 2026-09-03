"""A tabela de transições do §6.3, inteira — inclusive as proibidas."""

import pytest

from app.domain.value_objects.initiative_status import (
    MANUAL_TRANSITIONS,
    InitiativeStatus,
)

S = InitiativeStatus

ALLOWED = [
    (S.BACKLOG, S.CANCELLED),
    (S.PLANNED, S.IN_PROGRESS),
    (S.PLANNED, S.CANCELLED),
    (S.IN_PROGRESS, S.DEPRIORITIZED),
    (S.IN_PROGRESS, S.DONE),
    (S.IN_PROGRESS, S.CANCELLED),
    (S.DEPRIORITIZED, S.PLANNED),
    (S.DEPRIORITIZED, S.IN_PROGRESS),
    (S.DEPRIORITIZED, S.CANCELLED),
]


@pytest.mark.parametrize(("current", "requested"), ALLOWED)
def test_the_allowed_manual_transitions(
    current: InitiativeStatus, requested: InitiativeStatus
) -> None:
    assert current.can_change_to(requested)


@pytest.mark.parametrize(
    ("current", "requested"),
    [
        # BACKLOG <-> PLANNED é automático, nunca manual.
        (S.BACKLOG, S.PLANNED),
        (S.PLANNED, S.BACKLOG),
        # Nada volta para BACKLOG depois de ter começado.
        (S.IN_PROGRESS, S.BACKLOG),
        (S.DEPRIORITIZED, S.BACKLOG),
        (S.DONE, S.BACKLOG),
        # Terminais não saem.
        (S.DONE, S.IN_PROGRESS),
        (S.DONE, S.CANCELLED),
        (S.CANCELLED, S.PLANNED),
        (S.CANCELLED, S.DONE),
        # Saltos que a tabela não prevê.
        (S.BACKLOG, S.IN_PROGRESS),
        (S.BACKLOG, S.DONE),
        (S.BACKLOG, S.DEPRIORITIZED),
        (S.PLANNED, S.DONE),
        (S.PLANNED, S.DEPRIORITIZED),
    ],
)
def test_the_forbidden_manual_transitions(
    current: InitiativeStatus, requested: InitiativeStatus
) -> None:
    assert not current.can_change_to(requested)


def test_the_table_covers_every_status() -> None:
    assert set(MANUAL_TRANSITIONS) == set(InitiativeStatus)


def test_terminal_statuses_have_no_exit_and_refuse_allocation() -> None:
    for status in (S.DONE, S.CANCELLED):
        assert status.is_terminal
        assert not status.accepts_allocation
        assert MANUAL_TRANSITIONS[status] == frozenset()


def test_the_other_four_accept_allocation() -> None:
    for status in (S.BACKLOG, S.PLANNED, S.IN_PROGRESS, S.DEPRIORITIZED):
        assert status.accepts_allocation
        assert not status.is_terminal
