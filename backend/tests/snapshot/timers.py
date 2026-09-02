"""Timers de teste para o debounce (RNF3).

O debounce recebe a fábrica de timers pela porta da frente justamente para que
a suíte não precise esperar cinco segundos de relógio de verdade — e para que
"coalescer" possa ser verificado, e não cronometrado.

- `ImmediateTimer` dispara no `start()`. Serve a quem quer o efeito (o arquivo
  aparece depois da mutação) sem se importar com o intervalo.
- `ManualTimer` só dispara quando o teste chama `fire()`. Serve a quem quer
  verificar o cancelamento: é ele que mostra que três agendamentos em sequência
  viram um export.
"""

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class ImmediateTimer:
    """Timer sem espera: `start()` chama a função na hora."""

    delay: float
    function: Callable[[], None]
    cancelled: bool = False

    def start(self) -> None:
        self.function()

    def cancel(self) -> None:
        self.cancelled = True


@dataclass
class ManualTimer:
    """Timer que espera o teste. Registra-se em `created` ao ser construído."""

    delay: float
    function: Callable[[], None]
    cancelled: bool = False
    fired: bool = False

    def start(self) -> None:
        pass

    def cancel(self) -> None:
        self.cancelled = True

    def fire(self) -> None:
        """O que a thread do `threading.Timer` faria ao vencer o intervalo."""
        self.fired = True
        self.function()


@dataclass
class TimerSpy:
    """Fábrica de `ManualTimer` que guarda os que criou."""

    created: list[ManualTimer] = field(default_factory=list)

    def __call__(self, delay: float, function: Callable[[], None]) -> ManualTimer:
        timer = ManualTimer(delay=delay, function=function)
        self.created.append(timer)
        return timer

    @property
    def pending(self) -> ManualTimer:
        """O último criado — o único que não foi cancelado."""
        assert self.created, "nenhum timer foi agendado"
        return self.created[-1]
