"""Cálculo dos quatro alertas do §7.3.

Puro: recebe a fotografia do plano (`PlanningSnapshot`) e o mapa de
silenciamentos, devolve alertas. Sem repositório, sem banco, sem mock nos
testes.

Devolve **todos** os alertas, inclusive os silenciados, já com `is_muted`,
`mute_id` e `mute_reason` preenchidos. Filtrar por `include_muted` é decisão do
use case — é isso que permite a resposta de `POST /allocations` dizer "já
silenciado" em vez de gritar de novo.

Nenhum alerta é bloqueio. Todos são aviso visual.
"""

from collections.abc import Iterator, Mapping, Sequence
from types import MappingProxyType
from uuid import UUID

from app.domain.entities.muted_alert import MutedAlert
from app.domain.services.fingerprint import alert_fingerprint
from app.domain.services.planning_rules import (
    InitiativeRef,
    PlanningSnapshot,
    effective_initiatives,
    squad_initiatives,
)
from app.domain.value_objects.alert import (
    Alert,
    AlertType,
    EntityRef,
    EntityRefType,
)

_NO_MUTES: Mapping[str, MutedAlert] = MappingProxyType({})

#: Mais de uma frente não-reserva na mesma sprint é conflito (§6.8).
_MAX_INITIATIVES_PER_SPRINT = 1


def evaluate_alerts(
    snapshot: PlanningSnapshot,
    mutes: Mapping[str, MutedAlert] = _NO_MUTES,
) -> list[Alert]:
    """Avalia a janela de `snapshot.sprint_numbers`, sprint por sprint.

    A ordem da saída é determinística — sprint, então a ordem de declaração
    do `AlertType`, então o nome do sujeito — para que os testes não
    dependam de ordem de dicionário.
    """
    alerts: list[Alert] = []
    for sprint_number in sorted(snapshot.sprint_numbers):
        alerts.extend(_squad_overloaded(snapshot, sprint_number))
        alerts.extend(_member_conflict(snapshot, sprint_number))
        alerts.extend(_member_idle(snapshot, sprint_number))
        alerts.extend(_empty_squad(snapshot, sprint_number))
    return [_apply_mute(alert, mutes) for alert in alerts]


# ------------------------------------------------------------------ #
# SQUAD_OVERLOADED — WARNING
# ------------------------------------------------------------------ #


def _squad_overloaded(
    snapshot: PlanningSnapshot, sprint_number: int
) -> Iterator[Alert]:
    """Squad em mais de uma iniciativa na mesma sprint (RN4).

    Iniciativas de projeto com `is_capacity_reserve` ficam fora da conta:
    quem está na sustentação sob demanda não fica travado (§3).

    Squad **inativa** entra. É o único dos quatro alertas que o §7.3 não
    qualifica com "ativa", e a assimetria é deliberada: inativar a squad não
    apaga as duas frentes que ela ficou devendo naquela sprint.
    """
    for squad_id, squad_name in _sorted(snapshot.squads):
        initiatives = squad_initiatives(
            snapshot,
            squad_id=squad_id,
            sprint_number=sprint_number,
            include_capacity_reserve=False,
        )
        if len(initiatives) <= _MAX_INITIATIVES_PER_SPRINT:
            continue
        yield _build(
            AlertType.SQUAD_OVERLOADED,
            sprint_number=sprint_number,
            subject=EntityRef(EntityRefType.SQUAD, squad_id, squad_name),
            initiatives=initiatives,
            extra=(),
            message=(
                f"Squad {squad_name} está em {len(initiatives)} iniciativas "
                f"na Sprint {sprint_number}: {_join(initiatives)}."
            ),
        )


# ------------------------------------------------------------------ #
# MEMBER_CONFLICT — WARNING
# ------------------------------------------------------------------ #


