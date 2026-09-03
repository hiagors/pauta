"""`/initiatives` pela borda HTTP (§8)."""

from uuid import uuid4

from tests.http.conftest import Api


def test_creating_an_initiative_stamps_the_entry_date(api: Api) -> None:
    """§6.2: `entered_at` vem do `Clock`, que a suíte congelou em 02/09/2026."""
    project = api.project("Aurora")["project"]

    created = api.initiative(project["id"], "Catálogo V1", priority="HIGH")

    assert created["entered_at"] == "2026-09-02"
    assert created["priority"] == "HIGH"
    assert created["status"] == "BACKLOG"


def test_an_initiative_of_an_unknown_project_is_404(api: Api) -> None:
    response = api.post(
        "/initiatives", json={"project_id": str(uuid4()), "name": "Órfã"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"


def test_an_estimate_of_zero_is_422(api: Api) -> None:
    project = api.project("Aurora")["project"]

    response = api.post(
        "/initiatives",
        json={
            "project_id": project["id"],
            "name": "Catálogo V1",
            "estimated_sprints": 0,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_ESTIMATE"


def test_the_same_name_in_two_projects_is_allowed(api: Api) -> None:
    """O nome é único **dentro** do projeto: "Descoberta" em dois produtos é
    normal."""
    aurora = api.project("Aurora")["project"]
    boreal = api.project("Boreal")["project"]

    api.initiative(aurora["id"], "Descoberta")
    api.initiative(boreal["id"], "Descoberta")

    found = api.get("/initiatives", params={"q": "descoberta"}).json()
    assert len(found) == 2


def test_the_same_name_twice_in_one_project_is_409(api: Api) -> None:
    aurora = api.project("Aurora")["project"]
    api.initiative(aurora["id"], "Descoberta")

    response = api.post(
        "/initiatives", json={"project_id": aurora["id"], "name": "Descoberta"}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_NAME"


def test_the_filters_of_the_spec_narrow_the_list(api: Api) -> None:
    aurora = api.project("Aurora")["project"]
    boreal = api.project("Boreal")["project"]
    api.initiative(aurora["id"], "Catálogo V1", priority="HIGH", layer="dados")
    api.initiative(aurora["id"], "Descoberta", priority="LOW")
    api.initiative(boreal["id"], "Portal Externo", priority="HIGH")

    by_project = api.get("/initiatives", params={"project_id": aurora["id"]}).json()
    by_priority = api.get("/initiatives", params={"priority": "HIGH"}).json()
    by_layer = api.get("/initiatives", params={"layer": "dados"}).json()
    by_status = api.get("/initiatives", params={"status": "PLANNED"}).json()

    assert {item["name"] for item in by_project} == {
        "Aurora",
        "Catálogo V1",
        "Descoberta",
    }
    assert {item["name"] for item in by_priority} == {
        "Catálogo V1",
        "Portal Externo",
    }
    assert [item["name"] for item in by_layer] == ["Catálogo V1"]
    assert by_status == []


def test_an_unknown_status_in_the_query_is_422(api: Api) -> None:
    response = api.get("/initiatives", params={"status": "ABANDONADA"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_a_patch_clears_the_layer_with_null_and_keeps_it_when_absent(
    api: Api,
) -> None:
    project = api.project("Aurora")["project"]
    initiative = api.initiative(project["id"], "Catálogo V1", layer="dados")

    kept = api.patch(
        f"/initiatives/{initiative['id']}", json={"priority": "HIGH"}
    ).json()
    cleared = api.patch(f"/initiatives/{initiative['id']}", json={"layer": None}).json()

    assert kept["layer"] == "dados"
    assert cleared["layer"] is None
    assert cleared["priority"] == "HIGH"


def test_the_patch_does_not_accept_status(api: Api) -> None:
    """Status muda por `POST /initiatives/{id}/status`, que valida a transição
    do §6.3. Aceitar aqui seria contornar a tabela."""
    initiative = api.project("Aurora")["initiatives"][0]

    response = api.patch(f"/initiatives/{initiative['id']}", json={"status": "DONE"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert api.get(f"/initiatives/{initiative['id']}").json()["status"] == "BACKLOG"


def test_a_manual_transition_of_the_table_is_accepted(api: Api) -> None:
    """§6.3: BACKLOG -> CANCELLED é o caminho de quem desiste antes de começar."""
    initiative = api.project("Aurora")["initiatives"][0]

    updated = api.post(
        f"/initiatives/{initiative['id']}/status", json={"status": "CANCELLED"}
    ).json()

    assert updated["status"] == "CANCELLED"


def test_deleting_the_last_initiative_of_a_project_is_409(api: Api) -> None:
    """RN-I2: projeto não pode ficar sem iniciativa. O caminho é CANCELLED."""
    initiative = api.project("Aurora")["initiatives"][0]

    response = api.delete(f"/initiatives/{initiative['id']}")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LAST_INITIATIVE_OF_PROJECT"


def test_deleting_an_initiative_with_an_allocation_is_409(api: Api) -> None:
    api.sprints()
    project = api.project("Aurora")["project"]
    initiative = api.initiative(project["id"], "Catálogo V1")
    squad = api.squad("Alfa")
    api.allocate(initiative["id"], 18, 19, squad_id=squad["id"])

    response = api.delete(f"/initiatives/{initiative['id']}")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "HAS_ALLOCATIONS"


def test_deleting_a_spare_initiative_without_allocation_works(api: Api) -> None:
    project = api.project("Aurora")["project"]
    initiative = api.initiative(project["id"], "Catálogo V1")

    assert api.delete(f"/initiatives/{initiative['id']}").status_code == 204
    assert api.get(f"/initiatives/{initiative['id']}").status_code == 404
