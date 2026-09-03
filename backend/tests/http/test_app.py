"""O critério de aceite da Fase 4: `/docs` navegável e todos os endpoints do §8.

A lista `ENDPOINTS` é a transcrição literal da tabela do §8. Ela existe para
que "todos os endpoints existem" seja um teste, e não uma conferência à mão —
e, na direção contrária, para que um endpoint inventado que não está no spec
apareça como falha (`test_the_api_has_no_endpoint_beyond_the_spec`).
"""

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.adapters.inbound.http.deps import provide_timer_factory
from app.adapters.inbound.http.main import API_PREFIX, OPENAPI_URL, create_app
from app.config.settings import DEFAULT_CORS_ORIGINS, Settings
from tests.http.conftest import Api
from tests.persistence.conftest import database_url, upgrade
from tests.snapshot.timers import TimerSpy

#: A tabela do §8, método a método — os dois de snapshot inclusive (Fase 5).
ENDPOINTS: tuple[tuple[str, str], ...] = (
    ("get", "/projects"),
    ("post", "/projects"),
    ("get", "/projects/{project_id}"),
    ("patch", "/projects/{project_id}"),
    ("delete", "/projects/{project_id}"),
    ("get", "/initiatives"),
    ("post", "/initiatives"),
    ("get", "/initiatives/{initiative_id}"),
    ("patch", "/initiatives/{initiative_id}"),
    ("post", "/initiatives/{initiative_id}/status"),
    ("delete", "/initiatives/{initiative_id}"),
    ("get", "/members"),
    ("post", "/members"),
    ("patch", "/members/{member_id}"),
    ("delete", "/members/{member_id}"),
    ("get", "/squads"),
    ("post", "/squads"),
    ("get", "/squads/{squad_id}"),
    ("patch", "/squads/{squad_id}"),
    ("delete", "/squads/{squad_id}"),
    ("get", "/squads/{squad_id}/memberships"),
    ("put", "/squads/{squad_id}/memberships"),
    ("delete", "/squads/{squad_id}/memberships"),
    ("get", "/sprints"),
    ("post", "/sprints"),
    ("get", "/sprints/next/preview"),
    ("post", "/sprints/next"),
    ("get", "/allocations"),
    ("post", "/allocations"),
    ("delete", "/allocations"),
    ("delete", "/allocations/{allocation_id}"),
    ("get", "/planning/grid"),
    ("get", "/planning/backlog"),
    ("get", "/alerts"),
    ("post", "/alerts/mute"),
    ("delete", "/alerts/mute/{mute_id}"),
    ("post", "/snapshots/export"),
    ("post", "/snapshots/import"),
)

