"""DTOs da grade e do backlog (§8, `planning/grid` e `planning/backlog`).

Formato pensado para renderizar direto, sem o front recalcular nada: as linhas
já vêm agrupadas por projeto, as barras já vêm consolidadas e a cor já vem
resolvida.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Self
from uuid import UUID

from app.application.dto.initiatives import InitiativeView
from app.domain.entities.project import Project
from app.domain.value_objects.alert import AlertType
from app.domain.value_objects.assignee import AssigneeKind
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.priority import Priority


@dataclass(frozen=True)
class GridQuery:
    """Sem `sprint_from`/`sprint_to`, a janela é o trimestre corrente (RN13)."""

    sprint_from: int | None = None
    sprint_to: int | None = None
    squad_id: UUID | None = None
    member_id: UUID | None = None
    project_id: UUID | None = None


@dataclass(frozen=True)
class GridSprintView:
    id: UUID
    number: int
    start_date: date
    end_date: date
    is_current: bool


@dataclass(frozen=True)
class GridProjectView:
    """A cor vem resolvida: é o projeto que carrega a cor da grade (§8)."""

    id: UUID
    name: str
    color: str
    is_capacity_reserve: bool

    @classmethod
    def of(cls, project: Project) -> Self:
        return cls(
            id=project.id,
            name=project.name,
            color=str(project.effective_color),
            is_capacity_reserve=project.is_capacity_reserve,
        )


@dataclass(frozen=True)
class GridInitiativeView:
    id: UUID
    name: str
    layer: str | None
    status: InitiativeStatus
    priority: Priority


@dataclass(frozen=True)
class GridAssigneeView:
    """`kind` é `"squad"` ou `"member"` (§8)."""

    kind: AssigneeKind
    id: UUID
    name: str


@dataclass(frozen=True)
class GridBarView:
    """Sprints contíguas do mesmo responsável, já consolidadas pelo domínio."""

    assignee: GridAssigneeView
    from_sprint_number: int
    to_sprint_number: int
    allocation_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class GridRowView:
    """Uma iniciativa é uma linha. Por RN8 as barras nunca se sobrepõem."""

    initiative: GridInitiativeView
    bars: tuple[GridBarView, ...]


@dataclass(frozen=True)
class GridGroupView:
    project: GridProjectView
    rows: tuple[GridRowView, ...]


@dataclass(frozen=True)
class GridView:
    """`alerts_by_sprint` reporta a sprint **inteira**.

    Os filtros de squad, membro e projeto não o afetam: o ícone no cabeçalho da
    coluna existe para não esconder justamente o conflito que se quer ver (§8).
    """

    sprints: tuple[GridSprintView, ...]
    groups: tuple[GridGroupView, ...]
    alerts_by_sprint: dict[int, tuple[AlertType, ...]]


class BacklogOrder(StrEnum):
    """Valores de `?order_by=` (§8), minúsculos porque viajam na query string."""

    PRIORITY = "priority"
    SIZE = "size"
    ENTERED_AT = "entered_at"


@dataclass(frozen=True)
class BacklogQuery:
    order_by: BacklogOrder = BacklogOrder.PRIORITY
    descending: bool = False


@dataclass(frozen=True)
class BacklogProjectView:
    """Sem `is_capacity_reserve`: o backlog já exclui esses projetos (§8)."""

    id: UUID
    name: str
    color: str

    @classmethod
    def of(cls, project: Project) -> Self:
        return cls(id=project.id, name=project.name, color=str(project.effective_color))


@dataclass(frozen=True)
class BacklogItemView:
    initiative: InitiativeView
    project: BacklogProjectView


@dataclass(frozen=True)
class BacklogSummaryView:
    """`estimated_sprints_total` soma **só** quem tem estimativa (§8)."""

    count: int
    estimated_sprints_total: int
    items_without_estimate: int


@dataclass(frozen=True)
class BacklogView:
    items: tuple[BacklogItemView, ...]
    summary: BacklogSummaryView
