"""`/alerts` e o silenciamento pela borda HTTP (§7.3, §8).

Os cenários do §13.1 são cobertos de verdade nas suítes de domínio e de use
case. Aqui o alvo é a borda: a janela default, o que sai da lista e o que fica
no contador, e o ciclo silenciar → reativar.
"""

from uuid import uuid4

from tests.http.conftest import Api


def alerts_of(payload: dict[str, object], kind: str) -> list[dict[str, object]]:
    items: list[dict[str, object]] = payload["items"]  # type: ignore[assignment]
    return [alert for alert in items if alert["type"] == kind]


def test_an_active_member_with_no_front_is_reported_as_idle(api: Api) -> None:
    """Cenário E do §13.1. D16: o alerta é sobre a **pessoa**, não sobre a
    squad — uma squad sem alocação não é problema; uma pessoa sem frente é
    exatamente a pergunta de capacidade que interessa."""
    api.sprints()
    api.member("Diana")

    idle = alerts_of(api.get("/alerts").json(), "MEMBER_IDLE")

    # A janela default vai da 18 à 22, mas o horizonte do `MEMBER_IDLE` é a
    # sprint atual e as duas seguintes (§7.3): a 21 e a 22 ficam de fora.
    assert [alert["sprint_number"] for alert in idle] == [18, 19, 20]
    assert idle[0]["severity"] == "INFO"


def test_an_inactive_member_is_not_reported_as_idle(api: Api) -> None:
    """Premissa A3 do §16: os alertas ignoram inativos."""
    api.sprints()
    diana = api.member("Diana")
    api.delete(f"/members/{diana['id']}")

    assert alerts_of(api.get("/alerts").json(), "MEMBER_IDLE") == []


def test_a_squad_allocated_without_anyone_in_it_is_reported(api: Api) -> None:
    """Cenário F do §13.1: `Gama` alocada na 21 sem membership na 21."""
    api.sprints()
    initiative = api.project("API de Cobrança")["initiatives"][0]
    squad = api.squad("Gama")
    api.allocate(initiative["id"], 21, 21, squad_id=squad["id"])

    empty = alerts_of(api.get("/alerts").json(), "EMPTY_SQUAD")

    assert [alert["sprint_number"] for alert in empty] == [21]
    assert {ref["name"] for ref in empty[0]["entity_refs"]} >= {"Gama"}


def test_a_member_in_two_squads_on_two_fronts_is_a_conflict(api: Api) -> None:
    """Cenário C do §13.1."""
    api.sprints()
    aurora = api.project("Aurora")["initiatives"][0]
    boreal = api.project("Boreal")["initiatives"][0]
    alfa = api.squad("Alfa")
    beta = api.squad("Beta")
    ana = api.member("Ana")
    api.join(alfa["id"], [ana["id"]], 19, 19)
    api.join(beta["id"], [ana["id"]], 19, 19)
    api.allocate(aurora["id"], 19, 19, squad_id=alfa["id"])
    api.allocate(boreal["id"], 19, 19, squad_id=beta["id"])

    conflicts = alerts_of(api.get("/alerts").json(), "MEMBER_CONFLICT")

    assert [alert["sprint_number"] for alert in conflicts] == [19]
    assert conflicts[0]["severity"] == "WARNING"


def test_a_handover_between_squads_is_not_a_conflict(api: Api) -> None:
    """Cenário D do §13.1: Carla na `Beta` até a 19 e na `Alfa` da 20 em
    diante. Passagem de bastão não é conflito em sprint nenhuma."""
    api.sprints()
    aurora = api.project("Aurora")["initiatives"][0]
    boreal = api.project("Boreal")["initiatives"][0]
    alfa = api.squad("Alfa")
    beta = api.squad("Beta")
    carla = api.member("Carla")
    api.join(beta["id"], [carla["id"]], 18, 19)
    api.join(alfa["id"], [carla["id"]], 20, 22)
    api.allocate(boreal["id"], 18, 19, squad_id=beta["id"])
    api.allocate(aurora["id"], 20, 22, squad_id=alfa["id"])

    assert alerts_of(api.get("/alerts").json(), "MEMBER_CONFLICT") == []


def test_the_window_narrows_by_interval(api: Api) -> None:
    """O filtro estreita a janela; ele não desloca o horizonte do `MEMBER_IDLE`.

    A sprint atual é a 18, então o horizonte é 18–20 em qualquer recorte.
    Pedir 20–21 devolve a 20 e não a 21: a 21 está fora do horizonte, e
    ancorá-lo no começo do filtro faria o mesmo alerta aparecer ou sumir
    conforme o intervalo pedido.
    """
    api.sprints()
    api.member("Diana")

    narrowed = api.get("/alerts", params={"sprint_from": 20, "sprint_to": 21}).json()

    assert [alert["sprint_number"] for alert in narrowed["items"]] == [20]


