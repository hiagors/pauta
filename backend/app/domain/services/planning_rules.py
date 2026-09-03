"""Regras de planejamento que atravessam mais de uma entidade.

Reúne três coisas que andam juntas:

1. a **fotografia** (`PlanningSnapshot`) que `evaluate_alerts` e a grade
   consomem — um modelo de leitura imutável que o use case monta a partir dos
   repositórios, para que o domínio nunca receba repositório;
2. o **calendário de sprints**: invariantes do conjunto (§6.6), sprint atual
   (RN12), proposta da próxima (RN10) e janela default da grade (RN13);
3. a **alocação em intervalo** (RN1, RN5, RN8) e a alocação **efetiva** de um
   membro (§6.8).

As buscas são varreduras lineares. A escala real é de uma dezena de membros por
uma dezena de sprints; índice aqui seria complexidade sem ganho.
"""

import calendar
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from itertools import pairwise
from types import MappingProxyType
from uuid import UUID

from app.domain.entities.sprint import Sprint
from app.domain.errors import (
    AllocationConflict,
    SprintNotFound,
    SprintNumberGap,
    SprintNumberTaken,
    SprintOverlap,
)
from app.domain.value_objects.assignee import Assignee
from app.domain.value_objects.sprint_range import SprintRange

#: Padrão do §6.6: começa numa segunda, termina na sexta da semana seguinte.
DEFAULT_SPRINT_LENGTH_DAYS = 11

_MONDAY = 0
_MONTHS_PER_QUARTER = 3


# --------------------------------------------------------------------------- #
# Fotografia do plano
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class InitiativeRef:
    """Iniciativa com o que os alertas precisam saber do projeto dela.

    `is_capacity_reserve` é **herdado do projeto** (§6.2): a iniciativa não tem
    esse campo, e é o use case que resolve o projeto e traz o booleano.
    """

    id: UUID
    name: str
    project_id: UUID
    project_name: str
    is_capacity_reserve: bool

    @property
    def label(self) -> str:
        """ "Projeto / Iniciativa" — o rótulo das mensagens de alerta."""
        return f"{self.project_name} / {self.name}"


@dataclass(frozen=True)
class AllocationFact:
    sprint_number: int
    initiative: InitiativeRef
    assignee: Assignee


@dataclass(frozen=True)
class MembershipFact:
    sprint_number: int
    squad_id: UUID
    member_id: UUID


@dataclass(frozen=True)
class PlanningSnapshot:
    """Tudo o que o cálculo de alertas precisa, sem repositório.

    `members` contém **apenas** os ativos: é assim que a premissa A3 do §16
    (inativo só desaparece) fica implementada num lugar só, e é o que os dois
    alertas de membro do §7.3 pedem ao dizer "membro ativo".

    `squads` contém **todas**, ativas ou não. A tabela do §7.3 qualifica
    "squad ativa" em `EMPTY_SQUAD` e não qualifica em `SQUAD_OVERLOADED`, e a
    assimetria é deliberada: inativar uma squad não apaga o que ela ficou
    devendo. Quem separa as duas é `inactive_squad_ids`.
    """

    sprint_numbers: tuple[int, ...]
    allocations: tuple[AllocationFact, ...] = ()
    memberships: tuple[MembershipFact, ...] = ()
    squads: Mapping[UUID, str] = field(default_factory=dict)
    members: Mapping[UUID, str] = field(default_factory=dict)
    #: Vazio significa "nenhuma inativa", que é o que vale em quase todo
    #: cenário — e é o default certo para quem monta uma fotografia à mão.
    inactive_squad_ids: frozenset[UUID] = frozenset()
    current_sprint_number: int | None = None

    def squad_is_active(self, squad_id: UUID) -> bool:
        return squad_id not in self.inactive_squad_ids

    @property
    def idle_from(self) -> int | None:
        """Primeira sprint "atual ou futura" para o `MEMBER_IDLE` (§7.3).

        Se nenhuma sprint começou (RN12: `is_current` é `false` em todas), toda
        sprint da janela é futura e entra.
        """
        if not self.sprint_numbers:
            return None
        if self.current_sprint_number is None:
            return min(self.sprint_numbers)
        return self.current_sprint_number

    def squad_ids_of(self, member_id: UUID, sprint_number: int) -> frozenset[UUID]:
        """Squads a que o membro pertence **naquela** sprint."""
        return frozenset(
            fact.squad_id
            for fact in self.memberships
            if fact.member_id == member_id and fact.sprint_number == sprint_number
        )

    def member_ids_of(self, squad_id: UUID, sprint_number: int) -> frozenset[UUID]:
        return frozenset(
            fact.member_id
            for fact in self.memberships
            if fact.squad_id == squad_id and fact.sprint_number == sprint_number
        )


