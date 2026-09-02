"""Membro: nunca deletado, só inativado (§6.4)."""

import pytest

from app.domain.entities.member import Member
from app.domain.errors import InvalidName


def test_criacao() -> None:
    member = Member.create(name="Bianca Souza", short_name="Bianca", role="Dados")
    assert member.is_active


def test_nome_e_nome_curto_sao_obrigatorios() -> None:
    with pytest.raises(InvalidName):
        Member.create(name="", short_name="Bianca")
    with pytest.raises(InvalidName):
        Member.create(name="Bianca", short_name="  ")


def test_inativar_nao_apaga() -> None:
    member = Member.create(name="Bianca", short_name="Bianca")
    member.deactivate()
    assert member.is_active is False
    assert member.name == "Bianca"


def test_reativar() -> None:
    member = Member.create(name="Bianca", short_name="Bianca")
    member.deactivate()
    member.activate()
    assert member.is_active


def test_a_entidade_de_pessoa_nao_tem_nada_de_autenticacao() -> None:
    campos = set(Member.__dataclass_fields__)
    assert not campos & {"email", "password", "password_hash", "username"}
