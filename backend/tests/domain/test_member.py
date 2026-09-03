"""Membro: nunca deletado, só inativado (§6.4)."""

import pytest

from app.domain.entities.member import Member
from app.domain.errors import InvalidName


def test_a_member_is_created_active() -> None:
    member = Member.create(name="Ana Martins", short_name="Ana", role="Dados")
    assert member.is_active


def test_the_name_and_the_short_name_are_required() -> None:
    with pytest.raises(InvalidName):
        Member.create(name="", short_name="Ana")
    with pytest.raises(InvalidName):
        Member.create(name="Ana", short_name="  ")


def test_deactivating_does_not_delete() -> None:
    member = Member.create(name="Ana", short_name="Ana")
    member.deactivate()
    assert member.is_active is False
    assert member.name == "Ana"


def test_reactivating() -> None:
    member = Member.create(name="Ana", short_name="Ana")
    member.deactivate()
    member.activate()
    assert member.is_active


def test_the_person_entity_carries_nothing_about_authentication() -> None:
    fields = set(Member.__dataclass_fields__)
    assert not fields & {"email", "password", "password_hash", "username"}
