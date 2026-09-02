"""Apoio comum aos use cases de composição de squad (§6.5).

A composição é **por sprint** (D11): não existe "os membros da squad", existe
"os membros da squad na Sprint 20". Três use cases montam essa leitura do mesmo
jeito, e a montagem mora aqui para ser uma só.
"""

from collections.abc import Sequence
from uuid import UUID

from app.application.dto.members import MemberView
from app.application.dto.squads import SprintCompositionView
from app.domain.entities.sprint import Sprint
from app.domain.errors import SprintNotFound
from app.domain.ports.repositories import (
    MemberRepository,
    SprintRepository,
    SquadMembershipRepository,
)
from app.domain.value_objects.sprint_range import SprintRange


def resolve_sprint_range(
    *, sprints: SprintRepository, sprint_range: SprintRange
) -> list[Sprint]:
    """As sprints do intervalo, todas elas.

    Aqui, ao contrário da alocação (RN5), sprint faltando é 404: a matriz de
    composição da UI só oferece sprints que existem, e aceitar um intervalo
    parcial em silêncio esconderia composição que o usuário acha que gravou.
    """
    found = {
        sprint.number: sprint
        for sprint in sprints.list_all(
            number_from=sprint_range.from_number, number_to=sprint_range.to_number
        )
    }
    missing = [number for number in sprint_range if number not in found]
    if missing:
        raise SprintNotFound(number=missing[0])
    return [found[number] for number in sprint_range]


def compose_by_sprint(
    *,
    squad_id: UUID,
    sprints: Sequence[Sprint],
    memberships: SquadMembershipRepository,
    members: MemberRepository,
) -> tuple[SprintCompositionView, ...]:
    """Uma entrada por sprint informada, mesmo quando a squad está vazia nela.

    Sprint vazia na resposta não é ruído: é o que a matriz precisa para
    desenhar a célula em branco, e é o que dispara `EMPTY_SQUAD` se houver
    alocação (RN-S2).
    """
    links = memberships.list_all(
        squad_id=squad_id, sprint_ids=[sprint.id for sprint in sprints]
    )
    by_sprint: dict[UUID, set[UUID]] = {sprint.id: set() for sprint in sprints}
    for link in links:
        by_sprint.setdefault(link.sprint_id, set()).add(link.member_id)
    known = {
        member.id: member
        for member in members.list_by_ids(
            {member_id for ids in by_sprint.values() for member_id in ids}
        )
    }
    return tuple(
        SprintCompositionView(
            sprint_id=sprint.id,
            sprint_number=sprint.number,
            members=tuple(
                MemberView.of(member)
                for member in sorted(
                    (
                        known[member_id]
                        for member_id in by_sprint[sprint.id]
                        if member_id in known
                    ),
                    key=lambda member: (member.name.casefold(), str(member.id)),
                )
            ),
        )
        for sprint in sorted(sprints, key=lambda sprint: sprint.number)
    )
