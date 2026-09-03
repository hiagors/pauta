"""Composição por sprint: o caso da Carla (§6.5)."""

from app.domain.entities.squad_membership import SquadMembership
from tests.domain.conftest import uid


def test_uma_linha_por_sprint() -> None:
    membership = SquadMembership.create(
        squad_id=uid(1), member_id=uid(2), sprint_id=uid(3)
    )
    assert membership.squad_id == uid(1)
    assert membership.member_id == uid(2)
    assert membership.sprint_id == uid(3)


def test_a_mesma_pessoa_em_squads_diferentes_em_sprints_diferentes() -> None:
    boreal, aurora = uid(1), uid(2)
    carla = uid(10)
    sprint_19, sprint_20 = uid(19), uid(20)
    linhas = [
        SquadMembership.create(squad_id=boreal, member_id=carla, sprint_id=sprint_19),
        SquadMembership.create(squad_id=aurora, member_id=carla, sprint_id=sprint_20),
    ]
    assert {linha.squad_id for linha in linhas} == {boreal, aurora}
    assert len({linha.id for linha in linhas}) == 2
