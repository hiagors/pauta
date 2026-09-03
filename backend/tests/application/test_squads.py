"""Use cases de squad e da composição por sprint (§6.5, D11)."""

from uuid import UUID

import pytest

from app.application.dto.squads import (
    CreateSquadInput,
    RemoveMembershipsInput,
    SetMembershipsInput,
    UpdateSquadInput,
)
from app.application.use_cases.squads.create import CreateSquad
from app.application.use_cases.squads.deactivate import DeactivateSquad
from app.application.use_cases.squads.get import GetSquad
from app.application.use_cases.squads.list import ListSquads
from app.application.use_cases.squads.list_memberships import ListSquadMemberships
from app.application.use_cases.squads.remove_memberships import RemoveSquadMemberships
from app.application.use_cases.squads.set_memberships import SetSquadMemberships
from app.application.use_cases.squads.update import UpdateSquad
from app.domain.errors import (
    DuplicateName,
    InvalidRepresentative,
    MemberNotFound,
    SprintNotFound,
    SquadNotFound,
)
from tests.application.conftest import Fakes, World
from tests.domain.conftest import uid


def test_create_squad_without_representative(fakes: Fakes) -> None:
    view = fakes.use_case(CreateSquad).execute(CreateSquadInput(name="Alfa"))

    assert view.representative_member_id is None
    assert view.is_active is True
    assert view.members == ()
    assert view.sprint_number is None


def test_create_squad_accepts_a_representative_who_is_not_a_member_yet(
    world: World, fakes: Fakes
) -> None:
    """RN-S1: o representante é uma ponte, não necessariamente quem executa.

    Na criação a squad não tem membership nenhuma — validar contra a composição
    tornaria impossível cadastrar squad com representante.
    """
    ana = world.member("Ana")

    view = fakes.use_case(CreateSquad).execute(
        CreateSquadInput(name="Alfa", representative_member_id=ana.id)
    )

    assert view.representative_member_id == ana.id
    assert fakes.memberships.list_all(squad_id=view.id) == []


def test_create_squad_refuses_an_inactive_representative(
    world: World, fakes: Fakes
) -> None:
    ana = world.member("Ana", active=False)

    with pytest.raises(InvalidRepresentative):
        fakes.use_case(CreateSquad).execute(
            CreateSquadInput(name="Alfa", representative_member_id=ana.id)
        )


def test_create_squad_refuses_an_unknown_representative(fakes: Fakes) -> None:
    with pytest.raises(InvalidRepresentative):
        fakes.use_case(CreateSquad).execute(
            CreateSquadInput(name="Alfa", representative_member_id=uid(999))
        )


def test_create_squad_rejects_duplicate_name(fakes: Fakes) -> None:
    create = fakes.use_case(CreateSquad)
    create.execute(CreateSquadInput(name="Alfa"))

    with pytest.raises(DuplicateName):
        create.execute(CreateSquadInput(name="Alfa"))


def test_update_squad_can_drop_the_representative(world: World, fakes: Fakes) -> None:
    ana = world.member("Ana")
    squad = world.squad("Alfa")
    squad.set_representative(ana.id)
    fakes.squads.update(squad)

    view = fakes.use_case(UpdateSquad).execute(
        squad.id, UpdateSquadInput(representative_member_id=None)
    )

    assert view.representative_member_id is None


def test_deactivate_squad_keeps_the_row(world: World, fakes: Fakes) -> None:
    squad = world.squad("Alfa")

    view = fakes.use_case(DeactivateSquad).execute(squad.id)

    assert view.is_active is False
    stored = fakes.squads.get(squad.id)
    assert stored is not None
    assert stored.is_active is False


def test_set_memberships_replaces_the_range(world: World, fakes: Fakes) -> None:
    world.sprints(18, 22)
    squad = world.squad("Alfa")
    ana = world.member("Ana")
    bruno = world.member("Bruno")
    set_memberships = fakes.use_case(SetSquadMemberships)

    set_memberships.execute(squad.id, SetMembershipsInput(18, 20, (ana.id, bruno.id)))
    composition = set_memberships.execute(
        squad.id, SetMembershipsInput(19, 19, (ana.id,))
    )

    assert [view.sprint_number for view in composition] == [19]
    assert [member.short_name for member in composition[0].members] == ["Ana"]

    whole = fakes.use_case(ListSquadMemberships).execute(squad.id)
    assert {
        view.sprint_number: [member.short_name for member in view.members]
        for view in whole
    } == {
        18: ["Ana", "Bruno"],
        19: ["Ana"],
        20: ["Ana", "Bruno"],
        21: [],
        22: [],
    }


def test_set_memberships_with_an_empty_list_empties_the_range(
    world: World, fakes: Fakes
) -> None:
    """Squad vazia com alocação é `EMPTY_SQUAD`, informativo, nunca bloqueio."""
    world.sprints(18, 19)
    squad = world.squad("Alfa")
    ana = world.member("Ana")
    set_memberships = fakes.use_case(SetSquadMemberships)
    set_memberships.execute(squad.id, SetMembershipsInput(18, 19, (ana.id,)))

    composition = set_memberships.execute(squad.id, SetMembershipsInput(18, 19, ()))

    assert [view.members for view in composition] == [(), ()]


