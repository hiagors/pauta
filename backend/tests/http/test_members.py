"""`/members` pela borda HTTP (§6.4, §8)."""

from uuid import uuid4

from tests.http.conftest import Api


def test_a_new_member_is_active(api: Api) -> None:
    created = api.member("Bianca Souza", role="Analista de dados")

    assert created["name"] == "Bianca Souza"
    assert created["short_name"] == "Bianca"
    assert created["role"] == "Analista de dados"
    assert created["is_active"] is True


def test_a_member_without_a_name_is_422(api: Api) -> None:
    response = api.post("/members", json={"name": "  ", "short_name": "x"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_NAME"


def test_the_active_filter_hides_the_inactive_ones(api: Api) -> None:
    bianca = api.member("Bianca")
    emilie = api.member("Emilie")
    api.delete(f"/members/{emilie['id']}")

    active = api.get("/members", params={"active": True}).json()
    everyone = api.get("/members").json()

    assert [item["id"] for item in active] == [bianca["id"]]
    assert len(everyone) == 2


def test_delete_is_a_soft_delete_and_returns_the_member(api: Api) -> None:
    """§6.4: membro nunca é apagado. Apagar reescreveria alocações passadas.

    A resposta é o membro inativado, e não 204, para a UI atualizar a linha
    sem recarregar a lista.
    """
    member = api.member("Emilie")

    response = api.delete(f"/members/{member['id']}")

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_an_inactive_member_can_be_reactivated_by_patch(api: Api) -> None:
    member = api.member("Emilie")
    api.delete(f"/members/{member['id']}")

    updated = api.patch(f"/members/{member['id']}", json={"is_active": True}).json()

    assert updated["is_active"] is True


def test_a_patch_only_touches_what_it_carries(api: Api) -> None:
    member = api.member("Bianca Souza", role="Analista")

    updated = api.patch(f"/members/{member['id']}", json={"short_name": "Bia"}).json()

    assert updated["short_name"] == "Bia"
    assert updated["name"] == "Bianca Souza"
    assert updated["role"] == "Analista"


def test_an_unknown_member_is_404_on_every_verb(api: Api) -> None:
    unknown = uuid4()

    assert api.patch(f"/members/{unknown}", json={"role": "x"}).status_code == 404
    assert api.delete(f"/members/{unknown}").status_code == 404
