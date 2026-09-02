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
    view = fakes.use_case(CreateSquad).execute(CreateSquadInput(name="Dados-A"))

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
    bianca = world.member("Bianca")

    view = fakes.use_case(CreateSquad).execute(
        CreateSquadInput(name="Dados-A", representative_member_id=bianca.id)
    )

    assert view.representative_member_id == bianca.id
    assert fakes.memberships.list_all(squad_id=view.id) == []


def test_create_squad_refuses_an_inactive_representative(
    world: World, fakes: Fakes
) -> None:
    ana = world.member("Ana", active=False)

    with pytest.raises(InvalidRepresentative):
        fakes.use_case(CreateSquad).execute(
            CreateSquadInput(name="Dados-A", representative_member_id=ana.id)
        )


def test_create_squad_refuses_an_unknown_representative(fakes: Fakes) -> None:
    with pytest.raises(InvalidRepresentative):
        fakes.use_case(CreateSquad).execute(
            CreateSquadInput(name="Dados-A", representative_member_id=uid(999))
        )


def test_create_squad_rejects_duplicate_name(fakes: Fakes) -> None:
    create = fakes.use_case(CreateSquad)
    create.execute(CreateSquadInput(name="Dados-A"))

    with pytest.raises(DuplicateName):
        create.execute(CreateSquadInput(name="Dados-A"))


def test_update_squad_can_drop_the_representative(world: World, fakes: Fakes) -> None:
    bianca = world.member("Bianca")
    squad = world.squad("Dados-A")
    squad.set_representative(bianca.id)
    fakes.squads.update(squad)

    view = fakes.use_case(UpdateSquad).execute(
        squad.id, UpdateSquadInput(representative_member_id=None)
    )

    assert view.representative_member_id is None


def test_deactivate_squad_keeps_the_row(world: World, fakes: Fakes) -> None:
    squad = world.squad("Dados-A")

    view = fakes.use_case(DeactivateSquad).execute(squad.id)

    assert view.is_active is False
    stored = fakes.squads.get(squad.id)
    assert stored is not None
    assert stored.is_active is False


def test_set_memberships_replaces_the_range(world: World, fakes: Fakes) -> None:
    world.sprints(18, 22)
    squad = world.squad("Dados-A")
    bianca = world.member("Bianca")
    gabriel = world.member("Gabriel")
    set_memberships = fakes.use_case(SetSquadMemberships)

    set_memberships.execute(
        squad.id, SetMembershipsInput(18, 20, (bianca.id, gabriel.id))
    )
    composition = set_memberships.execute(
        squad.id, SetMembershipsInput(19, 19, (bianca.id,))
    )

    assert [view.sprint_number for view in composition] == [19]
    assert [member.short_name for member in composition[0].members] == ["Bianca"]

    whole = fakes.use_case(ListSquadMemberships).execute(squad.id)
    assert {
        view.sprint_number: [member.short_name for member in view.members]
        for view in whole
    } == {
        18: ["Bianca", "Gabriel"],
        19: ["Bianca"],
        20: ["Bianca", "Gabriel"],
        21: [],
        22: [],
    }


def test_set_memberships_with_an_empty_list_empties_the_range(
    world: World, fakes: Fakes
) -> None:
    """Squad vazia com alocação é `EMPTY_SQUAD`, informativo, nunca bloqueio."""
    world.sprints(18, 19)
    squad = world.squad("Dados-A")
    bianca = world.member("Bianca")
    set_memberships = fakes.use_case(SetSquadMemberships)
    set_memberships.execute(squad.id, SetMembershipsInput(18, 19, (bianca.id,)))

    composition = set_memberships.execute(squad.id, SetMembershipsInput(18, 19, ()))

    assert [view.members for view in composition] == [(), ()]


