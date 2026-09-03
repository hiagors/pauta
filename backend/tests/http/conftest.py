"""Apoio da suíte de HTTP (Fase 4).

Três decisões, cada uma com um motivo que custa caro descobrir depois:

- **SQLite em memória, com o schema criado pelas migrations** (RNF2). Não
  `metadata.create_all()`: se a migration não cria a tabela, a suíte não roda.
  Um banco `:memory:` vive dentro da conexão, então a engine usa `StaticPool` e
  a migration recebe **essa** conexão por `config.attributes` — com um pool
  normal, o Alembic migraria um banco descartável e o teste veria um vazio.
- **O relógio é congelado em 02/09/2026**, a mesma data da suíte de use case.
  `is_current` (RN12) e a janela default da grade (RN13) dependem de hoje.
- **A dependência trocada é a fábrica de sessões**, não a `Session`. É o que
  mantém em pé o caminho de verdade do `deps.py`: uma transação por requisição,
  com `commit` no fim e `rollback` na exceção.

A Fase 5 acrescentou uma quarta: **o timer do debounce é do teste, e só ele**.
O que a suíte precisa verificar é a regra da RNF3 — mutação bem-sucedida
agenda, importação não —, e esperar cinco segundos por teste não verificaria
nada melhor. `api.snapshot_scheduled` diz se a mutação agendou;
`api.flush_snapshot()` faz o que a thread do timer faria ao vencer o intervalo.

O que é trocado é `provide_timer_factory`, e não `provide_snapshot_debouncer`.
A diferença é o que separa a suíte de cobrir a RNF3 de fingir que cobre:
substituindo o debouncer inteiro por um lambda, a memoização em `app.state` —
que é o mecanismo do coalescing em produção — não era exercitada por nada, e um
debouncer novo por requisição (zero coalescing) deixaria tudo verde. Com só o
timer trocado, o `run`, a fábrica de sessões e a memoização são os de produção.

Disparar o timer **depois** da resposta não é detalhe de conveniência: a tarefa
de fundo roda antes de a requisição dar `commit` (ver `deps.py`), e é o atraso
do debounce que faz o export ver o dado gravado.
"""

from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from alembic import command
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.pool import StaticPool

from app.adapters.inbound.http.deps import (
    provide_clock,
    provide_session_factory,
    provide_timer_factory,
)
from app.adapters.inbound.http.main import API_PREFIX, create_app
from app.adapters.outbound.persistence.session import make_engine, make_session_factory
from app.config.settings import Settings
from tests.domain.conftest import FrozenClock
from tests.persistence.conftest import alembic_config
from tests.snapshot.timers import TimerSpy

#: Um banco por engine, e a engine morre no fim do teste.
IN_MEMORY_URL = "sqlite+pysqlite:///:memory:"

#: 02/09/2026, a data das confirmações de D15-D17. Cai dentro da Sprint 18.
TODAY = date(2026, 9, 2)

#: A Sprint 18 começa na segunda 31/08/2026 (§6.6).
FIRST_SPRINT_START = date(2026, 8, 31)


