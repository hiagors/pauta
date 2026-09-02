"""Os oito arquivos de entidade e o `meta.json` (§9).

Cada arquivo é uma lista JSON ordenada por `id`, com chaves ordenadas e
indentação de 2 — as regras estão em `codec.dumps`, num lugar só, porque é
delas que depende o roundtrip byte a byte da Fase 5.

`meta.json` é o único arquivo com timestamp de geração, e por isso é o único
que muda quando nada mudou no dado. Ele fica de fora dos arquivos de entidade
justamente para não sujar o diff dos outros oito (§9).
"""

from dataclasses import dataclass
from pathlib import Path

from app.adapters.outbound.snapshot.codec import (
    ENTITY_FILES,
    FORMAT_VERSION,
    META_FILENAME,
    dumps,
)
from app.domain.ports.clock import Clock
from app.domain.ports.snapshot import SnapshotBundle


@dataclass(frozen=True)
class JsonSnapshotWriter:
    """Implementa `SnapshotWriter` com a parte JSON do §9.

    O `Clock` entra pela porta, como em todo o resto do sistema: é o que faz o
    `generated_at` do `meta.json` ser um valor de teste, e não a hora da
    máquina que rodou a suíte.
    """

    directory: Path
    clock: Clock

    def write(self, bundle: SnapshotBundle) -> tuple[Path, ...]:
        self.directory.mkdir(parents=True, exist_ok=True)
        paths = [
            _write(
                self.directory / spec.filename, spec.rows(getattr(bundle, spec.field))
            )
            for spec in ENTITY_FILES
        ]
        paths.append(self._write_meta(bundle))
        return tuple(paths)

    def _write_meta(self, bundle: SnapshotBundle) -> Path:
        """`format_version` existe para o reader poder recusar o que não
        conhece, em vez de montar entidade errada a partir de um snapshot de
        outra época."""
        return _write(
            self.directory / META_FILENAME,
            {
                "format_version": FORMAT_VERSION,
                "generated_at": self.clock.now().isoformat(),
                "counts": {
                    spec.field: len(getattr(bundle, spec.field))
                    for spec in ENTITY_FILES
                },
            },
        )


def _write(path: Path, payload: object) -> Path:
    path.write_text(dumps(payload), encoding="utf-8")
    return path
