"""Composição por sprint: o caso da Emilie (§6.5)."""

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
    bnpl, crm = uid(1), uid(2)
    emilie = uid(10)
    sprint_19, sprint_20 = uid(19), uid(20)
    linhas = [
        SquadMembership.create(squad_id=bnpl, member_id=emilie, sprint_id=sprint_19),
        SquadMembership.create(squad_id=crm, member_id=emilie, sprint_id=sprint_20),
    ]
    assert {linha.squad_id for linha in linhas} == {bnpl, crm}
    assert len({linha.id for linha in linhas}) == 2
