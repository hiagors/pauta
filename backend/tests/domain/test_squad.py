"""Squad: agrupamento com prazo, sem lista de membros (§6.5)."""

import pytest

from app.domain.entities.squad import Squad
from app.domain.errors import InvalidName
from tests.domain.conftest import uid


def test_a_squad_is_created_active() -> None:
    squad = Squad.create(name="Alfa")
    assert squad.is_active
    assert squad.representative_member_id is None


def test_the_name_is_required() -> None:
    with pytest.raises(InvalidName):
        Squad.create(name=" ")


def test_a_squad_does_not_carry_a_member_list() -> None:
    fields = set(Squad.__dataclass_fields__)
    assert not fields & {"member_ids", "members"}


def test_the_representative_is_optional_and_not_validated_against_the_composition() -> (
    None
):
    """RN-S1: no momento da criação a squad não tem membership nenhuma."""
    squad = Squad.create(name="Alfa", representative_member_id=uid(7))
    assert squad.representative_member_id == uid(7)
    squad.set_representative(None)
    assert squad.representative_member_id is None