def test_the_carla_case_does_not_leak_between_squads(
    world: World, fakes: Fakes
) -> None:
    """Carla no Boreal nas 18-19 e no Aurora da 20 em diante (§6.5)."""
    world.sprints(18, 22)
    boreal = world.squad("Boreal")
    aurora = world.squad("Aurora")
    carla = world.member("Carla")
    set_memberships = fakes.use_case(SetSquadMemberships)

    set_memberships.execute(boreal.id, SetMembershipsInput(18, 19, (carla.id,)))
    set_memberships.execute(aurora.id, SetMembershipsInput(20, 22, (carla.id,)))

    def sprints_of(squad_id: UUID) -> list[int]:
        return [
            view.sprint_number
            for view in fakes.use_case(ListSquadMemberships).execute(squad_id)
            if view.members
        ]

    assert sprints_of(boreal.id) == [18, 19]
    assert sprints_of(aurora.id) == [20, 21, 22]


def test_set_memberships_requires_existing_members(world: World, fakes: Fakes) -> None:
    world.sprints(18, 18)
    squad = world.squad("Alfa")

    with pytest.raises(MemberNotFound):
        fakes.use_case(SetSquadMemberships).execute(
            squad.id, SetMembershipsInput(18, 18, (uid(999),))
        )


def test_set_memberships_requires_the_whole_sprint_range_to_exist(
    world: World, fakes: Fakes
) -> None:
    """Diferente da alocação (RN5): composição não aceita intervalo parcial."""
    world.sprints(18, 19)
    squad = world.squad("Alfa")
    ana = world.member("Ana")

    with pytest.raises(SprintNotFound):
        fakes.use_case(SetSquadMemberships).execute(
            squad.id, SetMembershipsInput(18, 21, (ana.id,))
        )


def test_remove_memberships_takes_out_only_who_was_asked(
    world: World, fakes: Fakes
) -> None:
    world.sprints(18, 20)
    squad = world.squad("Alfa")
    ana = world.member("Ana")
    bruno = world.member("Bruno")
    fakes.use_case(SetSquadMemberships).execute(
        squad.id, SetMembershipsInput(18, 20, (ana.id, bruno.id))
    )

    composition = fakes.use_case(RemoveSquadMemberships).execute(
        squad.id, RemoveMembershipsInput(19, 20, (bruno.id,))
    )

    assert {
        view.sprint_number: [member.short_name for member in view.members]
        for view in composition
    } == {19: ["Ana"], 20: ["Ana"]}
    assert len(fakes.memberships.list_all(squad_id=squad.id)) == 4


def test_remove_memberships_without_ids_empties_the_range(
    world: World, fakes: Fakes
) -> None:
    world.sprints(18, 20)
    squad = world.squad("Alfa")
    ana = world.member("Ana")
    fakes.use_case(SetSquadMemberships).execute(
        squad.id, SetMembershipsInput(18, 20, (ana.id,))
    )

    fakes.use_case(RemoveSquadMemberships).execute(
        squad.id, RemoveMembershipsInput(18, 19)
    )

    assert [
        view.sprint_number
        for view in fakes.use_case(ListSquadMemberships).execute(squad.id)
        if view.members
    ] == [20]


def test_get_squad_shows_only_the_sprints_with_people(
    world: World, fakes: Fakes
) -> None:
    world.sprints(18, 22)
    squad = world.squad("Alfa")
    ana = world.member("Ana")
    world.join(squad, ana, 19, 20)

    view = fakes.use_case(GetSquad).execute(squad.id)

    assert [item.sprint_number for item in view.memberships] == [19, 20]
    assert view.squad.name == "Alfa"


def test_list_squads_expands_the_composition_of_the_asked_sprint(
    world: World, fakes: Fakes
) -> None:
    world.sprints(18, 20)
    alfa = world.squad("Alfa")
    world.squad("Beta")
    ana = world.member("Ana")
    world.join(alfa, ana, 19)

    without = fakes.use_case(ListSquads).execute()
    assert [view.members for view in without] == [(), ()]

    with_sprint = fakes.use_case(ListSquads).execute(sprint_number=19)
    assert {
        view.name: [member.short_name for member in view.members]
        for view in with_sprint
    } == {"Alfa": ["Ana"], "Beta": []}
    assert {view.sprint_number for view in with_sprint} == {19}


def test_list_squads_reports_an_unknown_sprint(world: World, fakes: Fakes) -> None:
    world.sprints(18, 18)
    world.squad("Alfa")

    with pytest.raises(SprintNotFound):
        fakes.use_case(ListSquads).execute(sprint_number=99)


def test_membership_use_cases_report_an_unknown_squad(fakes: Fakes) -> None:
    with pytest.raises(SquadNotFound):
        fakes.use_case(GetSquad).execute(uid(999))
    with pytest.raises(SquadNotFound):
        fakes.use_case(ListSquadMemberships).execute(uid(999))
    with pytest.raises(SquadNotFound):
        fakes.use_case(SetSquadMemberships).execute(
            uid(999), SetMembershipsInput(18, 18, ())
        )
