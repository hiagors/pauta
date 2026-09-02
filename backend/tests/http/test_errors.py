"""Os códigos de erro do §8, e o formato único do envelope.

`DomainError` -> 422, `NotFoundError` -> 404, `ConflictError` -> 409, tudo pelo
mesmo handler. Os testes daqui não checam a mensagem em português palavra por
palavra: checam o `code`, que é o contrato estável pelo qual a UI decide.
"""

from typing import Any
from uuid import uuid4

from sqlalchemy import Engine, text

from tests.http.conftest import Api


def error(response: Any) -> dict[str, Any]:
    """O corpo do erro, já validado como o envelope do §8."""
    payload = response.json()
    assert set(payload) == {"error"}, payload
    assert set(payload["error"]) == {"code", "message", "details"}, payload
    body: dict[str, Any] = payload["error"]
    return body


def test_an_unknown_id_is_404_with_the_code_of_the_entity(api: Api) -> None:
    response = api.get(f"/projects/{uuid4()}")

    assert response.status_code == 404
    assert error(response)["code"] == "PROJECT_NOT_FOUND"


def test_a_duplicate_name_is_409(api: Api) -> None:
    api.project("CRM")

    response = api.post("/projects", json={"name": "CRM"})

    assert response.status_code == 409
    assert error(response)["code"] == "DUPLICATE_NAME"


def test_a_broken_business_rule_is_422_with_the_code_of_the_rule(api: Api) -> None:
    """Transição de status proibida (§6.3): BACKLOG não vai direto a DONE."""
    project = api.project("CRM")
    initiative = project["initiatives"][0]

    response = api.post(
        f"/initiatives/{initiative['id']}/status", json={"status": "DONE"}
    )

    assert response.status_code == 422
    assert error(response)["code"] == "INVALID_STATUS_TRANSITION"


def test_the_error_details_carry_the_data_the_ui_needs(api: Api) -> None:
    """`details` é o que permite o aviso dizer *qual* sprint, *qual* projeto."""
    project = api.project("CRM")

    response = api.post("/projects", json={"name": "CRM"})

    assert error(response)["details"] == {"entity": "um projeto", "name": "CRM"}
    assert project["project"]["name"] == "CRM"


def test_an_allocation_without_an_assignee_is_422(api: Api) -> None:
    """A invariante é do domínio (`Assignee.from_ids`), não do schema (§6.7)."""
    api.sprints()
    initiative = api.project("CRM")["initiatives"][0]

    response = api.post(
        "/allocations",
        json={
            "initiative_id": initiative["id"],
            "from_sprint_number": 18,
            "to_sprint_number": 18,
        },
    )

    assert response.status_code == 422
    assert error(response)["code"] == "ASSIGNEE_REQUIRED"


def test_an_allocation_with_two_assignees_is_422(api: Api) -> None:
    api.sprints()
    initiative = api.project("CRM")["initiatives"][0]
    squad = api.squad("Dados-A")
    member = api.member("Bianca")

    response = api.post(
        "/allocations",
        json={
            "initiative_id": initiative["id"],
            "from_sprint_number": 18,
            "to_sprint_number": 18,
            "squad_id": squad["id"],
            "member_id": member["id"],
        },
    )

    assert response.status_code == 422
    assert error(response)["code"] == "AMBIGUOUS_ASSIGNEE"


def test_a_malformed_body_is_422_in_the_same_envelope(api: Api) -> None:
    """Sem o handler, este erro sairia no formato do FastAPI e o `lib/api.ts`
    precisaria de dois caminhos."""
    response = api.post("/projects", json={"nome": "CRM"})

    assert response.status_code == 422
    assert error(response)["code"] == "VALIDATION_ERROR"


def test_an_unknown_field_is_refused_instead_of_ignored(api: Api) -> None:
    """`is_capacity_reserv` escrito errado e aceito em silêncio é pior que 422."""
    response = api.post("/projects", json={"name": "CRM", "is_capacity_reserv": True})

    assert response.status_code == 422
    assert error(response)["code"] == "VALIDATION_ERROR"


def test_an_unknown_route_is_404_in_the_same_envelope(api: Api) -> None:
    response = api.get("/nao-existe")

    assert response.status_code == 404
    assert error(response)["code"] == "HTTP_ERROR"


def test_a_failed_request_leaves_nothing_written(api: Api, engine: Engine) -> None:
    """A transação é da requisição: meia operação gravada é pior que nenhuma.

    `PUT /squads/{id}/memberships` grava a composição sprint a sprint e só
    então tropeça no membro inexistente. Sem o `rollback` do `deps.py`, as
    primeiras sprints ficariam gravadas.
    """
    api.sprints()
    squad = api.squad("Dados-A")
    bianca = api.member("Bianca")

    response = api.put(
        f"/squads/{squad['id']}/memberships",
        json={
            "sprint_from": 18,
            "sprint_to": 22,
            "member_ids": [bianca["id"], str(uuid4())],
        },
    )

    assert response.status_code == 404
    assert error(response)["code"] == "MEMBER_NOT_FOUND"
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT count(*) FROM squad_memberships"))
        assert rows.scalar() == 0


def test_a_successful_request_is_committed(api: Api, engine: Engine) -> None:
    """O outro lado da moeda: o repositório faz `flush`, e o `commit` é daqui."""
    api.project("CRM")

    with engine.connect() as connection:
        rows = connection.execute(text("SELECT count(*) FROM projects"))
        assert rows.scalar() == 1
