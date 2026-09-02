"""`/planning/grid` e `/planning/backlog` pela borda HTTP (§8)."""

from tests.http.conftest import Api


def test_the_grid_groups_the_rows_by_project(api: Api) -> None:
    """§8: é o agrupamento por projeto que faz a leitura vertical funcionar, e
    é o projeto que carrega a cor."""
    api.sprints()
    crm = api.project("CRM", color="#0052CC")
    squad = api.squad("Dados-A")
    api.allocate(crm["initiatives"][0]["id"], 18, 19, squad_id=squad["id"])

    grid = api.get("/planning/grid", params={"sprint_from": 18, "sprint_to": 22}).json()

    assert [group["project"]["name"] for group in grid["groups"]] == ["CRM"]
    assert grid["groups"][0]["project"]["color"] == "#0052CC"


def test_a_project_without_color_gets_the_default_one_resolved(api: Api) -> None:
    """A grade recebe a cor já resolvida; quem edita é que vê o campo nulo."""
    api.sprints()
    crm = api.project("CRM")
    squad = api.squad("Dados-A")
    api.allocate(crm["initiatives"][0]["id"], 18, 18, squad_id=squad["id"])

    grid = api.get("/planning/grid").json()

    assert grid["groups"][0]["project"]["color"] == "#7A869A"


def test_contiguous_sprints_of_one_assignee_become_a_single_bar(api: Api) -> None:
    """O front desenha barras, não células — é o que dá a cara de Gantt."""
    api.sprints()
    crm = api.project("CRM")
    squad = api.squad("Dados-A")
    api.allocate(crm["initiatives"][0]["id"], 18, 20, squad_id=squad["id"])

    grid = api.get("/planning/grid", params={"sprint_from": 18, "sprint_to": 22}).json()

    bars = grid["groups"][0]["rows"][0]["bars"]
    assert len(bars) == 1
    assert (bars[0]["from_sprint_number"], bars[0]["to_sprint_number"]) == (18, 20)
    assert bars[0]["assignee"] == {
        "kind": "squad",
        "id": squad["id"],
        "name": "Dados-A",
    }
    assert len(bars[0]["allocation_ids"]) == 3


def test_a_pause_in_the_middle_generates_two_bars(api: Api) -> None:
    api.sprints()
    crm = api.project("CRM")
    squad = api.squad("Dados-A")
    initiative = crm["initiatives"][0]["id"]
    api.allocate(initiative, 18, 18, squad_id=squad["id"])
    api.allocate(initiative, 21, 22, squad_id=squad["id"])

    grid = api.get("/planning/grid", params={"sprint_from": 18, "sprint_to": 22}).json()

    bars = grid["groups"][0]["rows"][0]["bars"]
    assert [(bar["from_sprint_number"], bar["to_sprint_number"]) for bar in bars] == [
        (18, 18),
        (21, 22),
    ]


def test_the_default_window_is_the_current_civil_quarter(api: Api) -> None:
    """RN13, com a premissa A1 do §16 em vigor: trimestre civil.

    Hoje é 02/09/2026, então a janela é jul-set: entram a 18, a 19 e a 20, que
    começa em 28/09; a 21 já é de outubro.
    """
    api.sprints()

    grid = api.get("/planning/grid").json()

    assert [sprint["number"] for sprint in grid["sprints"]] == [18, 19, 20]
    assert [sprint["number"] for sprint in grid["sprints"] if sprint["is_current"]] == [
        18
    ]


def test_the_alerts_of_the_header_ignore_the_filters(api: Api) -> None:
    """§8: filtrar por uma squad não pode esconder o conflito da outra — o
    ícone da coluna reporta a sprint inteira."""
    api.sprints()
    crm = api.project("CRM")["initiatives"][0]
    bnpl = api.project("BNPL")["initiatives"][0]
    dados_a = api.squad("Dados-A")
    dados_b = api.squad("Dados-B")
    bianca = api.member("Bianca")
    api.join(dados_a["id"], [bianca["id"]], 18, 22)
    api.join(dados_b["id"], [bianca["id"]], 18, 22)
    api.allocate(crm["id"], 19, 19, squad_id=dados_a["id"])
    api.allocate(bnpl["id"], 19, 19, squad_id=dados_b["id"])

    grid = api.get(
        "/planning/grid",
        params={"sprint_from": 18, "sprint_to": 22, "squad_id": dados_a["id"]},
    ).json()

    assert "MEMBER_CONFLICT" in grid["alerts_by_sprint"]["19"]
    rows = [row for group in grid["groups"] for row in group["rows"]]
    assert len(rows) == 1


