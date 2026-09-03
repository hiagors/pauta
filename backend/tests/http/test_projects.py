"""`/projects` pela borda HTTP (§8)."""

from uuid import uuid4

from tests.http.conftest import Api


def test_creating_a_project_creates_the_first_initiative(api: Api) -> None:
    """RN-I1: projeto sem iniciativa não é planejável, então nasce com uma."""
    created = api.project("Aurora", description="Plataforma de vendas")

    assert created["project"]["name"] == "Aurora"
    assert created["project"]["description"] == "Plataforma de vendas"
    assert [item["name"] for item in created["initiatives"]] == ["Aurora"]
    assert created["initiatives"][0]["status"] == "BACKLOG"


def test_a_project_without_color_keeps_the_field_null(api: Api) -> None:
    """Quem edita precisa ver o campo vazio para saber que não escolheu cor;
    a cor padrão é resolvida na leitura (grade e backlog)."""
    created = api.project("Aurora")

    assert created["project"]["color"] is None


def test_the_color_is_normalized_to_upper_case(api: Api) -> None:
    created = api.project("Aurora", color="#0052cc")

    assert created["project"]["color"] == "#0052CC"


def test_an_invalid_color_is_422(api: Api) -> None:
    response = api.post("/projects", json={"name": "Aurora", "color": "azul"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_COLOR"


def test_the_list_comes_sorted_by_name(api: Api) -> None:
    for name in ("Portal", "Boreal", "Aurora"):
        api.project(name)

    found = api.get("/projects").json()

    assert [item["name"] for item in found] == ["Aurora", "Boreal", "Portal"]


def test_the_search_folds_case_including_accents(api: Api) -> None:
    """`?q=` usa `pauta_casefold`: os nomes deste sistema são em português."""
    api.project("Catálogo")
    api.project("Boreal")

    found = api.get("/projects", params={"q": "CATÁLOGO"}).json()

    assert [item["name"] for item in found] == ["Catálogo"]


def test_the_active_filter_separates_the_two_sides(api: Api) -> None:
    kept = api.project("Aurora")["project"]
    archived = api.project("Legado")["project"]
    api.patch(f"/projects/{archived['id']}", json={"is_active": False})

    active = api.get("/projects", params={"active": True}).json()
    inactive = api.get("/projects", params={"active": False}).json()

    assert [item["id"] for item in active] == [kept["id"]]
    assert [item["id"] for item in inactive] == [archived["id"]]


def test_get_includes_the_initiatives_of_the_project(api: Api) -> None:
    project = api.project("Aurora")["project"]
    api.initiative(project["id"], "Catálogo V1")

    found = api.get(f"/projects/{project['id']}").json()

    assert {item["name"] for item in found["initiatives"]} == {
        "Aurora",
        "Catálogo V1",
    }


def test_a_patch_only_touches_the_fields_it_carries(api: Api) -> None:
    project = api.project("Aurora", description="Vendas", color="#0052CC")["project"]

    updated = api.patch(f"/projects/{project['id']}", json={"name": "Aurora 2"}).json()

    assert updated["name"] == "Aurora 2"
    assert updated["description"] == "Vendas"
    assert updated["color"] == "#0052CC"


def test_a_null_color_clears_the_color(api: Api) -> None:
    """§8: `color: null` limpa; a **ausência** de `color` não mexe."""
    project = api.project("Aurora", color="#0052CC")["project"]

    updated = api.patch(f"/projects/{project['id']}", json={"color": None}).json()

    assert updated["color"] is None


def test_a_null_name_is_refused_by_the_schema(api: Api) -> None:
    """O nome não é anulável no domínio, então nem chega lá: 422 na borda."""
    project = api.project("Aurora")["project"]

    response = api.patch(f"/projects/{project['id']}", json={"name": None})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_an_empty_patch_is_a_no_op(api: Api) -> None:
    project = api.project("Aurora", description="Vendas")["project"]

    updated = api.patch(f"/projects/{project['id']}", json={}).json()

    assert updated == project


def test_deleting_a_project_takes_its_initiatives(api: Api) -> None:
    """Projeto sem iniciativa não existe (RN-I2), então as dele vão junto."""
    created = api.project("Aurora")
    project_id = created["project"]["id"]
    initiative_id = created["initiatives"][0]["id"]

    assert api.delete(f"/projects/{project_id}").status_code == 204
    assert api.get(f"/projects/{project_id}").status_code == 404
    assert api.get(f"/initiatives/{initiative_id}").status_code == 404


def test_deleting_a_project_with_an_allocation_is_409(api: Api) -> None:
    """§8: o caminho é marcar a iniciativa como CANCELLED, não apagar."""
    api.sprints()
    created = api.project("Aurora")
    squad = api.squad("Alfa")
    api.allocate(created["initiatives"][0]["id"], 18, 18, squad_id=squad["id"])

    response = api.delete(f"/projects/{created['project']['id']}")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "HAS_ALLOCATIONS"


def test_deleting_an_unknown_project_is_404(api: Api) -> None:
    assert api.delete(f"/projects/{uuid4()}").status_code == 404
