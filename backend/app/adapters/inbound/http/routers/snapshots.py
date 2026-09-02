"""`/snapshots` (§8, §9).

Os dois endpoints que a Fase 5 acrescenta. O export é o mesmo que o
`mise run snapshot` roda; o import é a restauração da RNF4, e é destrutivo —
por isso o `?confirm=true` do §8, sem o qual a requisição é recusada antes de
qualquer coisa ser apagada.

Este router é o único que **não** agenda o export automático da RNF3: quem
acabou de restaurar uma pasta não quer que o sistema a reescreva antes de ele
olhar o resultado. Quem monta isso é o `main.py`, e o motivo está lá.
"""

from fastapi import APIRouter, Query, status

from app.adapters.inbound.http.deps import PortsDep
from app.adapters.inbound.http.schemas.snapshots import (
    SnapshotExportOut,
    SnapshotImportIn,
    SnapshotImportOut,
)
from app.application.use_cases.snapshots.export import ExportSnapshot
from app.application.use_cases.snapshots.import_ import ImportSnapshot
from app.domain.errors import SnapshotImportNotConfirmed

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


@router.post("/export", summary="Exporta o snapshot")
def export_snapshot(ports: PortsDep) -> SnapshotExportOut:
    """Escreve os arquivos do §9 em `SNAPSHOT_DIR` e devolve os caminhos."""
    return SnapshotExportOut.model_validate(ports.use_case(ExportSnapshot).execute())


@router.post(
    "/import",
    status_code=status.HTTP_200_OK,
    summary="Restaura o banco a partir de um snapshot",
)
def import_snapshot(
    ports: PortsDep,
    body: SnapshotImportIn,
    confirm: bool = Query(
        default=False,
        description="Obrigatório: a importação apaga todos os dados (§8).",
    ),
) -> SnapshotImportOut:
    """Modo `replace` apenas: apaga e recria, na transação da requisição.

    Sem `confirm=true` nada é lido nem apagado — a recusa vem antes de o
    reader abrir a pasta.
    """
    if not confirm:
        raise SnapshotImportNotConfirmed
    return SnapshotImportOut.model_validate(
        ports.use_case(ImportSnapshot).execute(body.to_input())
    )
