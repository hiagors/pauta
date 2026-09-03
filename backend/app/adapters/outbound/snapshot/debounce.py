"""O debounce de 5 segundos da RNF3.

A cada mutação bem-sucedida o snapshot é reexportado. Sem debounce, editar uma
sprint inteira à mão significaria escrever a pasta sincronizada dezenas de
vezes em um minuto — e o Drive veria dezenas de versões de arquivos idênticos.
`schedule()` derruba o agendamento anterior e marca um novo: uma edição em
sequência coalesce em um export só, 5 segundos depois da última alteração.

Isto é detalhe de adapter. Nem o domínio nem o use case sabem que existe — o
`ExportSnapshot` continua sendo "leia tudo e escreva", e quem decide quando
chamá-lo é a borda (§9).

Duas escolhas com consequência visível:

- **A thread não é `daemon`, e isso precisa ser dito em código.** Um export
  pendente sobrevive ao `Ctrl+C`: o interpretador espera a thread terminar. Na
  prática o desligamento pode demorar até `delay` segundos, e é o preço de não
  perder a última alteração — que é exatamente a que a pessoa acabou de fazer.
  `Thread.daemon` **herda de quem cria a thread**, e quem cria esta é a tarefa
  de fundo da requisição, que o Starlette roda numa worker do anyio — que é
  daemon. Sem `durable_timer` abaixo, a promessa deste parágrafo era falsa e o
  export dos últimos cinco segundos morria com o processo.
- **A exceção do export não sobe.** Ela acontece numa thread, fora de qualquer
  requisição, e derrubar a thread em silêncio esconderia o problema: fica
  registrada no log e o próximo agendamento tenta de novo. Um export que falha
  não pode invalidar a mutação, que já está gravada.
"""

import logging
import threading
from collections.abc import Callable
from typing import Final, Protocol

#: §9. Segundos entre a última mutação e o export.
DEFAULT_DELAY: Final = 5.0

_log = logging.getLogger(__name__)


class Timer(Protocol):
    """O que `threading.Timer` oferece, e tudo o que o debounce usa.

    Existe para o teste poder passar um timer que dispara na hora, em vez de
    a suíte esperar cinco segundos de relógio de verdade.
    """

    def start(self) -> None: ...

    def cancel(self) -> None: ...


#: Assinatura de `threading.Timer(interval, function)`.
type TimerFactory = Callable[[float, Callable[[], None]], Timer]


def durable_timer(delay: float, function: Callable[[], None]) -> Timer:
    """`threading.Timer` que **não** herda o `daemon` de quem o criou.

    É a fábrica default, e a única linha que a torna diferente de
    `threading.Timer` é o `daemon = False` — ver o terceiro parágrafo do topo
    do módulo. Como o timer nasce dentro de uma worker do anyio, o default
    herdado é `True`, e um timer daemon é justamente o que a RNF3 não pode ter:
    o interpretador não o espera.
    """
    timer = threading.Timer(delay, function)
    timer.daemon = False
    return timer


class SnapshotDebouncer:
    """Um por processo, e um método público: `schedule()`.

    Não há `flush()` nem `cancel()` porque nada precisaria deles: a thread não
    é `daemon`, então o export pendente sai no desligamento sem ninguém pedir.
    """

    def __init__(
        self,
        run: Callable[[], None],
        *,
        delay: float = DEFAULT_DELAY,
        timer_factory: TimerFactory = durable_timer,
    ) -> None:
        self._run = run
        self._delay = delay
        self._timer_factory = timer_factory
        self._lock = threading.Lock()
        self._pending: Timer | None = None

    def schedule(self) -> None:
        """Marca um export para `delay` segundos e cancela o anterior."""
        with self._lock:
            self._cancel_pending()
            timer = self._timer_factory(self._delay, self._fire)
            self._pending = timer
        timer.start()

    def _cancel_pending(self) -> None:
        if self._pending is not None:
            self._pending.cancel()
            self._pending = None

    def _fire(self) -> None:
        """Chamado pela thread do timer.

        Não limpa `_pending`: um `schedule()` que chegue no mesmo instante
        pode já ter posto outro timer ali, e apagá-lo faria o agendamento
        seguinte não ter o que cancelar. Cancelar um timer que já disparou é
        no-op, então guardar a referência morta não custa nada.
        """
        try:
            self._run()
        except Exception:
            _log.exception("Falha ao exportar o snapshot automático.")
