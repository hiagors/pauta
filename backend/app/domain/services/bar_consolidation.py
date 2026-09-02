"""Consolidação de células de alocação em barras do Gantt (§8, `planning/grid`).

O front desenha barras, não células — é o que dá a cara de Gantt. Quem
consolida é o backend, para o front não recalcular nada.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from app.domain.value_objects.assignee import Assignee


@dataclass(frozen=True)
class AllocationCell:
    """Uma alocação já resolvida para o número da sprint."""

    allocation_id: UUID
    sprint_number: int
    assignee: Assignee


@dataclass(frozen=True)
class Bar:
    assignee: Assignee
    from_sprint_number: int
    to_sprint_number: int
    allocation_ids: tuple[UUID, ...]


def consolidate_bars(cells: Iterable[AllocationCell]) -> list[Bar]:
    """Funde células **consecutivas** do mesmo responsável em uma barra.

    Um buraco no meio (frente pausada) ou uma troca de responsável abre barra
    nova. A contiguidade é medida pelo número da sprint, o que é seguro porque
    a numeração não tem buraco (§6.6).

    Por RN8 nunca há duas células no mesmo número para a mesma iniciativa, então
    as barras de uma linha nunca se sobrepõem.
    """
    ordered = sorted(cells, key=lambda cell: cell.sprint_number)
    bars: list[Bar] = []
    for cell in ordered:
        last = bars[-1] if bars else None
        if (
            last is not None
            and last.assignee == cell.assignee
            and last.to_sprint_number + 1 == cell.sprint_number
        ):
            bars[-1] = Bar(
                assignee=last.assignee,
                from_sprint_number=last.from_sprint_number,
                to_sprint_number=cell.sprint_number,
                allocation_ids=(*last.allocation_ids, cell.allocation_id),
            )
            continue
        bars.append(
            Bar(
                assignee=cell.assignee,
                from_sprint_number=cell.sprint_number,
                to_sprint_number=cell.sprint_number,
                allocation_ids=(cell.allocation_id,),
            )
        )
    return bars