def _member_conflict(snapshot: PlanningSnapshot, sprint_number: int) -> Iterator[Alert]:
    """Membro com mais de uma iniciativa **efetiva** não-reserva (§6.8, RN9).

    Tipicamente por estar em duas squads naquela sprint. É aceito no dado e
    sinalizado; nunca bloqueio.
    """
    for member_id, member_name in _sorted(snapshot.members):
        initiatives = effective_initiatives(
            snapshot,
            member_id=member_id,
            sprint_number=sprint_number,
            include_capacity_reserve=False,
        )
        if len(initiatives) <= _MAX_INITIATIVES_PER_SPRINT:
            continue
        squad_refs = _squads_behind(snapshot, member_id, sprint_number, initiatives)
        has_direct = any(
            fact.assignee.member_id == member_id
            for fact in snapshot.allocations
            if fact.sprint_number == sprint_number
            and not fact.initiative.is_capacity_reserve
        )
        if squad_refs and not has_direct:
            squad_names = _join_names([ref.name for ref in squad_refs])
            message = (
                f"{member_name} está nas squads {squad_names}, alocadas na "
                f"Sprint {sprint_number} em {_join(initiatives)}."
            )
        else:
            message = (
                f"{member_name} está em {len(initiatives)} iniciativas na "
                f"Sprint {sprint_number}: {_join(initiatives)}."
            )
        yield _build(
            AlertType.MEMBER_CONFLICT,
            sprint_number=sprint_number,
            subject=EntityRef(EntityRefType.MEMBER, member_id, member_name),
            initiatives=initiatives,
            extra=squad_refs,
            message=message,
        )


def _squads_behind(
    snapshot: PlanningSnapshot,
    member_id: UUID,
    sprint_number: int,
    initiatives: Sequence[InitiativeRef],
) -> tuple[EntityRef, ...]:
    """As squads que levaram o membro às iniciativas em conflito."""
    initiative_ids = {ref.id for ref in initiatives}
    squad_ids = snapshot.squad_ids_of(member_id, sprint_number)
    involved = {
        fact.assignee.squad_id
        for fact in snapshot.allocations
        if fact.sprint_number == sprint_number
        and fact.initiative.id in initiative_ids
        and fact.assignee.squad_id in squad_ids
    }
    return tuple(
        EntityRef(EntityRefType.SQUAD, squad_id, snapshot.squads[squad_id])
        for squad_id, _ in _sorted(snapshot.squads)
        if squad_id in involved
    )


# ------------------------------------------------------------------ #
# MEMBER_IDLE — INFO
# ------------------------------------------------------------------ #


def _member_idle(snapshot: PlanningSnapshot, sprint_number: int) -> Iterator[Alert]:
    """Membro ativo sem nenhuma frente numa sprint atual ou futura.

    Reserva de capacidade **não** conta como trabalho aqui: é o que a
    própria flag significa. Se a iniciativa de sustentação não entra em
    contagem de capacidade (§3), quem está só nela tem capacidade livre — e
    `MEMBER_IDLE` é exatamente a pergunta de capacidade que fez o D16
    trocar `SQUAD_IDLE` por ele.

    A mensagem separa os dois casos. Dizer "não está em nenhuma frente"
    para quem está de plantão seria falso, e alerta que mente é alerta que
    se aprende a ignorar.

    Sem teto (premissa A2 do §16): toda sprint da atual em diante entra.
    """
    idle_from = snapshot.idle_from
    if idle_from is None or sprint_number < idle_from:
        return
    for member_id, member_name in _sorted(snapshot.members):
        initiatives = effective_initiatives(
            snapshot,
            member_id=member_id,
            sprint_number=sprint_number,
            include_capacity_reserve=False,
        )
        if initiatives:
            continue
        reserve = effective_initiatives(
            snapshot,
            member_id=member_id,
            sprint_number=sprint_number,
            include_capacity_reserve=True,
        )
        yield _build(
            AlertType.MEMBER_IDLE,
            sprint_number=sprint_number,
            subject=EntityRef(EntityRefType.MEMBER, member_id, member_name),
            initiatives=reserve,
            extra=(),
            message=(
                (
                    f"{member_name} está só em reserva de capacidade na "
                    f"Sprint {sprint_number}: {_join(reserve)}."
                )
                if reserve
                else (
                    f"{member_name} não está em nenhuma frente na "
                    f"Sprint {sprint_number}."
                )
            ),
        )


