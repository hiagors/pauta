"""Exportar o snapshot (`POST /snapshots/export`, `pauta snapshot export`).

Três linhas, e é justamente o ponto: a decisão de "o que é o banco inteiro" é
`SnapshotStore`, a de "como isso vira arquivo" é `SnapshotWriter`, e o use case
só amarra as duas. Trocar JSON por outro formato não passa por aqui.

O export é leitura: não escreve nada no banco e não precisa de transação
própria. O debounce da RNF3 também não é assunto deste módulo — ele vive no
adapter, e nem o domínio nem o use case sabem dele.
"""

from dataclasses import dataclass

from app.application.dto.snapshots import ExportSnapshotResultView, SnapshotCountsView
from app.domain.ports.snapshot import SnapshotStore, SnapshotWriter


@dataclass(frozen=True)
class ExportSnapshot:
    store: SnapshotStore
    writer: SnapshotWriter

    def execute(self) -> ExportSnapshotResultView:
        bundle = self.store.dump()
        return ExportSnapshotResultView(
            paths=self.writer.write(bundle),
            counts=SnapshotCountsView.of(bundle),
        )
