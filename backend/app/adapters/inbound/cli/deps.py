"""Wiring dos comandos (§5).

O equivalente do `http/deps.py`, e com a mesma responsabilidade principal: **a
transação é do comando**. Uma execução que termina bem faz `commit`; uma que
levanta exceção faz `rollback`. É o que faz a importação `replace` — que apaga
o banco antes de recriá-lo — ser tudo ou nada (RNF4).

Aqui não existe o feixe de portas do HTTP: os dois comandos da Fase 5 usam
`SnapshotStore`, `SnapshotWriter` e `SnapshotReader`, e montar os oito
repositórios para não usá-los seria abrir banco à toa.

Nada é lido do ambiente em tempo de import — quem lê é o comando, quando roda.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from app.adapters.outbound.persistence.repositories import SqlAlchemySnapshotStore
from app.adapters.outbound.persistence.session import make_engine, make_session_factory
from app.adapters.outbound.snapshot.reader import DirectorySnapshotReader
from app.adapters.outbound.snapshot.writer import DirectorySnapshotWriter
from app.adapters.outbound.system_clock import SystemClock
from app.config.settings import get_settings


@dataclass(frozen=True)
class CliPorts:
    """As portas que os comandos de snapshot recebem.

    Os nomes dos campos são os dos use cases (`store`, `writer`, `reader`),
    como no `Ports` do HTTP.
    """

    store: SqlAlchemySnapshotStore
    writer: DirectorySnapshotWriter
    reader: DirectorySnapshotReader


@contextmanager
def ports(*, snapshot_dir: Path | None = None) -> Iterator[CliPorts]:
    """Abre a transação do comando e devolve as portas.

    `snapshot_dir` sobrescreve o `SNAPSHOT_DIR` do ambiente — é o `--path` do
    comando, que serve para exportar uma cópia sem mexer na pasta sincronizada.
    """
    settings = get_settings()
    engine = make_engine(settings.database_url)
    try:
        factory = make_session_factory(engine)
        with factory() as session:
            try:
                yield CliPorts(
                    store=SqlAlchemySnapshotStore(session),
                    writer=DirectorySnapshotWriter(
                        directory=snapshot_dir or settings.snapshot_dir,
                        clock=SystemClock(),
                    ),
                    reader=DirectorySnapshotReader(),
                )
            except Exception:
                session.rollback()
                raise
            session.commit()
    finally:
        engine.dispose()
