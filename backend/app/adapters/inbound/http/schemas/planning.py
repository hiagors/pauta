"""Schemas da grade e do backlog (§8).

Formato pensado para renderizar direto, sem o front recalcular nada: as linhas
já vêm agrupadas por projeto, as barras já vêm consolidadas pelo domínio e a
cor já vem resolvida.
"""

from datetime import date
from uuid import UUID

from app.adapters.inbound.http.schemas.common import OutputModel
from app.adapters.inbound.http.schemas.initiatives import InitiativeOut
from app.domain.value_objects.alert import AlertType
from app.domain.value_objects.assignee import AssigneeKind
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.priority import Priority


class GridSprintOut(OutputModel):
    id: UUID
    number: int
    start_date: date
    end_date: date
    is_current: bool


class GridProjectOut(OutputModel):
    """A cor vem resolvida: é o projeto que carrega a cor da grade (§8)."""

    id: UUID
    name: str
    color: str
    is_capacity_reserve: bool


class GridInitiativeOut(OutputModel):
    id: UUID
    name: str
    layer: str | None
    status: InitiativeStatus
    priority: Priority


class GridAssigneeOut(OutputModel):
    """`kind` é `"squad"` ou `"member"` (§8)."""

    kind: AssigneeKind
    id: UUID
    name: str


class GridBarOut(OutputModel):
    """Sprints contíguas do mesmo responsável, já consolidadas.

    Uma pausa no meio gera duas barras. O front desenha barras, não células —
    é o que dá a cara de Gantt.
    """

    assignee: GridAssigneeOut
    from_sprint_number: int
    to_sprint_number: int
    allocation_ids: list[UUID]


class GridRowOut(OutputModel):
    """Uma iniciativa é uma linha. Por RN8 as barras nunca se sobrepõem."""

    initiative: GridInitiativeOut
    bars: list[GridBarOut]


class GridGroupOut(OutputModel):
    project: GridProjectOut
    rows: list[GridRowOut]


class GridOut(OutputModel):
    """`alerts_by_sprint` reporta a sprint **inteira**.

    Os filtros de squad, membro e projeto não o afetam: o ícone no cabeçalho da
    coluna existe para não esconder justamente o conflito que se quer ver (§8).
    A chave é o número da sprint — no JSON ela sai como string, porque é chave
    de objeto.
    """

    sprints: list[GridSprintOut]
    groups: list[GridGroupOut]
    alerts_by_sprint: dict[int, list[AlertType]]


class BacklogProjectOut(OutputModel):
    """Sem `is_capacity_reserve`: o backlog já exclui esses projetos (§8)."""

    id: UUID
    name: str
    color: str


class BacklogItemOut(OutputModel):
    initiative: InitiativeOut
    project: BacklogProjectOut


class BacklogSummaryOut(OutputModel):
    """`estimated_sprints_total` soma **só** quem tem estimativa (§8)."""

    count: int
    estimated_sprints_total: int
    items_without_estimate: int


class BacklogOut(OutputModel):
    items: list[BacklogItemOut]
    summary: BacklogSummaryOut
