"""O critério de aceite da Fase 4: `/docs` navegável e todos os endpoints do §8.

A lista `ENDPOINTS` é a transcrição literal da tabela do §8. Ela existe para
que "todos os endpoints existem" seja um teste, e não uma conferência à mão —
e, na direção contrária, para que um endpoint inventado que não está no spec
apareça como falha (`test_the_api_has_no_endpoint_beyond_the_spec`).
"""

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.adapters.inbound.http.main import API_PREFIX, OPENAPI_URL, create_app
from app.config.settings import DEFAULT_CORS_ORIGINS, Settings
from tests.http.conftest import Api

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
