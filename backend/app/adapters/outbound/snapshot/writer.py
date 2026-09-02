"""A porta `SnapshotWriter`: o JSON e o Markdown, juntos (§9).

O §9 descreve **um** snapshot com duas naturezas de arquivo — os oito JSON, que
são a fonte da restauração, e os Markdown, que são para ler. A porta é uma só,
então alguém tem de compor as duas metades; é este módulo, e não o use case,
que continua sabendo apenas "escreva o bundle e me diga os caminhos".

A ordem dos caminhos devolvidos é a do §9: os arquivos de entidade, o
`meta.json`, os `plan-sprint-N.md` por número e o `plan-grid.md`.
"""

from dataclasses import dataclass
from pathlib import Path

from app.adapters.outbound.snapshot.json_writer import JsonSnapshotWriter
from app.adapters.outbound.snapshot.markdown_writer import MarkdownSnapshotWriter
from app.domain.ports.clock import Clock
from app.domain.ports.snapshot import SnapshotBundle


@dataclass(frozen=True)
class DirectorySnapshotWriter:
    directory: Path
    clock: Clock

    def write(self, bundle: SnapshotBundle) -> tuple[Path, ...]:
        return (
            *JsonSnapshotWriter(self.directory, self.clock).write(bundle),
            *MarkdownSnapshotWriter(self.directory).write(bundle),
        )
