"""O debounce da RNF3: coalescer, e não cronometrar.

A propriedade que interessa é "uma edição em sequência vira um export só". Ela
é verificável sem esperar cinco segundos: o timer entra pela porta da frente, e
o teste é quem o dispara.
"""

import logging

import pytest

from app.adapters.outbound.snapshot.debounce import DEFAULT_DELAY, SnapshotDebouncer
from tests.snapshot.timers import TimerSpy


@pytest.fixture
def timers() -> TimerSpy:
    return TimerSpy()


def test_the_default_delay_is_the_five_seconds_of_the_spec(timers: TimerSpy) -> None:
    SnapshotDebouncer(lambda: None, timer_factory=timers).schedule()

    assert timers.pending.delay == DEFAULT_DELAY == 5.0


def test_nothing_is_exported_before_the_timer_fires(timers: TimerSpy) -> None:
    exports: list[int] = []
    debouncer = SnapshotDebouncer(lambda: exports.append(1), timer_factory=timers)

    debouncer.schedule()

    assert exports == []


def test_a_sequence_of_mutations_collapses_into_one_export(
    timers: TimerSpy,
) -> None:
    """É a razão de o debounce existir: editar uma sprint à mão são dezenas de
    mutações, e a pasta sincronizada não precisa de dezenas de versões."""
    exports: list[int] = []
    debouncer = SnapshotDebouncer(lambda: exports.append(1), timer_factory=timers)

    for _ in range(3):
        debouncer.schedule()
    timers.pending.fire()

    assert exports == [1]
    assert [timer.cancelled for timer in timers.created] == [True, True, False]


def test_a_mutation_after_the_export_schedules_another_one(
    timers: TimerSpy,
) -> None:
    exports: list[int] = []
    debouncer = SnapshotDebouncer(lambda: exports.append(1), timer_factory=timers)

    debouncer.schedule()
    timers.pending.fire()
    debouncer.schedule()
    timers.pending.fire()

    assert exports == [1, 1]


def test_a_failed_export_is_logged_and_does_not_escape(
    timers: TimerSpy, caplog: pytest.LogCaptureFixture
) -> None:
    """A exceção acontece numa thread, fora de qualquer requisição. Derrubar a
    thread em silêncio esconderia o problema; deixá-la subir não tem para onde
    subir. E um export que falha não pode invalidar a mutação, que já está
    gravada."""

    def explode() -> None:
        raise OSError("pasta sincronizada indisponível")

    debouncer = SnapshotDebouncer(explode, timer_factory=timers)
    debouncer.schedule()

    with caplog.at_level(logging.ERROR):
        timers.pending.fire()

    assert "Falha ao exportar o snapshot automático." in caplog.text


def test_a_failed_export_does_not_block_the_next_one(timers: TimerSpy) -> None:
    calls: list[int] = []

    def once() -> None:
        calls.append(1)
        if len(calls) == 1:
            raise OSError("primeira tentativa falhou")

    debouncer = SnapshotDebouncer(once, timer_factory=timers)
    debouncer.schedule()
    timers.pending.fire()
    debouncer.schedule()
    timers.pending.fire()

    assert calls == [1, 1]