def test_the_emilie_case_does_not_leak_between_squads(
    world: World, fakes: Fakes
) -> None:
    """Emilie no BNPL nas 18-19 e no CRM da 20 em diante (§6.5)."""
    world.sprints(18, 22)
    bnpl = world.squad("BNPL")
    crm = world.squad("CRM")
    emilie = world.member("Emilie")
    set_memberships = fakes.use_case(SetSquadMemberships)

    set_memberships.execute(bnpl.id, SetMembershipsInput(18, 19, (emilie.id,)))
    set_memberships.execute(crm.id, SetMembershipsInput(20, 22, (emilie.id,)))

    def sprints_of(squad_id: UUID) -> list[int]:
        return [
            view.sprint_number
            for view in fakes.use_case(ListSquadMemberships).execute(squad_id)
            if view.members
        ]

    assert sprints_of(bnpl.id) == [18, 19]
    assert sprints_of(crm.id) == [20, 21, 22]


def test_set_memberships_requires_existing_members(world: World, fakes: Fakes) -> None:
    world.sprints(18, 18)
    squad = world.squad("Dados-A")

    with pytest.raises(MemberNotFound):
        fakes.use_case(SetSquadMemberships).execute(
            squad.id, SetMembershipsInput(18, 18, (uid(999),))
        )


def test_set_memberships_requires_the_whole_sprint_range_to_exist(
    world: World, fakes: Fakes
) -> None:
    """Diferente da alocação (RN5): composição não aceita intervalo parcial."""
    world.sprints(18, 19)
    squad = world.squad("Dados-A")
    bianca = world.member("Bianca")

    with pytest.raises(SprintNotFound):
        fakes.use_case(SetSquadMemberships).execute(
            squad.id, SetMembershipsInput(18, 21, (bianca.id,))
        )


def test_remove_memberships_takes_out_only_who_was_asked(
    world: World, fakes: Fakes
) -> None:
    world.sprints(18, 20)
    squad = world.squad("Dados-A")
    bianca = world.member("Bianca")
    gabriel = world.member("Gabriel")
    fakes.use_case(SetSquadMemberships).execute(
        squad.id, SetMembershipsInput(18, 20, (bianca.id, gabriel.id))
    )

    composition = fakes.use_case(RemoveSquadMemberships).execute(
        squad.id, RemoveMembershipsInput(19, 20, (gabriel.id,))
    )

    assert {
        view.sprint_number: [member.short_name for member in view.members]
        for view in composition
    } == {19: ["Bianca"], 20: ["Bianca"]}
    assert len(fakes.memberships.list_all(squad_id=squad.id)) == 4


def test_remove_memberships_without_ids_empties_the_range(
    world: World, fakes: Fakes
) -> None:
    world.sprints(18, 20)
    squad = world.squad("Dados-A")
    bianca = world.member("Bianca")
    fakes.use_case(SetSquadMemberships).execute(
        squad.id, SetMembershipsInput(18, 20, (bianca.id,))
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
    squad = world.squad("Dados-A")
    bianca = world.member("Bianca")
    world.join(squad, bianca, 19, 20)

    view = fakes.use_case(GetSquad).execute(squad.id)

    assert [item.sprint_number for item in view.memberships] == [19, 20]
    assert view.squad.name == "Dados-A"


def test_list_squads_expands_the_composition_of_the_asked_sprint(
    world: World, fakes: Fakes
) -> None:
    world.sprints(18, 20)
    dados_a = world.squad("Dados-A")
    world.squad("Dados-B")
    bianca = world.member("Bianca")
    world.join(dados_a, bianca, 19)

    without = fakes.use_case(ListSquads).execute()
    assert [view.members for view in without] == [(), ()]

    with_sprint = fakes.use_case(ListSquads).execute(sprint_number=19)
    assert {
        view.name: [member.short_name for member in view.members]
        for view in with_sprint
    } == {"Dados-A": ["Bianca"], "Dados-B": []}
    assert {view.sprint_number for view in with_sprint} == {19}


def test_list_squads_reports_an_unknown_sprint(world: World, fakes: Fakes) -> None:
    world.sprints(18, 18)
    world.squad("Dados-A")

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
