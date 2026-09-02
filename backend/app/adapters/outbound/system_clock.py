"""Implementação da porta `Clock` (§5).

Uma linha por método, e é justamente esse o ponto: `date.today()` existe em
exatamente um lugar do sistema, aqui. O domínio recebe a porta, e é por isso
que `is_current` (RN12) e `entered_at` (§6.2) são testáveis com data fixa.
"""

from datetime import UTC, date, datetime


class SystemClock:
    """Relógio do sistema. `today()` no fuso local, `now()` em UTC."""

    def today(self) -> date:
        return date.today()

    def now(self) -> datetime:
        return datetime.now(UTC)
