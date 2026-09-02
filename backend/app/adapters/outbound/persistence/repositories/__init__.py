"""Implementações SQLAlchemy das portas de `domain/ports/repositories.py`.

Um módulo por agregado, e o prefixo `SqlAlchemy` no nome da classe para que
importar a implementação e o `Protocol` no mesmo arquivo — o que os testes de
contrato fazem — não vire colisão de nome.

Todos recebem uma `Session` e nenhum faz `commit`: a transação é do adapter de
entrada (ver `session.py`).
"""

from app.adapters.outbound.persistence.repositories.allocation import (
    SqlAlchemyAllocationRepository,
)
from app.adapters.outbound.persistence.repositories.initiative import (
    SqlAlchemyInitiativeRepository,
)
from app.adapters.outbound.persistence.repositories.member import (
    SqlAlchemyMemberRepository,
)
from app.adapters.outbound.persistence.repositories.muted_alert import (
    SqlAlchemyMutedAlertRepository,
)
from app.adapters.outbound.persistence.repositories.project import (
    SqlAlchemyProjectRepository,
)
from app.adapters.outbound.persistence.repositories.sprint import (
    SqlAlchemySprintRepository,
)
from app.adapters.outbound.persistence.repositories.squad import (
    SqlAlchemySquadRepository,
)
from app.adapters.outbound.persistence.repositories.squad_membership import (
    SqlAlchemySquadMembershipRepository,
)

__all__ = [
    "SqlAlchemyAllocationRepository",
    "SqlAlchemyInitiativeRepository",
    "SqlAlchemyMemberRepository",
    "SqlAlchemyMutedAlertRepository",
    "SqlAlchemyProjectRepository",
    "SqlAlchemySprintRepository",
    "SqlAlchemySquadMembershipRepository",
    "SqlAlchemySquadRepository",
]