#: Os campos de cada resposta do §8, transcritos como a lista de rotas acima.
#:
#: Existe por causa do `C2` da revisão: até aqui o contrato era conferido por
#: rota, e um campo inventado numa resposta passava em silêncio — foi assim que
#: seis deles entraram sem ninguém notar. Campo novo numa resposta agora quebra
#: este teste, e o caminho é escrevê-lo no §8 antes de acrescentá-lo aqui.
RESPONSE_FIELDS: dict[str, tuple[str, ...]] = {
    "AlertOut": (
        "entity_refs",
        "fingerprint",
        "is_muted",
        "message",
        "mute_id",
        "mute_reason",
        "severity",
        "sprint_number",
        "subject_id",
        "type",
    ),
    "AlertsOut": ("items", "muted_count"),
    "AllocationCellOut": ("id", "sprint_number"),
    "AllocationOut": (
        "id",
        "initiative_id",
        "member_id",
        "sprint_id",
        "sprint_number",
        "squad_id",
    ),
    "AllocationResultOut": (
        "alerts",
        "already_existed",
        "created",
        "initiative_status",
        "missing_sprint_numbers",
    ),
    "BacklogItemOut": ("initiative", "project"),
    "BacklogOut": ("items", "summary"),
    "BacklogProjectOut": ("color", "id", "name"),
    "BacklogSummaryOut": ("count", "estimated_sprints_total", "items_without_estimate"),
    "DeallocationResultOut": ("alerts", "initiative_status", "removed"),
    "EntityRefOut": ("id", "name", "type"),
    "ErrorBody": ("code", "details", "message"),
    "ErrorEnvelope": ("error",),
    "GridAssigneeOut": ("id", "kind", "name"),
    "GridBarOut": (
        "allocation_ids",
        "assignee",
        "from_sprint_number",
        "to_sprint_number",
    ),
    "GridGroupOut": ("project", "rows"),
    "GridInitiativeOut": ("id", "layer", "name", "priority", "status"),
    "GridOut": ("alerts_by_sprint", "groups", "sprints"),
    "GridProjectOut": ("color", "id", "is_capacity_reserve", "name"),
    "GridRowOut": ("bars", "initiative"),
    "GridSprintOut": ("end_date", "id", "is_current", "number", "start_date"),
    "InitiativeOut": (
        "description",
        "entered_at",
        "estimated_sprints",
        "id",
        "layer",
        "name",
        "priority",
        "project_id",
        "status",
    ),
    "MemberOut": ("id", "is_active", "name", "role", "short_name"),
    "MutedAlertOut": ("alert_type", "created_at", "fingerprint", "id", "reason"),
    "ProjectDetailOut": ("initiatives", "project"),
    "ProjectOut": (
        "color",
        "description",
        "id",
        "is_active",
        "is_capacity_reserve",
        "name",
    ),
    "SnapshotCountsOut": (
        "allocations",
        "initiatives",
        "members",
        "muted_alerts",
        "projects",
        "sprints",
        "squad_memberships",
        "squads",
    ),
    "SnapshotExportOut": ("counts", "paths"),
    "SnapshotImportOut": ("counts", "mode", "path"),
    "SprintCompositionOut": ("members", "sprint_id", "sprint_number"),
    "SprintOut": ("end_date", "id", "is_current", "number", "start_date"),
    "SprintProposalOut": ("end_date", "number", "start_date"),
    "SquadDetailOut": ("memberships", "squad"),
    "SquadOut": (
        "id",
        "is_active",
        "members",
        "name",
        "representative_member_id",
        "sprint_number",
    ),
}

#: Os filtros de query do §8, endpoint a endpoint. A outra metade do `C2`: o
#: `?descending=` do backlog entrou sem estar escrito em lugar nenhum.
QUERY_PARAMETERS: dict[tuple[str, str], tuple[str, ...]] = {
    ("get", "/alerts"): ("include_muted", "sprint_from", "sprint_to"),
    ("get", "/allocations"): (
        "initiative_id",
        "member_id",
        "project_id",
        "sprint_from",
        "sprint_to",
        "squad_id",
    ),
    ("get", "/initiatives"): ("layer", "priority", "project_id", "q", "status"),
    ("get", "/members"): ("active",),
    ("get", "/planning/backlog"): ("descending", "order_by"),
    ("get", "/planning/grid"): (
        "member_id",
        "project_id",
        "sprint_from",
        "sprint_to",
        "squad_id",
    ),
    ("get", "/projects"): ("active", "q"),
    ("get", "/sprints"): ("from", "to"),
    ("get", "/squads"): ("active", "sprint_number"),
    ("get", "/squads/{squad_id}/memberships"): ("sprint_from", "sprint_to"),
    ("post", "/snapshots/import"): ("confirm",),
}


def _operations(schema: dict[str, Any]) -> set[tuple[str, str]]:
    """`(método, caminho sem prefixo)` de tudo que o OpenAPI publica."""
    return {
        (method, path.removeprefix(API_PREFIX))
        for path, operations in schema["paths"].items()
        for method in operations
    }


def test_the_openapi_document_is_where_the_front_looks_for_it(api: Api) -> None:
    """`mise run types` aponta para este caminho (§4.3, §8)."""
    response = api.client.get(OPENAPI_URL)

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Pauta"


