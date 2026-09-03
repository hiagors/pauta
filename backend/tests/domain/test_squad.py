"""Squad: agrupamento com prazo, sem lista de membros (§6.5)."""

import pytest

from app.domain.entities.squad import Squad
from app.domain.errors import InvalidName
from tests.domain.conftest import uid


def test_criacao() -> None:
    squad = Squad.create(name="Alfa")
    assert squad.is_active
    assert squad.representative_member_id is None


def test_nome_e_obrigatorio() -> None:
    with pytest.raises(InvalidName):
        Squad.create(name=" ")


def test_a_squad_nao_carrega_lista_de_membros() -> None:
    campos = set(Squad.__dataclass_fields__)
    assert not campos & {"member_ids", "members"}


def test_representante_e_opcional_e_nao_e_validado_contra_a_composicao() -> None:
    """RN-S1: no momento da criação a squad não tem membership nenhuma."""
    squad = Squad.create(name="Alfa", representative_member_id=uid(7))
    assert squad.representative_member_id == uid(7)
    squad.set_representative(None)
    assert squad.representative_member_id is None