def test_muting_takes_the_alert_out_of_the_list_but_keeps_it_counted(
    api: Api,
) -> None:
    """§7.3: o painel mostra os não silenciados e guarda os outros atrás de um
    contador expansível."""
    api.sprints()
    api.member("Diana")
    target = api.get("/alerts").json()["items"][0]

    mute = api.created(
        "/alerts/mute",
        {
            "fingerprint": target["fingerprint"],
            "alert_type": target["type"],
            "reason": "Diana está em treinamento nesta sprint",
        },
    )
    after = api.get("/alerts").json()

    assert mute["reason"] == "Diana está em treinamento nesta sprint"
    assert after["muted_count"] == 1
    assert target["fingerprint"] not in {
        alert["fingerprint"] for alert in after["items"]
    }


def test_include_muted_brings_it_back_marked(api: Api) -> None:
    """Com `is_muted: true` e o `mute_id`, que é o que o botão "Reativar" usa."""
    api.sprints()
    api.member("Diana")
    target = api.get("/alerts").json()["items"][0]
    mute = api.created(
        "/alerts/mute",
        {
            "fingerprint": target["fingerprint"],
            "alert_type": target["type"],
            "reason": "combinado com o time",
        },
    )

    with_muted = api.get("/alerts", params={"include_muted": True}).json()

    silenced = next(
        alert
        for alert in with_muted["items"]
        if alert["fingerprint"] == target["fingerprint"]
    )
    assert silenced["is_muted"] is True
    assert silenced["mute_id"] == mute["id"]
    assert silenced["mute_reason"] == "combinado com o time"


def test_muting_the_same_fingerprint_twice_is_409(api: Api) -> None:
    api.sprints()
    api.member("Diana")
    target = api.get("/alerts").json()["items"][0]
    body = {
        "fingerprint": target["fingerprint"],
        "alert_type": target["type"],
        "reason": "combinado com o time",
    }
    api.created("/alerts/mute", body)

    response = api.post("/alerts/mute", json=body)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ALERT_ALREADY_MUTED"


def test_muting_without_a_reason_is_422(api: Api) -> None:
    """§7.3: silenciar exige motivo em texto."""
    api.sprints()
    api.member("Diana")
    target = api.get("/alerts").json()["items"][0]

    response = api.post(
        "/alerts/mute",
        json={
            "fingerprint": target["fingerprint"],
            "alert_type": target["type"],
            "reason": "   ",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "MUTE_REASON_REQUIRED"


def test_reactivating_puts_the_alert_back(api: Api) -> None:
    api.sprints()
    api.member("Diana")
    target = api.get("/alerts").json()["items"][0]
    mute = api.created(
        "/alerts/mute",
        {
            "fingerprint": target["fingerprint"],
            "alert_type": target["type"],
            "reason": "combinado com o time",
        },
    )

    assert api.delete(f"/alerts/mute/{mute['id']}").status_code == 204
    after = api.get("/alerts").json()
    assert after["muted_count"] == 0
    assert target["fingerprint"] in {alert["fingerprint"] for alert in after["items"]}


def test_a_third_front_does_not_undo_the_mute(api: Api) -> None:
    """Cenário G do §13.1: o `fingerprint` é ancorado no sujeito mais a sprint,
    nunca nas iniciativas — senão alocar uma terceira frente ressuscitaria o
    alerta que já foi respondido."""
    api.sprints()
    aurora = api.project("Aurora")["initiatives"][0]
    boreal = api.project("Boreal")["initiatives"][0]
    billing = api.project("API de Cobrança")["initiatives"][0]
    alfa = api.squad("Alfa")
    ana = api.member("Ana")
    api.join(alfa["id"], [ana["id"]], 19, 19)
    api.allocate(aurora["id"], 19, 19, squad_id=alfa["id"])
    api.allocate(boreal["id"], 19, 19, squad_id=alfa["id"])
    overloaded = alerts_of(api.get("/alerts").json(), "SQUAD_OVERLOADED")[0]
    api.created(
        "/alerts/mute",
        {
            "fingerprint": overloaded["fingerprint"],
            "alert_type": overloaded["type"],
            "reason": "as duas frentes são da mesma pessoa",
        },
    )

    result = api.allocate(billing["id"], 19, 19, squad_id=alfa["id"])

    still_muted = [
        alert for alert in result["alerts"] if alert["type"] == "SQUAD_OVERLOADED"
    ]
    assert [alert["is_muted"] for alert in still_muted] == [True]
    assert alerts_of(api.get("/alerts").json(), "SQUAD_OVERLOADED") == []


def test_reactivating_an_unknown_mute_is_404(api: Api) -> None:
    response = api.delete(f"/alerts/mute/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "MUTED_ALERT_NOT_FOUND"


def test_there_is_nothing_to_report_without_any_sprint(api: Api) -> None:
    api.member("Diana")

    assert api.get("/alerts").json() == {"items": [], "muted_count": 0}