# --------------------------------------------------------------------------- #
# Alocação efetiva (§6.8)
# --------------------------------------------------------------------------- #


def squad_initiatives(
    snapshot: PlanningSnapshot,
    *,
    squad_id: UUID,
    sprint_number: int,
    include_capacity_reserve: bool,
) -> tuple[InitiativeRef, ...]:
    """Iniciativas em que a squad está naquela sprint."""
    return _distinct(
        fact.initiative
        for fact in snapshot.allocations
        if fact.sprint_number == sprint_number
        and fact.assignee.squad_id == squad_id
        and (include_capacity_reserve or not fact.initiative.is_capacity_reserve)
    )


def effective_initiatives(
    snapshot: PlanningSnapshot,
    *,
    member_id: UUID,
    sprint_number: int,
    include_capacity_reserve: bool,
) -> tuple[InitiativeRef, ...]:
    """Alocação efetiva do membro na sprint (§6.8).

    A união de: alocações diretas dele, e alocações das squads a que ele
    pertence **naquela** sprint. Conceito derivado, não tabela.
    """
    squad_ids = snapshot.squad_ids_of(member_id, sprint_number)
    return _distinct(
        fact.initiative
        for fact in snapshot.allocations
        if fact.sprint_number == sprint_number
        and (
            fact.assignee.member_id == member_id
            or (
                fact.assignee.squad_id is not None
                and fact.assignee.squad_id in squad_ids
            )
        )
        and (include_capacity_reserve or not fact.initiative.is_capacity_reserve)
    )


def _distinct(refs: Iterable[InitiativeRef]) -> tuple[InitiativeRef, ...]:
    """Deduplica por id e ordena por rótulo, para a saída ser determinística."""
    unique: dict[UUID, InitiativeRef] = {}
    for ref in refs:
        unique.setdefault(ref.id, ref)
    return tuple(sorted(unique.values(), key=lambda ref: (ref.label, str(ref.id))))


# --------------------------------------------------------------------------- #
# Calendário de sprints
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SprintProposal:
    """Proposta da próxima sprint (RN10). Editável antes de confirmar."""

    number: int
    start_date: date
    end_date: date


def validate_sprint_sequence(sprints: Sequence[Sprint]) -> None:
    """Invariantes do **conjunto** de sprints (§6.6).

    Numeração sequencial sem buraco, e `start_date` da N+1 posterior ao
    `end_date` da N — que, junto com a contiguidade, é o que garante a ausência
    de sobreposição.
    """
    ordered = sorted(sprints, key=lambda sprint: sprint.number)
    seen: set[int] = set()
    for sprint in ordered:
        if sprint.number in seen:
            raise SprintNumberTaken(sprint.number)
        seen.add(sprint.number)
    for previous, current in pairwise(ordered):
        if current.number != previous.number + 1:
            raise SprintNumberGap(previous.number + 1, current.number)
        if current.start_date <= previous.end_date:
            raise SprintOverlap(current.number, previous.number)


def ensure_can_add_sprint(existing: Sequence[Sprint], candidate: Sprint) -> None:
    """A sprint nova só entra se o conjunto resultante continuar válido.

    Não exige que a numeração comece em 1: o time cadastra a primeira sprint
    com o número que ela tem na vida real (a 18, no dado atual).
    """
    validate_sprint_sequence([*existing, candidate])


def current_sprint(sprints: Sequence[Sprint], today: date) -> Sprint | None:
    """RN12: a de **maior `start_date` que já passou**, ignorando `end_date`.

    Uma sprint só termina de verdade quando a próxima começa, então uma folga de
    calendário entre duas não deixa o sistema sem sprint atual. Se nenhuma
    começou, não há sprint atual.
    """
    started = [sprint for sprint in sprints if sprint.start_date <= today]
    if not started:
        return None
    return max(started, key=lambda sprint: (sprint.start_date, sprint.number))


