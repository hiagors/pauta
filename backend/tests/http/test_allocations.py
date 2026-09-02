"""`/allocations` pela borda HTTP (§7.1, §8)."""

from uuid import uuid4

from tests.http.conftest import Api


def test_allocating_an_interval_reports_what_it_did(api: Api) -> None:
    """§8: `created`, `already_existed` e `missing_sprint_numbers`.

    O intervalo pedido vai da 21 à 24; só a 21 e a 22 existem, e as duas que
    faltam entram no relatório em vez de derrubar a operação (RN5).
    """
    api.sprints()
    initiative = api.project("CRM")["initiatives"][0]
    squad = api.squad("Dados-A")

    result = api.allocate(initiative["id"], 21, 24, squad_id=squad["id"])

    assert [cell["sprint_number"] for cell in result["created"]] == [21, 22]
    assert result["already_existed"] == []
    assert result["missing_sprint_numbers"] == [23, 24]


def test_allocating_promotes_the_initiative_out_of_the_backlog(api: Api) -> None:
    """RN2: ganhar alocação leva `BACKLOG` a `PLANNED`, automaticamente."""
    api.sprints()
    initiative = api.project("CRM")["initiatives"][0]
    squad = api.squad("Dados-A")

    result = api.allocate(initiative["id"], 18, 19, squad_id=squad["id"])

    assert result["initiative_status"] == "PLANNED"
    assert api.get(f"/initiatives/{initiative['id']}").json()["status"] == "PLANNED"


def test_repeating_the_same_allocation_creates_nothing(api: Api) -> None:
    """RN4: a operação é idempotente por célula."""
    api.sprints()
    initiative = api.project("CRM")["initiatives"][0]
    squad = api.squad("Dados-A")
    api.allocate(initiative["id"], 18, 19, squad_id=squad["id"])

    again = api.allocate(initiative["id"], 18, 19, squad_id=squad["id"])

    assert again["created"] == []
    assert [cell["sprint_number"] for cell in again["already_existed"]] == [18, 19]


