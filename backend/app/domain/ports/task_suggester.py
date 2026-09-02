"""Porta da v2, declarada e **não implementada** (§12).

Existe para que, quando a v2 chegar, a orquestração de LLM entre como um
adapter `outbound/llm/` implementando este contrato — sem migração e sem
reescrever o domínio.

Na v1: sem provider, sem SDK, sem chave de API, sem dependência nova, sem
prompt escrito. Nada aqui é chamado por nenhum use case.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID

from app.domain.services.planning_rules import InitiativeRef


@dataclass(frozen=True)
class PlanningContext:
    """O que o time está tocando na sprint, para a sugestão ter contexto."""

    sprint_number: int
    initiatives: tuple[InitiativeRef, ...]


@dataclass(frozen=True)
class SuggestedTask:
    title: str
    initiative_id: UUID | None = None
    notes: str = ""


@runtime_checkable
class TaskSuggester(Protocol):
    def suggest(
        self, transcript: str, context: PlanningContext
    ) -> list[SuggestedTask]: ...