def is_current(sprint: Sprint, sprints: Sequence[Sprint], today: date) -> bool:
    current = current_sprint(sprints, today)
    return current is not None and current.id == sprint.id


def next_monday_after(day: date) -> date:
    """A próxima segunda **estritamente** depois de `day`."""
    return day + timedelta(days=7 - day.weekday() + _MONDAY)


def propose_next_sprint(
    sprints: Sequence[Sprint], *, length_days: int = DEFAULT_SPRINT_LENGTH_DAYS
) -> SprintProposal:
    """RN10: número incrementado, início na segunda seguinte ao fim da última,
    fim em `início + 11 dias`."""
    if not sprints:
        raise SprintNotFound
    last = max(sprints, key=lambda sprint: sprint.number)
    start = next_monday_after(last.end_date)
    return SprintProposal(
        number=last.number + 1,
        start_date=start,
        end_date=start + timedelta(days=length_days),
    )


def civil_quarter_bounds(today: date) -> tuple[date, date]:
    """Trimestre **civil** que contém `today` (premissa A1 do §16).

    Trocar por um trimestre fiscal deslocado é mexer só nesta função.
    """
    quarter = (today.month - 1) // _MONTHS_PER_QUARTER
    first_month = quarter * _MONTHS_PER_QUARTER + 1
    last_month = first_month + _MONTHS_PER_QUARTER - 1
    last_day = calendar.monthrange(today.year, last_month)[1]
    return date(today.year, first_month, 1), date(today.year, last_month, last_day)


def sprints_in_quarter(sprints: Sequence[Sprint], today: date) -> list[Sprint]:
    """RN13: as sprints cujo intervalo intersecta o trimestre corrente."""
    start, end = civil_quarter_bounds(today)
    return sorted(
        (sprint for sprint in sprints if sprint.intersects(start, end)),
        key=lambda sprint: sprint.number,
    )


# --------------------------------------------------------------------------- #
# Alocação em intervalo
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AllocationPlan:
    """O que a alocação em intervalo vai fazer, antes de fazer.

    Espelha a resposta de `POST /allocations` (§8).
    """

    to_create: tuple[int, ...]
    already_existing: tuple[int, ...]
    missing_sprint_numbers: tuple[int, ...]


def plan_allocation(
    *,
    initiative_id: UUID,
    sprint_range: SprintRange,
    assignee: Assignee,
    existing_sprint_numbers: Collection[int],
    occupied: Mapping[int, Assignee],
    occupant_names: Mapping[UUID, str] = MappingProxyType({}),
) -> AllocationPlan:
    """Decide célula por célula o que fazer no intervalo pedido.

    - sprint que não existe -> `missing_sprint_numbers`; a operação **não** cai
      (RN5), e a UI mostra o atalho para criar a próxima sprint;
    - célula já ocupada pelo **mesmo** responsável -> `already_existing`, porque
      alocar é idempotente (RN1);
    - célula ocupada por **outro** responsável -> `AllocationConflict` (RN8):
      uma iniciativa tem um responsável por sprint;
    - célula livre -> `to_create`.

    `occupant_names` é o que a RN8 pede ao dizer "a mensagem apontando quem já
    está lá". É opcional porque o domínio não sabe buscar nome: quem o resolve
    é o use case. Sem o mapa, a frase sai genérica.
    """
    to_create: list[int] = []
    already_existing: list[int] = []
    missing: list[int] = []
    for number in sprint_range:
        if number not in existing_sprint_numbers:
            missing.append(number)
            continue
        occupant = occupied.get(number)
        if occupant is None:
            to_create.append(number)
        elif occupant == assignee:
            already_existing.append(number)
        else:
            raise AllocationConflict(
                initiative_id=initiative_id,
                sprint_number=number,
                occupant_kind=occupant.kind.value,
                occupant_id=occupant.id,
                occupant_name=occupant_names.get(occupant.id),
            )
    return AllocationPlan(
        to_create=tuple(to_create),
        already_existing=tuple(already_existing),
        missing_sprint_numbers=tuple(missing),
    )
