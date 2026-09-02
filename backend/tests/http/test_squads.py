"""`/squads` e a composição por sprint (§6.5, §8)."""

from uuid import uuid4

from tests.http.conftest import Api


def test_a_squad_without_a_sprint_has_no_member_list(api: Api) -> None:
    """D11: composição é por sprint. Uma lista sem sprint seria mentira."""
    api.sprints()
    squad = api.squad("Dados-A")
    bianca = api.member("Bianca")
    api.join(squad["id"], [bianca["id"]], 18, 22)

    found = api.get("/squads").json()

    assert found[0]["sprint_number"] is None
    assert found[0]["members"] == []


def test_asking_for_a_sprint_expands_the_composition(api: Api) -> None:
    api.sprints()
    squad = api.squad("Dados-A")
    bianca = api.member("Bianca")
    api.join(squad["id"], [bianca["id"]], 18, 19)

    on_19 = api.get("/squads", params={"sprint_number": 19}).json()[0]
    on_22 = api.get("/squads", params={"sprint_number": 22}).json()[0]

    assert on_19["sprint_number"] == 19
    assert [item["short_name"] for item in on_19["members"]] == ["Bianca"]
    assert on_22["members"] == []


def test_the_representative_has_to_be_an_active_member(api: Api) -> None:
    emilie = api.member("Emilie")
    api.delete(f"/members/{emilie['id']}")

    response = api.post(
        "/squads", json={"name": "Dados-A", "representative_member_id": emilie["id"]}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REPRESENTATIVE"


def test_the_representative_can_be_cleared_with_null(api: Api) -> None:
    bianca = api.member("Bianca")
    squad = api.squad("Dados-A", representative_member_id=bianca["id"])

    updated = api.patch(
        f"/squads/{squad['id']}", json={"representative_member_id": None}
    ).json()

    assert updated["representative_member_id"] is None


def test_delete_is_a_soft_delete_and_returns_the_squad(api: Api) -> None:
    """Squad é agrupamento com prazo. O prazo terminar não apaga o que ela
    fez, então as alocações passadas continuam de pé."""
    squad = api.squad("Dados-A")

    response = api.delete(f"/squads/{squad['id']}")

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_get_returns_only_the_sprints_where_the_squad_has_people(api: Api) -> None:
    """A leitura de uma squad não é a matriz de edição: as sprints vazias
    seriam ruído aqui. Quem quer o intervalo inteiro pede
    `GET /squads/{id}/memberships`."""
    api.sprints()
    squad = api.squad("Dados-A")
    bianca = api.member("Bianca")
    api.join(squad["id"], [bianca["id"]], 18, 19)

    found = api.get(f"/squads/{squad['id']}").json()

    assert found["squad"]["name"] == "Dados-A"
    assert [item["sprint_number"] for item in found["memberships"]] == [18, 19]
    assert [item["members"][0]["short_name"] for item in found["memberships"]] == [
        "Bianca",
        "Bianca",
    ]


def test_the_memberships_endpoint_shows_the_empty_sprints_too(api: Api) -> None:
    """A matriz precisa da célula em branco para poder ser editada."""
    api.sprints()
    squad = api.squad("Dados-A")
    bianca = api.member("Bianca")
    api.join(squad["id"], [bianca["id"]], 18, 19)

    found = api.get(f"/squads/{squad['id']}/memberships").json()

    assert [item["sprint_number"] for item in found] == [18, 19, 20, 21, 22]
    assert [len(item["members"]) for item in found] == [1, 1, 0, 0, 0]


def test_the_memberships_endpoint_narrows_by_interval(api: Api) -> None:
    api.sprints()
    squad = api.squad("Dados-A")
    bianca = api.member("Bianca")
    api.join(squad["id"], [bianca["id"]], 18, 22)

    found = api.get(
        f"/squads/{squad['id']}/memberships",
        params={"sprint_from": 19, "sprint_to": 20},
    ).json()

    assert [item["sprint_number"] for item in found] == [19, 20]


def test_put_replaces_the_composition_in_the_interval(api: Api) -> None:
    """`PUT` é substituição, não acréscimo: quem ficou de fora sai."""
    api.sprints()
    squad = api.squad("Dados-A")
    bianca = api.member("Bianca")
    emilie = api.member("Emilie")
    api.join(squad["id"], [bianca["id"], emilie["id"]], 18, 22)

    resulting = api.join(squad["id"], [emilie["id"]], 19, 19)

    on_19 = next(item for item in resulting if item["sprint_number"] == 19)
    assert [item["short_name"] for item in on_19["members"]] == ["Emilie"]
    on_18 = api.get("/squads", params={"sprint_number": 18}).json()[0]
    assert len(on_18["members"]) == 2


def test_an_empty_member_list_empties_the_interval(api: Api) -> None:
    api.sprints()
    squad = api.squad("Dados-A")
    bianca = api.member("Bianca")
    api.join(squad["id"], [bianca["id"]], 18, 22)

    resulting = api.join(squad["id"], [], 18, 22)

    assert all(item["members"] == [] for item in resulting)


def test_delete_removes_only_the_named_members(api: Api) -> None:
    api.sprints()
    squad = api.squad("Dados-A")
    bianca = api.member("Bianca")
    emilie = api.member("Emilie")
    api.join(squad["id"], [bianca["id"], emilie["id"]], 18, 22)

    response = api.delete(
        f"/squads/{squad['id']}/memberships",
        json={"sprint_from": 18, "sprint_to": 19, "member_ids": [bianca["id"]]},
    )

    assert response.status_code == 200
    remaining = {
        item["sprint_number"]: [member["short_name"] for member in item["members"]]
        for item in response.json()
    }
    assert remaining[18] == ["Emilie"]
    assert remaining[19] == ["Emilie"]


def test_delete_without_member_ids_removes_everyone(api: Api) -> None:
    api.sprints()
    squad = api.squad("Dados-A")
    bianca = api.member("Bianca")
    emilie = api.member("Emilie")
    api.join(squad["id"], [bianca["id"], emilie["id"]], 18, 22)

    response = api.delete(
        f"/squads/{squad['id']}/memberships",
        json={"sprint_from": 18, "sprint_to": 22},
    )

    assert all(item["members"] == [] for item in response.json())


def test_an_inverted_interval_is_422(api: Api) -> None:
    api.sprints()
    squad = api.squad("Dados-A")

    response = api.put(
        f"/squads/{squad['id']}/memberships",
        json={"sprint_from": 22, "sprint_to": 18, "member_ids": []},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_SPRINT_RANGE"


def test_an_unknown_squad_is_404_on_the_memberships(api: Api) -> None:
    response = api.get(f"/squads/{uuid4()}/memberships")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SQUAD_NOT_FOUND"
