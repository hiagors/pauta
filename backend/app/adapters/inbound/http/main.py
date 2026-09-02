"""Fábrica da aplicação (§5, §8, §10.4).

Três coisas e nada mais: CORS, handlers de erro e os routers do §8. Nenhuma
regra de negócio mora aqui, e nenhum router monta erro à mão — quem traduz
exceção para JSON é `errors.py`, num lugar só.

A montagem dos routers carrega uma decisão da RNF3: todos ganham a dependência
que agenda o export do snapshot a cada mutação bem-sucedida, **menos**
`/snapshots`. O motivo está ao lado da chamada.

O `uvicorn` sobe pela fábrica, não por uma instância de módulo
(`mise run dev` → `--factory ...main:create_app`). A diferença importa:
importar este módulo não lê o ambiente e não abre banco. Um
`app = create_app()` no fim do arquivo faria `import main` exigir
`DATABASE_URL`, o que amarraria a suíte de HTTP a uma variável de ambiente que
ela não usa — a engine dela é a de memória.
"""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.inbound.http import errors
from app.adapters.inbound.http.deps import schedule_snapshot_export
from app.adapters.inbound.http.routers import (
    alerts,
    allocations,
    initiatives,
    members,
    planning,
    projects,
    snapshots,
    sprints,
    squads,
)
from app.adapters.inbound.http.schemas.common import ErrorEnvelope
from app.config.settings import Settings, get_settings

#: Prefixo de todo o §8. A versão está no caminho para que a v2 possa conviver.
API_PREFIX = "/api/v1"

#: OpenAPI onde o `mise run types` procura, e a doc navegável em `/docs` (§8).
OPENAPI_URL = f"{API_PREFIX}/openapi.json"

#: O 422 documentado é o envelope do §8, e não o `HTTPValidationError` que o
#: FastAPI publica sozinho: quem responde é o handler de `errors.py`, e um
#: OpenAPI que descreve outro formato faria o front tipar um erro que nunca
#: chega. Vale para toda operação — path, query e corpo são validados em todas.
ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    422: {"model": ErrorEnvelope, "description": "Erro de validação ou de regra"},
}


def create_app(settings: Settings | None = None) -> FastAPI:
    """`settings` explícito existe para o teste; em produção vem do ambiente."""
    config = settings or get_settings()
    app = FastAPI(
        title="Pauta",
        version="1.0.0",
        summary="Planejamento de sprints do time",
        openapi_url=OPENAPI_URL,
        docs_url="/docs",
        redoc_url=None,
    )
    #: As dependências leem as configurações **desta** aplicação daqui, e não
    #: do ambiente do processo (ver `deps.provide_settings`).
    app.state.settings = config
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.cors_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    errors.register(app)
    for router in (
        projects.router,
        initiatives.router,
        members.router,
        squads.router,
        sprints.router,
        allocations.router,
        planning.router,
        alerts.router,
    ):
        app.include_router(
            router,
            prefix=API_PREFIX,
            responses=ERROR_RESPONSES,
            dependencies=[Depends(schedule_snapshot_export)],
        )
    #: `/snapshots` fica fora do agendamento automático de propósito (RNF3): a
    #: importação `replace` não dispara export, e reexportar depois de um
    #: export explícito seria escrever a pasta sincronizada duas vezes pelo
    #: mesmo pedido.
    app.include_router(snapshots.router, prefix=API_PREFIX, responses=ERROR_RESPONSES)
    return app
