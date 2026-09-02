"""A porta `SnapshotReader` (RNF4).

Lê os oito arquivos de entidade de uma pasta e devolve o `SnapshotBundle`. Os
Markdown não são lidos: são derivados, e reconstruir dado a partir de tabela
formatada é como se perde informação.

O que este módulo garante é que uma pasta errada vira erro de domínio com
mensagem em português, e não `KeyError` subindo até um 500:

- pasta ou arquivo que não existe -> `SnapshotNotFound`;
- JSON malformado, campo faltando, tipo trocado, `format_version` desconhecida
  -> `InvalidSnapshot`, dizendo em qual arquivo.

`DomainError` que venha da própria entidade — nome vazio, data invertida —
passa reto: a mensagem dela já é melhor do que qualquer coisa que este módulo
escreveria em volta.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.adapters.outbound.snapshot.codec import (
    ENTITY_FILES,
    FORMAT_VERSION,
    META_FILENAME,
    EntityFile,
)
from app.domain.errors import DomainError, InvalidSnapshot, SnapshotNotFound
from app.domain.ports.snapshot import SnapshotBundle


@dataclass(frozen=True)
class DirectorySnapshotReader:
    def read(self, path: Path) -> SnapshotBundle:
        if not path.is_dir():
            raise SnapshotNotFound(str(path))
        self._check_format(path)
        return SnapshotBundle(
            **{spec.field: self._entities(path, spec) for spec in ENTITY_FILES}
        )

    def _check_format(self, path: Path) -> None:
        """`meta.json` é obrigatório: é o que distingue uma pasta de snapshot
        de uma pasta com JSON dentro, e é onde está a versão do formato."""
        meta = _load(path / META_FILENAME)
        if not isinstance(meta, dict):
            raise InvalidSnapshot(
                f"{META_FILENAME} deveria ser um objeto JSON.", file=META_FILENAME
            )
        version = meta.get("format_version")
        if version != FORMAT_VERSION:
            raise InvalidSnapshot(
                f"formato {version!r} não é suportado; esta versão lê "
                f"{FORMAT_VERSION}.",
                file=META_FILENAME,
                format_version=version,
            )

    def _entities(self, path: Path, spec: EntityFile[Any]) -> tuple[Any, ...]:
        rows = _load(path / spec.filename)
        if not isinstance(rows, list):
            raise InvalidSnapshot(
                f"{spec.filename} deveria ser uma lista JSON.", file=spec.filename
            )
        return tuple(_decode(spec, row) for row in rows)


def _load(path: Path) -> object:
    if not path.is_file():
        raise SnapshotNotFound(str(path))
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise InvalidSnapshot(
            f"{path.name} não é um JSON válido ({error.msg}, linha {error.lineno}).",
            file=path.name,
        ) from error


def _decode(spec: EntityFile[Any], row: object) -> Any:
    if not isinstance(row, dict):
        raise InvalidSnapshot(
            f"{spec.filename} tem um item que não é um objeto JSON.",
            file=spec.filename,
        )
    try:
        return spec.decode(row)
    except DomainError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise InvalidSnapshot(
            f"{spec.filename} tem uma linha que não pôde ser lida ({error}).",
            file=spec.filename,
        ) from error
