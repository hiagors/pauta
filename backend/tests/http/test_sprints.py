"""`/sprints` pela borda HTTP (§6.6, §8).

Sem `DELETE`: sprint é marcação de tempo e nunca é excluída (D13). Quem garante
que o endpoint não existe é `test_app.py`.
"""

from tests.http.conftest import Api


def test_the_first_sprint_can_start_at_any_number(api: Api) -> None:
    """A numeração do time real começa na 18, não na 1."""
    created = api.created(
        "/sprints",
        {"number": 18, "start_date": "2026-08-31", "end_date": "2026-09-11"},
    )

    assert created["number"] == 18
    assert created["is_current"] is True


def test_the_number_is_optional_and_continues_the_sequence(api: Api) -> None:
    api.sprints(18, 18)

    created = api.created(
        "/sprints", {"start_date": "2026-09-14", "end_date": "2026-09-25"}
    )

    assert created["number"] == 19


def test_an_end_date_before_the_start_is_422(api: Api) -> None:
    response = api.post(
        "/sprints", json={"start_date": "2026-09-11", "end_date": "2026-08-31"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_SPRINT_DATES"


def test_a_gap_in_the_numbering_is_409(api: Api) -> None:
    api.sprints(18, 18)

    response = api.post(
        "/sprints",
        json={"number": 25, "start_date": "2026-09-14", "end_date": "2026-09-25"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SPRINT_NUMBER_GAP"


def test_overlapping_dates_are_409(api: Api) -> None:
    api.sprints(18, 18)

    response = api.post(
        "/sprints",
        json={"number": 19, "start_date": "2026-09-07", "end_date": "2026-09-18"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SPRINT_OVERLAP"


def test_only_one_sprint_is_current(api: Api) -> None:
    """RN12: a atual é a de maior `start_date` já passado. Hoje é 02/09/2026,
    dentro da 18."""
    api.sprints()

    found = api.get("/sprints").json()

    assert [item["number"] for item in found if item["is_current"]] == [18]


def test_the_window_does_not_promote_another_sprint_to_current(api: Api) -> None:
    """Pedir da 20 à 22 não faz a 20 virar a atual."""
    api.sprints()

    found = api.get("/sprints", params={"from": 20, "to": 22}).json()

    assert [item["number"] for item in found] == [20, 21, 22]
    assert not any(item["is_current"] for item in found)


def test_the_preview_proposes_the_monday_after_the_last_sprint(api: Api) -> None:
    """RN10: próxima segunda depois do fim da anterior, `início + 11 dias`.
    A 22 vai de 26/10 a 06/11/2026, uma sexta; a proposta começa em 09/11."""
    api.sprints()

    proposal = api.get("/sprints/next/preview").json()

    assert proposal == {
        "number": 23,
        "start_date": "2026-11-09",
        "end_date": "2026-11-20",
    }


def test_the_preview_does_not_create_anything(api: Api) -> None:
    api.sprints()

    api.get("/sprints/next/preview")

    assert len(api.get("/sprints").json()) == 5


def test_creating_the_next_sprint_creates_exactly_the_proposal(api: Api) -> None:
    api.sprints()
    proposal = api.get("/sprints/next/preview").json()

    created = api.created("/sprints/next", {})

    assert {key: created[key] for key in proposal} == proposal


def test_there_is_nothing_to_propose_without_any_sprint(api: Api) -> None:
    """§6.6: a primeira sprint entra com as datas informadas."""
    response = api.get("/sprints/next/preview")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SPRINT_NOT_FOUND"
