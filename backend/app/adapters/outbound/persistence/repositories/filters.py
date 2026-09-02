"""Dois filtros que todo repositório repete, com a semântica dos fakes (§11).

Os fakes da Fase 2 fixaram o contrato; aqui ele é traduzido para SQL:

- **coleção vazia filtra tudo.** `sprint_ids=None` é "sem filtro";
  `sprint_ids=()` é "nenhuma sprint" e devolve lista vazia. O `IN ()` do
  SQLAlchemy já rende uma expressão sempre falsa, então basta não pular o
  `where`;
- **`?q=` é pedaço do nome, sem diferenciar maiúscula.** Com `casefold()` dos
  dois lados, e não com o `lower()` nativo do SQLite, que só dobra ASCII e
  faria "REESTRUTURAÇÃO" não achar "Reestruturação" (ver
  `session._register_casefold`).
"""

from collections.abc import Collection
from typing import Any

from sqlalchemy import ColumnElement, func
from sqlalchemy.orm import Mapped

from app.adapters.outbound.persistence.session import CASEFOLD

_LIKE_ESCAPE = "\\"

#: A função registrada em cada conexão por `session._register_casefold`. Vem do
#: `getattr` para o nome ter uma fonte só.
_casefold = getattr(func, CASEFOLD)


def contains_text(column: Mapped[str], query: str) -> ColumnElement[bool]:
    """`%` e `_` digitados na busca são texto, não curinga."""
    needle = query.strip().casefold()
    for special in (_LIKE_ESCAPE, "%", "_"):
        needle = needle.replace(special, _LIKE_ESCAPE + special)
    return _casefold(column).like(f"%{needle}%", escape=_LIKE_ESCAPE)


def any_of(column: Mapped[Any], values: Collection[Any]) -> ColumnElement[bool]:
    """Coleção vazia devolve a cláusula falsa, não "sem filtro".

    Serve para os filtros por id e para os por enum (`statuses`, `priorities`),
    que têm a mesma regra: `statuses=()` não devolve iniciativa nenhuma.
    """
    return column.in_(list(values))
