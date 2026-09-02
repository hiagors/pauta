"""Porta de tempo.

Existe para que `entered_at` (§6.2) e `is_current` (RN12) sejam testáveis.
Nada no domínio chama `date.today()`.
"""

from datetime import date, datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    def today(self) -> date:
        """Data corrente, no fuso local de quem usa o sistema."""
        ...

    def now(self) -> datetime:
        """Instante corrente, em UTC e com timezone."""
        ...
