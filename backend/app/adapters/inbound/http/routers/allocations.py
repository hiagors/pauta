"""`/allocations` (§7.1, §8)."""

from uuid import UUID

from fastapi import APIRouter

from app.adapters.inbound.http.deps import PortsDep
from app.adapters.inbound.http.schemas.allocations import (
    AllocateRangeIn,
    AllocationOut,
    AllocationResultOut,
    DeallocateRangeIn,
    DeallocationResultOut,
)
from app.application.dto.allocations import AllocationFilter
from app.application.use_cases.planning.allocate_range import AllocateRange
from app.application.use_cases.planning.deallocate import (
    DeallocateCell,
    DeallocateRange,
)
from app.application.use_cases.planning.list_allocations import ListAllocations

router = APIRouter(prefix="/allocations", tags=["alocações"])


@router.get("", summary="Lista alocações")
def list_allocations(
    ports: PortsDep,
    sprint_from: int | None = None,
    sprint_to: int | None = None,
    squad_id: UUID | None = None,
    member_id: UUID | None = None,
    initiative_id: UUID | None = None,
    project_id: UUID | None = None,
) -> list[AllocationOut]:
    """`member_id` aqui é o responsável **direto**. A alocação efetiva do §6.8
    — o que chega pelas squads do membro — é leitura de capacidade, e quem faz
    essa leitura é a grade."""
    filters = AllocationFilter(
        sprint_from=sprint_from,
        sprint_to=sprint_to,
        squad_id=squad_id,
        member_id=member_id,
        initiative_id=initiative_id,
        project_id=project_id,
    )
    return [
        AllocationOut.model_validate(view)
        for view in ports.use_case(ListAllocations).execute(filters)
    ]


@router.post("", summary="Aloca um intervalo de sprints")
def allocate_range(ports: PortsDep, body: AllocateRangeIn) -> AllocationResultOut:
    """200, e não 201: a operação é sobre um intervalo e o resultado é um
    relatório — o que foi criado, o que já existia e que sprint do intervalo
    não existe. Repetir o mesmo pedido não cria nada de novo (RN4)."""
    return AllocationResultOut.model_validate(
        ports.use_case(AllocateRange).execute(body.to_input())
    )


@router.delete("", summary="Desaloca um intervalo de sprints")
def deallocate_range(ports: PortsDep, body: DeallocateRangeIn) -> DeallocationResultOut:
    """RN6: o corpo traz o intervalo. Intervalo sem alocação nenhuma não é
    erro, é operação vazia."""
    return DeallocationResultOut.model_validate(
        ports.use_case(DeallocateRange).execute(body.to_input())
    )


@router.delete("/{allocation_id}", summary="Desaloca uma célula")
def deallocate_cell(ports: PortsDep, allocation_id: UUID) -> DeallocationResultOut:
    return DeallocationResultOut.model_validate(
        ports.use_case(DeallocateCell).execute(allocation_id)
    )
