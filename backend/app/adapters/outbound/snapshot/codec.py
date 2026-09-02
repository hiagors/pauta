"""A forma de cada linha do snapshot, nas duas direções (§9).

Codificar e decodificar moram juntos de propósito. O critério de aceite da
Fase 5 é um roundtrip `export -> import -> export` byte a byte idêntico, e isso
é uma propriedade do **par**: separar as duas metades em módulos diferentes é o
convite para que uma mude sem a outra.

Três regras de formato, todas para o diff no Git e no Drive ficar legível:

- chaves ordenadas e indentação de 2 (`dumps`);
- listas ordenadas por `id`, nunca por ordem de inserção;
- `ensure_ascii=False`, porque os nomes deste sistema são todos em português e
  `Reestrutura\\u00e7\\u00e3o` não é um diff que alguém leia.

Nenhum arquivo de entidade tem timestamp de geração (§9): ele mudaria o arquivo
inteiro a cada export sem mudança de dado. O registro da geração é o
`meta.json`.

A decodificação entra pelo **construtor da dataclass**, não por
`Entity.create()`: `create` é para entidade nova (gera `id`, lê o `Clock`), e o
que vem do snapshot já tem os dois. É o que preserva verbatim os UUIDs e o
`created_at` de `MutedAlert` (RNF4).
"""

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Final
from uuid import UUID

from app.domain.entities.allocation import Allocation
from app.domain.entities.initiative import Initiative
from app.domain.entities.member import Member
from app.domain.entities.muted_alert import MutedAlert
from app.domain.entities.project import Project
from app.domain.entities.sprint import Sprint
from app.domain.entities.squad import Squad
from app.domain.entities.squad_membership import SquadMembership
from app.domain.value_objects.alert import AlertType
from app.domain.value_objects.color import Color
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.priority import Priority

#: Uma linha do JSON, já em tipos primitivos.
type Row = dict[str, Any]

#: O único arquivo com timestamp de geração (§9).
META_FILENAME: Final = "meta.json"

#: Versão do formato. O reader recusa o que não conhece, em vez de montar
#: entidade errada em silêncio a partir de um snapshot de outra época.
FORMAT_VERSION: Final = 1


def dumps(payload: object) -> str:
    """JSON determinístico, com quebra de linha no fim.

    Sem o `\\n` final o arquivo não é um arquivo de texto POSIX e todo diff
    ganha um "\\ No newline at end of file" de ruído.
    """
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


# --------------------------------------------------------------------------- #
# Project
# --------------------------------------------------------------------------- #


def encode_project(entity: Project) -> Row:
    return {
        "id": str(entity.id),
        "name": entity.name,
        "description": entity.description,
        "color": None if entity.color is None else entity.color.value,
        "is_capacity_reserve": entity.is_capacity_reserve,
        "is_active": entity.is_active,
    }


def decode_project(row: Row) -> Project:
    return Project(
        id=UUID(row["id"]),
        name=row["name"],
        description=row["description"],
        color=Color.parse(row["color"]),
        is_capacity_reserve=row["is_capacity_reserve"],
        is_active=row["is_active"],
    )


# --------------------------------------------------------------------------- #
# Initiative
# --------------------------------------------------------------------------- #


def encode_initiative(entity: Initiative) -> Row:
    return {
        "id": str(entity.id),
        "project_id": str(entity.project_id),
        "name": entity.name,
        "layer": entity.layer,
        "description": entity.description,
        "priority": entity.priority.value,
        "estimated_sprints": entity.estimated_sprints,
        "status": entity.status.value,
        "entered_at": entity.entered_at.isoformat(),
    }


def decode_initiative(row: Row) -> Initiative:
    return Initiative(
        id=UUID(row["id"]),
        project_id=UUID(row["project_id"]),
        name=row["name"],
        entered_at=date.fromisoformat(row["entered_at"]),
        layer=row["layer"],
        description=row["description"],
        priority=Priority(row["priority"]),
        estimated_sprints=row["estimated_sprints"],
        status=InitiativeStatus(row["status"]),
    )


# --------------------------------------------------------------------------- #
# Member
# --------------------------------------------------------------------------- #


def encode_member(entity: Member) -> Row:
    return {
        "id": str(entity.id),
        "name": entity.name,
        "short_name": entity.short_name,
        "role": entity.role,
        "is_active": entity.is_active,
    }


def decode_member(row: Row) -> Member:
    return Member(
        id=UUID(row["id"]),
        name=row["name"],
        short_name=row["short_name"],
        role=row["role"],
        is_active=row["is_active"],
    )


# --------------------------------------------------------------------------- #
# Squad
# --------------------------------------------------------------------------- #


def encode_squad(entity: Squad) -> Row:
    representative = entity.representative_member_id
    return {
        "id": str(entity.id),
        "name": entity.name,
        "representative_member_id": (
            None if representative is None else str(representative)
        ),
        "is_active": entity.is_active,
    }


