"""`/snapshots` e o export automático (§8, §9, RNF3, RNF4).

Duas coisas em teste aqui, e a segunda é a que ninguém pede explicitamente:

1. os dois endpoints do §8 — o export, que é o mesmo do `mise run snapshot`, e
   o import, que é destrutivo e por isso exige `?confirm=true`;
2. a regra da RNF3: **toda mutação bem-sucedida** agenda um export, e a
   importação `replace` **não**.

O timer do debounce é do teste (ver `conftest`): `api.snapshot_scheduled` diz
se a requisição agendou o export, e `api.flush_snapshot()` faz o que a thread
faria ao vencer os 5 segundos.
"""

from pathlib import Path

from app.adapters.outbound.snapshot.writer import DirectorySnapshotWriter
from tests.domain.conftest import FrozenClock
from tests.http.conftest import Api
from tests.snapshot.bundles import full_bundle


def _source_snapshot(path: Path, clock: FrozenClock) -> Path:
    """Uma pasta de snapshot pronta, fora da pasta que a API escreve.

    Fora de propósito: é o que permite verificar que a importação não reescreve
    a pasta sincronizada (RNF3).
    """
    DirectorySnapshotWriter(directory=path, clock=clock).write(full_bundle())
    return path


# --------------------------------------------------------------------------- #
# POST /snapshots/export
# --------------------------------------------------------------------------- #


def test_the_export_writes_the_files_of_the_spec_and_returns_the_paths(
    api: Api,
) -> None:
    api.sprints(18, 19)
    api.project("Aurora")

    response = api.post("/snapshots/export")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"paths", "counts"}
    names = {Path(path).name for path in body["paths"]}
    assert "projects.json" in names
    assert "meta.json" in names
    assert "plan-sprint-18.md" in names
    assert "plan-grid.md" in names
    assert body["counts"] == {
        "projects": 1,
        "initiatives": 1,
        "members": 0,
        "squads": 0,
        "squad_memberships": 0,
        "sprints": 2,
        "allocations": 0,
        "muted_alerts": 0,
    }
    assert (api.snapshot_dir / "projects.json").is_file()


def test_the_export_of_an_empty_database_works(api: Api) -> None:
    """Não existe `seed` (RNF5): a primeira exportação é de um banco vazio."""
    response = api.post("/snapshots/export")

    assert response.status_code == 200
    assert response.json()["counts"]["projects"] == 0


# --------------------------------------------------------------------------- #
# POST /snapshots/import
# --------------------------------------------------------------------------- #


def test_the_import_replaces_the_database(
    api: Api, clock: FrozenClock, tmp_path: Path
) -> None:
    source = _source_snapshot(tmp_path / "origem", clock)
    api.project("Projeto que vai embora")

    response = api.post(
        "/snapshots/import", params={"confirm": True}, json={"path": str(source)}
    )

    assert response.status_code == 200
    assert response.json()["counts"]["allocations"] == 3
    assert [project["name"] for project in api.get("/projects").json()] == [
        "Aurora",
        "Reserva de capacidade",
    ]


def test_the_import_without_confirmation_is_refused_and_erases_nothing(
    api: Api, clock: FrozenClock, tmp_path: Path
) -> None:
    """§8: `?confirm=true`. Sem ele, nada é lido nem apagado."""
    source = _source_snapshot(tmp_path / "origem", clock)
    api.project("Continua aqui")

    response = api.post("/snapshots/import", json={"path": str(source)})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SNAPSHOT_IMPORT_NOT_CONFIRMED"
    assert [project["name"] for project in api.get("/projects").json()] == [
        "Continua aqui"
    ]