def test_the_grid_filters_narrow_the_rows(api: Api) -> None:
    api.sprints()
    crm = api.project("CRM")
    bnpl = api.project("BNPL")
    squad = api.squad("Dados-A")
    api.allocate(crm["initiatives"][0]["id"], 18, 18, squad_id=squad["id"])
    api.allocate(bnpl["initiatives"][0]["id"], 18, 18, squad_id=squad["id"])

    grid = api.get(
        "/planning/grid",
        params={"sprint_from": 18, "sprint_to": 18, "project_id": crm["project"]["id"]},
    ).json()

    assert [group["project"]["name"] for group in grid["groups"]] == ["CRM"]


def test_the_backlog_summarizes_what_is_estimated(api: Api) -> None:
    """§8: `estimated_sprints_total` soma só quem tem estimativa."""
    project = api.project("CRM")["project"]
    api.initiative(project["id"], "Reestruturação V1", estimated_sprints=3)
    api.initiative(project["id"], "Descoberta", estimated_sprints=4)

    backlog = api.get("/planning/backlog").json()

    assert backlog["summary"] == {
        "count": 3,
        "estimated_sprints_total": 7,
        "items_without_estimate": 1,
    }


def test_the_backlog_excludes_capacity_reserve_projects(api: Api) -> None:
    api.project("CRM")
    api.project("Férias", is_capacity_reserve=True)

    backlog = api.get("/planning/backlog").json()

    assert [item["project"]["name"] for item in backlog["items"]] == ["CRM"]


def test_the_backlog_is_by_status_and_loses_what_gets_planned(api: Api) -> None:
    """RN2 + §8: alocar leva a `PLANNED`, e `PLANNED` não é backlog."""
    api.sprints()
    initiative = api.project("CRM")["initiatives"][0]
    squad = api.squad("Dados-A")

    api.allocate(initiative["id"], 18, 18, squad_id=squad["id"])

    assert api.get("/planning/backlog").json()["items"] == []


def test_a_deprioritized_initiative_does_not_show_up_in_the_backlog(api: Api) -> None:
    """§8: `DEPRIORITIZED` é filtro da tela de projetos, e não se mistura."""
    api.sprints()
    initiative = api.project("CRM")["initiatives"][0]
    squad = api.squad("Dados-A")
    api.allocate(initiative["id"], 18, 18, squad_id=squad["id"])
    api.post(f"/initiatives/{initiative['id']}/status", json={"status": "IN_PROGRESS"})
    api.post(
        f"/initiatives/{initiative['id']}/status", json={"status": "DEPRIORITIZED"}
    )

    assert api.get("/planning/backlog").json()["items"] == []


def test_the_backlog_orders_by_priority_by_default(api: Api) -> None:
    project = api.project("CRM")["project"]
    api.initiative(project["id"], "Alta", priority="HIGH")
    api.initiative(project["id"], "Baixa", priority="LOW")

    items = api.get("/planning/backlog").json()["items"]

    assert [item["initiative"]["name"] for item in items][:2] == ["Alta", "CRM"]
    assert items[-1]["initiative"]["name"] == "Baixa"


def test_ordering_by_size_keeps_the_missing_estimates_last(api: Api) -> None:
    """§8: nulos por último **em qualquer direção**."""
    project = api.project("CRM")["project"]
    api.initiative(project["id"], "Pequena", estimated_sprints=1)
    api.initiative(project["id"], "Grande", estimated_sprints=8)

    ascending = api.get("/planning/backlog", params={"order_by": "size"}).json()
    descending = api.get(
        "/planning/backlog", params={"order_by": "size", "descending": True}
    ).json()

    assert [item["initiative"]["name"] for item in ascending["items"]] == [
        "Pequena",
        "Grande",
        "CRM",
    ]
    assert [item["initiative"]["name"] for item in descending["items"]] == [
        "Grande",
        "Pequena",
        "CRM",
    ]


def test_an_unknown_order_is_422(api: Api) -> None:
    response = api.get("/planning/backlog", params={"order_by": "tamanho"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