def decode_squad(row: Row) -> Squad:
    representative = row["representative_member_id"]
    return Squad(
        id=UUID(row["id"]),
        name=row["name"],
        representative_member_id=(
            None if representative is None else UUID(representative)
        ),
        is_active=row["is_active"],
    )


# --------------------------------------------------------------------------- #
# SquadMembership
# --------------------------------------------------------------------------- #


def encode_membership(entity: SquadMembership) -> Row:
    return {
        "id": str(entity.id),
        "squad_id": str(entity.squad_id),
        "member_id": str(entity.member_id),
        "sprint_id": str(entity.sprint_id),
    }


def decode_membership(row: Row) -> SquadMembership:
    return SquadMembership(
        id=UUID(row["id"]),
        squad_id=UUID(row["squad_id"]),
        member_id=UUID(row["member_id"]),
        sprint_id=UUID(row["sprint_id"]),
    )


# --------------------------------------------------------------------------- #
# Sprint
# --------------------------------------------------------------------------- #


def encode_sprint(entity: Sprint) -> Row:
    return {
        "id": str(entity.id),
        "number": entity.number,
        "start_date": entity.start_date.isoformat(),
        "end_date": entity.end_date.isoformat(),
    }


def decode_sprint(row: Row) -> Sprint:
    return Sprint(
        id=UUID(row["id"]),
        number=row["number"],
        start_date=date.fromisoformat(row["start_date"]),
        end_date=date.fromisoformat(row["end_date"]),
    )


# --------------------------------------------------------------------------- #
# Allocation
# --------------------------------------------------------------------------- #


def encode_allocation(entity: Allocation) -> Row:
    """As duas colunas do §6.7, e não o `Assignee`: é a forma da tabela, e é
    ela que faz `squad_id` e `member_id` continuarem legíveis no diff."""
    return {
        "id": str(entity.id),
        "initiative_id": str(entity.initiative_id),
        "sprint_id": str(entity.sprint_id),
        "squad_id": None if entity.squad_id is None else str(entity.squad_id),
        "member_id": None if entity.member_id is None else str(entity.member_id),
    }


def decode_allocation(row: Row) -> Allocation:
    squad_id = row["squad_id"]
    member_id = row["member_id"]
    return Allocation.create_from_ids(
        id=UUID(row["id"]),
        initiative_id=UUID(row["initiative_id"]),
        sprint_id=UUID(row["sprint_id"]),
        squad_id=None if squad_id is None else UUID(squad_id),
        member_id=None if member_id is None else UUID(member_id),
    )


# --------------------------------------------------------------------------- #
# MutedAlert
# --------------------------------------------------------------------------- #


def encode_muted_alert(entity: MutedAlert) -> Row:
    """`created_at` sai em ISO 8601 com o offset — a entidade já o normalizou
    para UTC, e é ele que a RNF4 preserva verbatim."""
    return {
        "id": str(entity.id),
        "alert_type": entity.alert_type.value,
        "fingerprint": entity.fingerprint,
        "reason": entity.reason,
        "created_at": entity.created_at.isoformat(),
    }


def decode_muted_alert(row: Row) -> MutedAlert:
    return MutedAlert(
        id=UUID(row["id"]),
        alert_type=AlertType(row["alert_type"]),
        fingerprint=row["fingerprint"],
        reason=row["reason"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


# --------------------------------------------------------------------------- #
# A tabela de arquivos
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class EntityFile[E]:
    """Um arquivo de entidade: nome, campo do bundle e o par de codecs.

    Ter isso como dado, e não como oito chamadas escritas à mão no writer e
    outras oito no reader, é o que garante que os dois lados falem dos mesmos
    arquivos.
    """

    filename: str
    field: str
    encode: Callable[[E], Row]
    decode: Callable[[Row], E]

    def rows(self, entities: Iterable[E]) -> list[Row]:
        """Ordenado por `id` (§9), e não por ordem de inserção."""
        return [self.encode(entity) for entity in _by_id(entities)]


def _by_id(entities: Iterable[Any]) -> list[Any]:
    return sorted(entities, key=lambda entity: str(entity.id))


#: Na ordem do §9, que é a ordem em que os arquivos aparecem na pasta.
ENTITY_FILES: Final[tuple[EntityFile[Any], ...]] = (
    EntityFile("projects.json", "projects", encode_project, decode_project),
    EntityFile("initiatives.json", "initiatives", encode_initiative, decode_initiative),
    EntityFile("members.json", "members", encode_member, decode_member),
    EntityFile("squads.json", "squads", encode_squad, decode_squad),
    EntityFile(
        "squad_memberships.json",
        "squad_memberships",
        encode_membership,
        decode_membership,
    ),
    EntityFile("sprints.json", "sprints", encode_sprint, decode_sprint),
    EntityFile("allocations.json", "allocations", encode_allocation, decode_allocation),
    EntityFile(
        "muted_alerts.json", "muted_alerts", encode_muted_alert, decode_muted_alert
    ),
)