@pytest.fixture
def engine() -> Iterator[Engine]:
    engine = make_engine(
        IN_MEMORY_URL,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    with engine.begin() as connection:
        config = alembic_config()
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(TODAY)


class Api:
    """`TestClient` com o prefixo do §8 já embutido.

    Os testes falam em `/projects`, não em `/api/v1/projects`: o prefixo é
    configuração da aplicação, e repeti-lo em cada chamada só faria o dia em
    que ele mudar ser um `sed` em cem linhas.
    """

    def __init__(
        self,
        app: FastAPI,
        client: TestClient,
        snapshot_dir: Path,
        snapshot_timers: TimerSpy,
    ) -> None:
        #: Exposto para o teste da RNF3 poder olhar `app.state`, que é onde o
        #: debounce e a fábrica de sessões são memoizados.
        self.app = app
        self.client = client
        #: A pasta que o export automático da RNF3 escreve.
        self.snapshot_dir = snapshot_dir
        #: Todo timer que o debounce criou, na ordem. Contar timer é como
        #: "coalescer" vira asserção em vez de cronômetro.
        self.snapshot_timers = snapshot_timers

    @property
    def snapshot_scheduled(self) -> bool:
        """Se alguma requisição agendou o export automático (RNF3)."""
        return bool(self.snapshot_timers.created)

    def flush_snapshot(self) -> None:
        """Dispara o export agendado, como a thread do timer faria."""
        self.snapshot_timers.pending.fire()

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.client.get(f"{API_PREFIX}{path}", **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self.client.post(f"{API_PREFIX}{path}", **kwargs)

    def patch(self, path: str, **kwargs: Any) -> Any:
        return self.client.patch(f"{API_PREFIX}{path}", **kwargs)

    def put(self, path: str, **kwargs: Any) -> Any:
        return self.client.put(f"{API_PREFIX}{path}", **kwargs)

    def delete(self, path: str, **kwargs: Any) -> Any:
        """`request`, e não o atalho `delete`: dois `DELETE` do §8 levam corpo
        (o intervalo de alocação e o de composição), e o atalho do httpx não
        aceita `json`."""
        return self.client.request("DELETE", f"{API_PREFIX}{path}", **kwargs)

    # -- atalhos de cenário --------------------------------------------- #
    #
    # O cenário entra pela API, e não escrevendo no banco: é o que faz um
    # endpoint de escrita quebrado derrubar também os testes de leitura que
    # dependem dele, em vez de passar contra um dado plantado à mão.

    def created(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        """`POST` que precisa ter dado certo. Falha alto, com o corpo do erro."""
        response = self.post(path, json=body)
        assert response.status_code == 201, response.json()
        payload: dict[str, Any] = response.json()
        return payload

    def sprints(self, first: int = 18, last: int = 22) -> list[dict[str, Any]]:
        """Sprints contíguas de duas semanas, a partir de 31/08/2026."""
        created: list[dict[str, Any]] = []
        start = FIRST_SPRINT_START + timedelta(days=14 * (first - 18))
        for number in range(first, last + 1):
            created.append(
                self.created(
                    "/sprints",
                    {
                        "number": number,
                        "start_date": start.isoformat(),
                        "end_date": (start + timedelta(days=11)).isoformat(),
                    },
                )
            )
            start += timedelta(days=14)
        return created

    def project(self, name: str, **extra: Any) -> dict[str, Any]:
        """Devolve o `ProjectDetailOut` inteiro: projeto e a iniciativa do RN-I1."""
        return self.created("/projects", {"name": name, **extra})

    def initiative(
        self, project_id: str | UUID, name: str, **extra: Any
    ) -> dict[str, Any]:
        return self.created(
            "/initiatives", {"project_id": str(project_id), "name": name, **extra}
        )

    def member(self, name: str, **extra: Any) -> dict[str, Any]:
        return self.created(
            "/members", {"name": name, "short_name": name.split()[0], **extra}
        )

    def squad(self, name: str, **extra: Any) -> dict[str, Any]:
        return self.created("/squads", {"name": name, **extra})

    def join(
        self, squad_id: str | UUID, member_ids: list[str], first: int, last: int
    ) -> Any:
        response = self.put(
            f"/squads/{squad_id}/memberships",
            json={
                "sprint_from": first,
                "sprint_to": last,
                "member_ids": member_ids,
            },
        )
        assert response.status_code == 200, response.json()
        return response.json()

    def allocate(
        self,
        initiative_id: str | UUID,
        first: int,
        last: int,
        *,
        squad_id: str | None = None,
        member_id: str | None = None,
    ) -> dict[str, Any]:
        response = self.post(
            "/allocations",
            json={
                "initiative_id": str(initiative_id),
                "from_sprint_number": first,
                "to_sprint_number": last,
                "squad_id": squad_id,
                "member_id": member_id,
            },
        )
        assert response.status_code == 200, response.json()
        payload: dict[str, Any] = response.json()
        return payload


@pytest.fixture
def snapshot_dir(tmp_path: Path) -> Path:
    """A pasta sincronizada do teste. Nunca a de verdade."""
    return tmp_path / "snapshots"


@pytest.fixture
def settings(snapshot_dir: Path) -> Settings:
    """Nem a URL nem a pasta vêm do ambiente: as duas são do teste."""
    return Settings(database_url=IN_MEMORY_URL, snapshot_dir=snapshot_dir)


@pytest.fixture
def api(
    engine: Engine, clock: FrozenClock, settings: Settings, snapshot_dir: Path
) -> Iterator[Api]:
    app = create_app(settings)
    factory = make_session_factory(engine)
    app.dependency_overrides[provide_session_factory] = lambda: factory
    app.dependency_overrides[provide_clock] = lambda: clock
    timers = TimerSpy()
    app.dependency_overrides[provide_timer_factory] = lambda: timers
    with TestClient(app) as client:
        yield Api(app, client, snapshot_dir, timers)