def test_a_second_assignee_in_the_same_cell_is_409(api: Api) -> None:
    """D17: a unicidade é `(initiative_id, sprint_id)` — um responsável por
    célula."""
    api.sprints()
    initiative = api.project("CRM")["initiatives"][0]
    dados_a = api.squad("Dados-A")
    dados_b = api.squad("Dados-B")
    api.allocate(initiative["id"], 18, 19, squad_id=dados_a["id"])

    response = api.post(
        "/allocations",
        json={
            "initiative_id": initiative["id"],
            "from_sprint_number": 19,
            "to_sprint_number": 19,
            "squad_id": dados_b["id"],
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ALLOCATION_CONFLICT"


def test_a_done_initiative_refuses_a_new_allocation(api: Api) -> None:
    """RN7: só DONE e CANCELLED recusam. O histórico existente permanece."""
    api.sprints()
    initiative = api.project("CRM")["initiatives"][0]
    squad = api.squad("Dados-A")
    api.post(f"/initiatives/{initiative['id']}/status", json={"status": "CANCELLED"})

    response = api.post(
        "/allocations",
        json={
            "initiative_id": initiative["id"],
            "from_sprint_number": 18,
            "to_sprint_number": 18,
            "squad_id": squad["id"],
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INITIATIVE_NOT_ALLOCATABLE"


def test_the_response_carries_the_current_alerts_of_the_touched_sprints(
    api: Api,
) -> None:
    """Cenário A do §13.1, pela API: a mesma squad em duas frentes na 19.

    `alerts` é o estado atual das sprints tocadas — é o que a UI usa para
    mostrar o aviso sem uma segunda chamada.
    """
    api.sprints()
    crm = api.project("CRM")["initiatives"][0]
    bnpl = api.project("BNPL")["initiatives"][0]
    squad = api.squad("Dados-A")
    bianca = api.member("Bianca")
    api.join(squad["id"], [bianca["id"]], 18, 22)
    api.allocate(crm["id"], 19, 19, squad_id=squad["id"])

    result = api.allocate(bnpl["id"], 19, 19, squad_id=squad["id"])

    overloaded = [
        alert for alert in result["alerts"] if alert["type"] == "SQUAD_OVERLOADED"
    ]
    assert [alert["sprint_number"] for alert in overloaded] == [19]
    assert {ref["name"] for ref in overloaded[0]["entity_refs"]} >= {"CRM", "BNPL"}


def test_a_capacity_reserve_project_does_not_overload_anyone(api: Api) -> None:
    """Cenário B do §13.1: a segunda frente é de projeto de reserva."""
    api.sprints()
    crm = api.project("CRM")["initiatives"][0]
    ferias = api.project("Férias", is_capacity_reserve=True)["initiatives"][0]
    squad = api.squad("Dados-A")
    bianca = api.member("Bianca")
    api.join(squad["id"], [bianca["id"]], 18, 22)
    api.allocate(crm["id"], 19, 19, squad_id=squad["id"])

    result = api.allocate(ferias["id"], 19, 19, squad_id=squad["id"])

    assert not [
        alert for alert in result["alerts"] if alert["type"] == "SQUAD_OVERLOADED"
    ]


def test_a_member_can_be_the_assignee_directly(api: Api) -> None:
    api.sprints()
    initiative = api.project("CRM")["initiatives"][0]
    bianca = api.member("Bianca")

    api.allocate(initiative["id"], 18, 18, member_id=bianca["id"])

    found = api.get("/allocations").json()
    assert found[0]["member_id"] == bianca["id"]
    assert found[0]["squad_id"] is None


def test_the_list_filters_by_everything_the_spec_names(api: Api) -> None:
    api.sprints()
    crm = api.project("CRM")
    bnpl = api.project("BNPL")
    dados_a = api.squad("Dados-A")
    bianca = api.member("Bianca")
    api.allocate(crm["initiatives"][0]["id"], 18, 19, squad_id=dados_a["id"])
    api.allocate(bnpl["initiatives"][0]["id"], 20, 20, member_id=bianca["id"])

    assert len(api.get("/allocations").json()) == 3
    assert len(api.get("/allocations", params={"sprint_from": 20}).json()) == 1
    assert len(api.get("/allocations", params={"squad_id": dados_a["id"]}).json()) == 2
    assert len(api.get("/allocations", params={"member_id": bianca["id"]}).json()) == 1
    assert (
        len(api.get("/allocations", params={"project_id": crm["project"]["id"]}).json())
        == 2
    )
    assert (
        len(
            api.get(
                "/allocations",
                params={"initiative_id": bnpl["initiatives"][0]["id"]},
            ).json()
        )
        == 1
    )


def test_deleting_an_interval_removes_only_that_interval(api: Api) -> None:
    api.sprints()
    initiative = api.project("CRM")["initiatives"][0]
    squad = api.squad("Dados-A")
    api.allocate(initiative["id"], 18, 22, squad_id=squad["id"])

    response = api.delete(
        "/allocations",
        json={
            "initiative_id": initiative["id"],
            "from_sprint_number": 19,
            "to_sprint_number": 20,
        },
    )

    assert response.status_code == 200
    assert [cell["sprint_number"] for cell in response.json()["removed"]] == [19, 20]
    remaining = api.get("/allocations").json()
    assert [item["sprint_number"] for item in remaining] == [18, 21, 22]


def test_deleting_an_empty_interval_is_not_an_error(api: Api) -> None:
    """Intervalo sem alocação nenhuma é operação vazia, não 404."""
    api.sprints()
    initiative = api.project("CRM")["initiatives"][0]

    response = api.delete(
        "/allocations",
        json={
            "initiative_id": initiative["id"],
            "from_sprint_number": 18,
            "to_sprint_number": 22,
        },
    )

    assert response.status_code == 200
    assert response.json()["removed"] == []


def test_deleting_a_single_cell_works_by_id(api: Api) -> None:
    api.sprints()
    initiative = api.project("CRM")["initiatives"][0]
    squad = api.squad("Dados-A")
    created = api.allocate(initiative["id"], 18, 19, squad_id=squad["id"])
    cell = created["created"][0]

    response = api.delete(f"/allocations/{cell['id']}")

    assert response.status_code == 200
    assert response.json()["removed"] == [cell]
    assert len(api.get("/allocations").json()) == 1


def test_losing_every_allocation_does_not_send_a_started_initiative_back(
    api: Api,
) -> None:
    """§6.3: quem começou não volta ao backlog. Parar é DEPRIORITIZED, à mão."""
    api.sprints()
    initiative = api.project("CRM")["initiatives"][0]
    squad = api.squad("Dados-A")
    api.allocate(initiative["id"], 18, 18, squad_id=squad["id"])
    api.post(f"/initiatives/{initiative['id']}/status", json={"status": "IN_PROGRESS"})

    response = api.delete(
        "/allocations",
        json={
            "initiative_id": initiative["id"],
            "from_sprint_number": 18,
            "to_sprint_number": 18,
        },
    )

    assert response.json()["initiative_status"] == "IN_PROGRESS"


def test_an_unknown_allocation_is_404(api: Api) -> None:
    response = api.delete(f"/allocations/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ALLOCATION_NOT_FOUND"