def test_the_docs_page_is_navigable(api: Api) -> None:
    response = api.client.get("/docs")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_every_endpoint_of_the_spec_exists(api: Api) -> None:
    published = _operations(api.client.get(OPENAPI_URL).json())

    missing = [
        f"{method.upper()} {path}"
        for method, path in ENDPOINTS
        if (method, path) not in published
    ]

    assert not missing, "endpoints do §8 que faltam:\n  " + "\n  ".join(missing)


def test_the_api_has_no_endpoint_beyond_the_spec(api: Api) -> None:
    """§14: não inventar endpoint."""
    published = _operations(api.client.get(OPENAPI_URL).json())

    extra = [
        f"{method.upper()} {path}"
        for method, path in sorted(published)
        if (method, path) not in ENDPOINTS
    ]

    assert not extra, "endpoints que o §8 não pede:\n  " + "\n  ".join(extra)


def test_every_response_carries_exactly_the_fields_of_the_spec(api: Api) -> None:
    """§14: não inventar campo. `C2` da revisão das Fases 0 a 5.

    Compara nome a nome, nas duas direções: campo a mais quebra, campo a menos
    quebra, e schema de resposta novo que ninguém transcreveu também.
    """
    published = api.client.get(OPENAPI_URL).json()["components"]["schemas"]
    responses = {
        name: tuple(sorted(body.get("properties", {})))
        for name, body in published.items()
        if name.endswith("Out") or name in {"ErrorBody", "ErrorEnvelope"}
    }
    expected = {name: tuple(sorted(fields)) for name, fields in RESPONSE_FIELDS.items()}

    assert responses == expected


def test_every_query_filter_is_one_the_spec_asks_for(api: Api) -> None:
    """A outra metade: filtro de query que o §8 não pede."""
    schema = api.client.get(OPENAPI_URL).json()
    published = {
        (method, path.removeprefix(API_PREFIX)): tuple(
            sorted(
                parameter["name"]
                for parameter in operation.get("parameters", ())
                if parameter["in"] == "query"
            )
        )
        for path, operations in schema["paths"].items()
        for method, operation in operations.items()
        if any(
            parameter["in"] == "query" for parameter in operation.get("parameters", ())
        )
    }
    expected = {key: tuple(sorted(names)) for key, names in QUERY_PARAMETERS.items()}

    assert published == expected


def test_every_path_is_under_the_versioned_prefix(api: Api) -> None:
    """§12: a API é versionada, e é o que permite a v2 conviver."""
    schema = api.client.get(OPENAPI_URL).json()

    assert all(path.startswith(API_PREFIX) for path in schema["paths"])


def test_the_documented_422_is_the_envelope_of_the_spec(api: Api) -> None:
    """O front tipa o erro a partir daqui (§10.5).

    Sem o `responses` do `main.py`, o OpenAPI publicaria o
    `HTTPValidationError` do FastAPI — um formato que o handler de `errors.py`
    nunca devolve.
    """
    schema = api.client.get(OPENAPI_URL).json()

    documented = {
        operation["responses"]["422"]["content"]["application/json"]["schema"]["$ref"]
        for operations in schema["paths"].values()
        for operation in operations.values()
    }

    assert documented == {"#/components/schemas/ErrorEnvelope"}
    assert "HTTPValidationError" not in schema["components"]["schemas"]


def test_a_patch_body_publishes_every_field_as_optional(api: Api) -> None:
    """Um `PATCH` é parcial (§8), e o schema tem de dizer isso.

    O `openapi-typescript` trata propriedade com `default` como não-opcional:
    com os defaults publicados, o tipo gerado exigiria mandar todos os campos.
    """
    schemas = api.client.get(OPENAPI_URL).json()["components"]["schemas"]

    for name in (
        "ProjectPatchIn",
        "InitiativePatchIn",
        "MemberPatchIn",
        "SquadPatchIn",
    ):
        body = schemas[name]
        assert "required" not in body, name
        assert not [
            field for field in body["properties"].values() if "default" in field
        ], name


def test_a_nullable_patch_field_stays_nullable_and_the_others_do_not(
    api: Api,
) -> None:
    """§8: `color: null` limpa a cor; `name: null` não é pedido válido."""
    color = api.client.get(OPENAPI_URL).json()["components"]["schemas"][
        "ProjectPatchIn"
    ]["properties"]

    assert {"type": "null"} in color["color"]["anyOf"]
    assert color["name"] == {"type": "string", "title": "Name"}


