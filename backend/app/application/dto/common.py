"""Peças compartilhadas pelos DTOs.

`Unset` existe por causa do `PATCH` (§8): num pedido parcial, "campo ausente" e
"campo com valor nulo" são coisas diferentes. `color: null` limpa a cor do
projeto e faz valer a cor padrão (§6.1); a **ausência** de `color` não mexe no
que está gravado. Um `None` só não consegue dizer as duas coisas.
"""

from typing import Final, TypeIs


class Unset:
    """Marca "o pedido não falou deste campo"."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"


#: Sentinela única. Comparar por identidade não é necessário: use `is_set`.
UNSET: Final = Unset()

#: Campo de PATCH: ou veio um valor (inclusive `None`), ou não veio nada.
type Patch[T] = T | Unset


def is_set[T](value: Patch[T]) -> TypeIs[T]:
    """`True` quando o pedido informou o campo. `None` conta como informado."""
    return not isinstance(value, Unset)
