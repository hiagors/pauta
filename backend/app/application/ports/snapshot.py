"""As portas de arquivo do snapshot (§9).

O writer devolve os caminhos que gerou — o §8 os publica na resposta de
`POST /snapshots/export`, e é a única informação da operação que o usuário
consegue usar. Que formato ele escreve, em que ordem de chaves e com qual
debounce é detalhe de adapter.

O motivo de estas duas não estarem em `domain/ports/` está no `__init__` deste
pacote.
"""

from pathlib import Path
from typing import Protocol

from app.domain.ports.snapshot import SnapshotBundle


class SnapshotWriter(Protocol):
    def write(self, bundle: SnapshotBundle) -> tuple[Path, ...]:
        """Escreve o snapshot e devolve os caminhos gerados."""
        ...


class SnapshotReader(Protocol):
    def read(self, path: Path) -> SnapshotBundle:
        """Lê um snapshot de um diretório."""
        ...