def test_cors_allows_the_astro_dev_server(api: Api) -> None:
    """§10.4: as duas formas de escrever o dev server, sem credenciais."""
    for origin in DEFAULT_CORS_ORIGINS:
        response = api.client.options(
            f"{API_PREFIX}/projects",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
            },
        )

        assert response.headers["access-control-allow-origin"] == origin
        assert "access-control-allow-credentials" not in response.headers


def test_cors_refuses_an_origin_that_is_not_configured(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            database_url="sqlite://",
            snapshot_dir=tmp_path,
            cors_origins=("http://localhost:4321",),
        )
    )

    with TestClient(app) as client:
        response = client.options(
            f"{API_PREFIX}/projects",
            headers={
                "Origin": "http://exemplo.invalido",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert "access-control-allow-origin" not in response.headers


def test_creating_the_application_touches_no_database(tmp_path: Path) -> None:
    """A engine nasce na primeira requisição, não no import (ver `main.py`).

    Uma URL que não abriria banco nenhum é aceita sem reclamar justamente
    porque `create_app` não abre banco.
    """
    assert create_app(
        Settings(
            database_url="sqlite+pysqlite:///nao/existe.sqlite",
            snapshot_dir=tmp_path / "snapshots",
        )
    )


def test_the_application_reads_the_database_url_it_was_given(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """`create_app(settings)` vale para **todos** os campos, não para alguns.

    Duas aplicações, dois bancos, no mesmo processo: o projeto criado na
    primeira não pode aparecer na segunda. Falharia das duas formas que a
    dependência já teve — lendo `DATABASE_URL` do processo (as duas veriam o
    mesmo banco do ambiente) ou memoizando a fábrica num `lru_cache` de módulo
    (a segunda herdaria a engine da primeira).

    O `DATABASE_URL` do ambiente aponta para um caminho que não existe de
    propósito: se alguém voltar a lê-lo, o teste quebra com o erro do SQLite,
    e não com uma asserção obscura.
    """
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///nao/existe.sqlite")
    first, second = tmp_path / "um.sqlite", tmp_path / "dois.sqlite"
    upgrade(first)
    upgrade(second)

    def app_for(path: Path) -> TestClient:
        app = create_app(
            Settings(
                database_url=database_url(path),
                snapshot_dir=tmp_path / "snapshots",
            )
        )
        # Sem isto, o `POST` abaixo deixa um `threading.Timer` de 5 segundos
        # que **não** é daemon (RNF3), e o interpretador o espera no fim da
        # suíte. Aqui só o timer é de teste; o resto do caminho é o de
        # produção, que é o que este teste existe para exercitar.
        app.dependency_overrides[provide_timer_factory] = lambda: TimerSpy()
        return TestClient(app)

    with app_for(first) as client:
        created = client.post(f"{API_PREFIX}/projects", json={"name": "Aurora"})
        assert created.status_code == 201, created.json()
        listed = client.get(f"{API_PREFIX}/projects").json()
        assert [item["name"] for item in listed] == ["Aurora"]

    with app_for(second) as client:
        assert client.get(f"{API_PREFIX}/projects").json() == []


def test_the_session_factory_is_built_once_per_application(tmp_path: Path) -> None:
    """Uma engine por aplicação, não uma por requisição.

    `provide_session_factory` guarda a fábrica em `app.state` na primeira
    requisição. Sem isso, cada requisição abriria uma engine nova — e num
    SQLite de arquivo isso passaria despercebido até o primeiro `:memory:`.
    """
    path = tmp_path / "pauta.sqlite"
    upgrade(path)
    app = create_app(
        Settings(database_url=database_url(path), snapshot_dir=tmp_path / "snapshots")
    )

    with TestClient(app) as client:
        client.get(f"{API_PREFIX}/projects")
        first = app.state.session_factory
        client.get(f"{API_PREFIX}/projects")

    assert app.state.session_factory is first
