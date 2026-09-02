"""Status da iniciativa e a tabela de transições do §6.3."""

from collections.abc import Mapping
from enum import StrEnum
from typing import Final


class InitiativeStatus(StrEnum):
    BACKLOG = "BACKLOG"
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    DEPRIORITIZED = "DEPRIORITIZED"
    DONE = "DONE"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        return self in _TERMINAL

    @property
    def accepts_allocation(self) -> bool:
        """RN7: só DONE e CANCELLED recusam nova alocação."""
        return not self.is_terminal

    def can_change_to(self, other: InitiativeStatus) -> bool:
        """Transição **manual**. BACKLOG <-> PLANNED não passa por aqui."""
        return other in MANUAL_TRANSITIONS[self]


_TERMINAL: Final[frozenset[InitiativeStatus]] = frozenset(
    {InitiativeStatus.DONE, InitiativeStatus.CANCELLED}
)

#: Transições **manuais** permitidas (§6.3).
#:
#: `BACKLOG -> PLANNED` e `PLANNED -> BACKLOG` estão deliberadamente fora: são
#: automáticas, efeito de ganhar ou perder alocação, e vivem em
#: `Initiative.recalculate_status`. Nada volta para BACKLOG depois de ter
#: começado — o caminho para parar é DEPRIORITIZED, à mão.
MANUAL_TRANSITIONS: Final[Mapping[InitiativeStatus, frozenset[InitiativeStatus]]] = {
    InitiativeStatus.BACKLOG: frozenset({InitiativeStatus.CANCELLED}),
    InitiativeStatus.PLANNED: frozenset(
        {InitiativeStatus.IN_PROGRESS, InitiativeStatus.CANCELLED}
    ),
    InitiativeStatus.IN_PROGRESS: frozenset(
        {
            InitiativeStatus.DEPRIORITIZED,
            InitiativeStatus.DONE,
            InitiativeStatus.CANCELLED,
        }
    ),
    InitiativeStatus.DEPRIORITIZED: frozenset(
        {
            InitiativeStatus.PLANNED,
            InitiativeStatus.IN_PROGRESS,
            InitiativeStatus.CANCELLED,
        }
    ),
    InitiativeStatus.DONE: frozenset(),
    InitiativeStatus.CANCELLED: frozenset(),
}