# ------------------------------------------------------------------ #
# EMPTY_SQUAD — INFO
# ------------------------------------------------------------------ #


def _empty_squad(snapshot: PlanningSnapshot, sprint_number: int) -> Iterator[Alert]:
    """Squad **ativa** com alocação na sprint e ninguém na composição (RN-S2).

    Informativo, nunca bloqueio: planejar antes de contratar é legítimo.

    Aqui o §7.3 escreve "squad ativa", ao contrário do `SQUAD_OVERLOADED`:
    cobrar composição de uma squad que foi desativada é pedir contratação
    para um agrupamento que acabou.
    """
    for squad_id, squad_name in _sorted(snapshot.squads):
        if not snapshot.squad_is_active(squad_id):
            continue
        initiatives = squad_initiatives(
            snapshot,
            squad_id=squad_id,
            sprint_number=sprint_number,
            include_capacity_reserve=True,
        )
        if not initiatives:
            continue
        if snapshot.member_ids_of(squad_id, sprint_number):
            continue
        yield _build(
            AlertType.EMPTY_SQUAD,
            sprint_number=sprint_number,
            subject=EntityRef(EntityRefType.SQUAD, squad_id, squad_name),
            initiatives=initiatives,
            extra=(),
            message=(
                f"Squad {squad_name} está alocada em {_join(initiatives)} na "
                f"Sprint {sprint_number}, mas não tem ninguém na composição "
                "dessa sprint."
            ),
        )


# ------------------------------------------------------------------ #


def _apply_mute(alert: Alert, mutes: Mapping[str, MutedAlert]) -> Alert:
    mute = mutes.get(alert.fingerprint)
    return alert.muted_by(mute) if mute is not None else alert


# --------------------------------------------------------------------------- #
# Auxiliares
# --------------------------------------------------------------------------- #


def _build(
    alert_type: AlertType,
    *,
    sprint_number: int,
    subject: EntityRef,
    initiatives: Sequence[InitiativeRef],
    extra: Sequence[EntityRef],
    message: str,
) -> Alert:
    """Monta o alerta com o sujeito na frente das `entity_refs`.

    O `fingerprint` sai daqui ancorado **só** no sujeito e na sprint: é o que
    mantém o silenciamento válido quando as iniciativas mudam (§7.3).
    """
    refs: list[EntityRef] = [subject, *extra]
    for initiative in initiatives:
        refs.append(EntityRef(EntityRefType.INITIATIVE, initiative.id, initiative.name))
        refs.append(
            EntityRef(
                EntityRefType.PROJECT, initiative.project_id, initiative.project_name
            )
        )
    return Alert.build(
        type=alert_type,
        sprint_number=sprint_number,
        subject_id=subject.id,
        entity_refs=_dedupe(refs),
        message=message,
        fingerprint=alert_fingerprint(alert_type, subject.id, sprint_number),
    )


def _dedupe(refs: Sequence[EntityRef]) -> tuple[EntityRef, ...]:
    seen: dict[tuple[EntityRefType, UUID], EntityRef] = {}
    for ref in refs:
        seen.setdefault((ref.type, ref.id), ref)
    return tuple(seen.values())


def _sorted(names: Mapping[UUID, str]) -> list[tuple[UUID, str]]:
    """Ordena sujeitos por nome, com o UUID como desempate estável."""
    return sorted(names.items(), key=lambda item: (item[1], str(item[0])))


def _join(initiatives: Sequence[InitiativeRef]) -> str:
    return _join_names([initiative.label for initiative in initiatives])


def _join_names(names: Sequence[str]) -> str:
    """ "a", "a e b", "a, b e c" — em português, sem vírgula antes do "e"."""
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} e {names[-1]}"