def test_confirm_false_is_the_same_as_not_confirming(api: Api, tmp_path: Path) -> None:
    response = api.post(
        "/snapshots/import",
        params={"confirm": False},
        json={"path": str(tmp_path)},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SNAPSHOT_IMPORT_NOT_CONFIRMED"


def test_a_path_without_a_snapshot_is_404(api: Api, tmp_path: Path) -> None:
    response = api.post(
        "/snapshots/import",
        params={"confirm": True},
        json={"path": str(tmp_path / "nao-existe")},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SNAPSHOT_NOT_FOUND"


def test_a_mode_that_does_not_exist_is_422(api: Api, tmp_path: Path) -> None:
    """RNF4: só existe `replace`."""
    response = api.post(
        "/snapshots/import",
        params={"confirm": True},
        json={"path": str(tmp_path), "mode": "merge"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_a_failed_import_leaves_the_database_as_it_was(
    api: Api, clock: FrozenClock, tmp_path: Path
) -> None:
    """A transação é da requisição: um snapshot que não fecha não deixa meio
    banco (RNF4)."""
    source = _source_snapshot(tmp_path / "origem", clock)
    (source / "projects.json").write_text("[]\n", encoding="utf-8")
    api.project("Continua aqui")

    response = api.post(
        "/snapshots/import", params={"confirm": True}, json={"path": str(source)}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_SNAPSHOT"
    assert [project["name"] for project in api.get("/projects").json()] == [
        "Continua aqui"
    ]


# --------------------------------------------------------------------------- #
# RNF3: o export automático
# --------------------------------------------------------------------------- #


def test_a_successful_mutation_schedules_an_export(api: Api) -> None:
    api.project("Aurora")

    assert api.snapshot_scheduled


def test_the_scheduled_export_writes_the_snapshot_of_the_committed_data(
    api: Api,
) -> None:
    """O export sai depois do `commit`, e é por isso que ele vê a mutação que
    o disparou (ver o topo de `deps.py`)."""
    api.project("Aurora")

    api.flush_snapshot()

    assert "Aurora" in (api.snapshot_dir / "projects.json").read_text(encoding="utf-8")


def test_a_sequence_of_mutations_collapses_into_one_export(api: Api) -> None:
    """RNF3: quatro mutações, quatro agendamentos, **um** export.

    O que faz este teste ser sobre coalescing é o `cancelled`: cada
    agendamento derruba o anterior, e só o último sobrevive para disparar. A
    asserção sobre o conteúdo do arquivo, sozinha, passaria também num sistema
    que exportasse na hora a cada mutação — que é o oposto da regra.
    """
    api.project("Aurora")
    api.project("Boreal")
    api.sprints(18, 19)

    timers = api.snapshot_timers.created
    assert len(timers) == 4
    assert [timer.cancelled for timer in timers] == [True, True, True, False]

    api.flush_snapshot()

    assert [timer.fired for timer in timers] == [False, False, False, True]
    text = (api.snapshot_dir / "projects.json").read_text(encoding="utf-8")
    assert "Aurora" in text
    assert "Boreal" in text


def test_the_debouncer_survives_the_request_that_created_it(api: Api) -> None:
    """A memoização em `app.state` **é** o mecanismo do coalescing (RNF3).

    Um debouncer novo por requisição não teria o que cancelar, e o teste acima
    veria quatro timers vivos em vez de um. Este aqui olha a causa em vez do
    efeito: é a mesma instância nas quatro requisições, e é ela que está em
    `app.state`.
    """
    api.project("Aurora")
    first = api.app.state.snapshot_debouncer
    api.project("Boreal")

    assert api.app.state.snapshot_debouncer is first
    assert len(api.snapshot_timers.created) == 2


def test_a_read_does_not_schedule_anything(api: Api) -> None:
    api.get("/projects")
    api.get("/planning/grid")

    assert not api.snapshot_scheduled
    assert not api.snapshot_dir.exists()


def test_a_mutation_that_failed_does_not_schedule_anything(api: Api) -> None:
    """A cada mutação **bem-sucedida** (RNF3). Uma requisição que virou 4xx não
    gravou nada, e não há o que exportar."""
    response = api.post("/projects", json={"name": "   "})

    assert response.status_code == 422
    assert not api.snapshot_scheduled


def test_an_unknown_route_does_not_schedule_anything(api: Api) -> None:
    assert api.post("/projetos").status_code == 404
    assert not api.snapshot_scheduled


def test_the_import_does_not_trigger_an_automatic_export(
    api: Api, clock: FrozenClock, tmp_path: Path
) -> None:
    """RNF3, última frase. Quem acabou de restaurar quer olhar o resultado
    antes de o sistema reescrever a pasta sincronizada."""
    source = _source_snapshot(tmp_path / "origem", clock)

    response = api.post(
        "/snapshots/import", params={"confirm": True}, json={"path": str(source)}
    )

    assert response.status_code == 200
    assert not api.snapshot_scheduled
    assert not api.snapshot_dir.exists()


def test_the_explicit_export_does_not_schedule_another_one(api: Api) -> None:
    """Escrever a pasta sincronizada duas vezes pelo mesmo pedido não serve a
    ninguém."""
    api.post("/snapshots/export")

    assert not api.snapshot_scheduled
