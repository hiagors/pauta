"""Tradução modelo <-> entidade.

Três funções por entidade, e o nome diz o sentido:

- `x_to_entity(model)` — reidrata a entidade a partir da linha;
- `x_to_model(entity)` — monta a linha nova, para o `INSERT`;
- `x_apply(model, entity)` — copia a entidade sobre a linha existente, para o
  `UPDATE`. Nunca toca no `id`, que é a identidade da linha.

A reidratação passa pelo **construtor da dataclass**, não por
`Entity.create(...)`: `create` é para entidade nova (gera `id`, lê `entered_at`
do `Clock`), e o que vem do banco já tem os dois. As invariantes do
`__post_init__` valem igual nos dois caminhos, o que é justamente o que se
quer: linha inválida no banco vira erro na leitura, não estado impossível
circulando pelo sistema.

Nenhuma função devolve objeto compartilhado com o modelo: a entidade é sempre
nova, com valores primitivos ou value objects imutáveis. É o que faz um
`update()` esquecido no use case falhar no teste em vez de "funcionar" porque a
mutação vazou para a sessão.
"""

from datetime import UTC

from app.adapters.outbound.persistence.models import (
    AllocationModel,
    InitiativeModel,
    MemberModel,
    MutedAlertModel,
    ProjectModel,
    SprintModel,
    SquadMembershipModel,
    SquadModel,
)
from app.domain.entities.allocation import Allocation
from app.domain.entities.initiative import Initiative
from app.domain.entities.member import Member
from app.domain.entities.muted_alert import MutedAlert
from app.domain.entities.project import Project
from app.domain.entities.sprint import Sprint
from app.domain.entities.squad import Squad
from app.domain.entities.squad_membership import SquadMembership
from app.domain.value_objects.color import Color

# --------------------------------------------------------------------------- #
# Project
# --------------------------------------------------------------------------- #


def project_to_entity(model: ProjectModel) -> Project:
    return Project(
        id=model.id,
        name=model.name,
        description=model.description,
        color=Color.parse(model.color),
        is_capacity_reserve=model.is_capacity_reserve,
        is_active=model.is_active,
    )


def project_to_model(entity: Project) -> ProjectModel:
    return ProjectModel(
        id=entity.id,
        name=entity.name,
        description=entity.description,
        color=None if entity.color is None else entity.color.value,
        is_capacity_reserve=entity.is_capacity_reserve,
        is_active=entity.is_active,
    )


def project_apply(model: ProjectModel, entity: Project) -> None:
    model.name = entity.name
    model.description = entity.description
    model.color = None if entity.color is None else entity.color.value
    model.is_capacity_reserve = entity.is_capacity_reserve
    model.is_active = entity.is_active


# --------------------------------------------------------------------------- #
# Initiative
# --------------------------------------------------------------------------- #


def initiative_to_entity(model: InitiativeModel) -> Initiative:
    return Initiative(
        id=model.id,
        project_id=model.project_id,
        name=model.name,
        entered_at=model.entered_at,
        layer=model.layer,
        description=model.description,
        priority=model.priority,
        estimated_sprints=model.estimated_sprints,
        status=model.status,
    )


def initiative_to_model(entity: Initiative) -> InitiativeModel:
    return InitiativeModel(
        id=entity.id,
        project_id=entity.project_id,
        name=entity.name,
        layer=entity.layer,
        description=entity.description,
        priority=entity.priority,
        estimated_sprints=entity.estimated_sprints,
        status=entity.status,
        entered_at=entity.entered_at,
    )


def initiative_apply(model: InitiativeModel, entity: Initiative) -> None:
    """`project_id` entra: mover iniciativa de projeto não está no §8, mas
    escrever o campo é mais honesto que ignorá-lo em silêncio."""
    model.project_id = entity.project_id
    model.name = entity.name
    model.layer = entity.layer
    model.description = entity.description
    model.priority = entity.priority
    model.estimated_sprints = entity.estimated_sprints
    model.status = entity.status
    model.entered_at = entity.entered_at


# --------------------------------------------------------------------------- #
# Member
# --------------------------------------------------------------------------- #


def member_to_entity(model: MemberModel) -> Member:
    return Member(
        id=model.id,
        name=model.name,
        short_name=model.short_name,
        role=model.role,
        is_active=model.is_active,
    )


def member_to_model(entity: Member) -> MemberModel:
    return MemberModel(
        id=entity.id,
        name=entity.name,
        short_name=entity.short_name,
        role=entity.role,
        is_active=entity.is_active,
    )


def member_apply(model: MemberModel, entity: Member) -> None:
    model.name = entity.name
    model.short_name = entity.short_name
    model.role = entity.role
    model.is_active = entity.is_active


# --------------------------------------------------------------------------- #
# Squad
# --------------------------------------------------------------------------- #


def squad_to_entity(model: SquadModel) -> Squad:
    return Squad(
        id=model.id,
        name=model.name,
        representative_member_id=model.representative_member_id,
        is_active=model.is_active,
    )


def squad_to_model(entity: Squad) -> SquadModel:
    return SquadModel(
        id=entity.id,
        name=entity.name,
        representative_member_id=entity.representative_member_id,
        is_active=entity.is_active,
    )


def squad_apply(model: SquadModel, entity: Squad) -> None:
    model.name = entity.name
    model.representative_member_id = entity.representative_member_id
    model.is_active = entity.is_active


# --------------------------------------------------------------------------- #
# SquadMembership
# --------------------------------------------------------------------------- #


def membership_to_entity(model: SquadMembershipModel) -> SquadMembership:
    return SquadMembership(
        id=model.id,
        squad_id=model.squad_id,
        member_id=model.member_id,
        sprint_id=model.sprint_id,
    )


def membership_to_model(entity: SquadMembership) -> SquadMembershipModel:
    return SquadMembershipModel(
        id=entity.id,
        squad_id=entity.squad_id,
        member_id=entity.member_id,
        sprint_id=entity.sprint_id,
    )


# --------------------------------------------------------------------------- #
# Sprint
# --------------------------------------------------------------------------- #


def sprint_to_entity(model: SprintModel) -> Sprint:
    return Sprint(
        id=model.id,
        number=model.number,
        start_date=model.start_date,
        end_date=model.end_date,
    )


def sprint_to_model(entity: Sprint) -> SprintModel:
    return SprintModel(
        id=entity.id,
        number=entity.number,
        start_date=entity.start_date,
        end_date=entity.end_date,
    )


# --------------------------------------------------------------------------- #
# Allocation
# --------------------------------------------------------------------------- #


def allocation_to_entity(model: AllocationModel) -> Allocation:
    """O par de colunas nulas vira um `Assignee`, que não representa
    "nenhum" nem "os dois" (§6.7)."""
    return Allocation.create_from_ids(
        id=model.id,
        initiative_id=model.initiative_id,
        sprint_id=model.sprint_id,
        squad_id=model.squad_id,
        member_id=model.member_id,
    )


def allocation_to_model(entity: Allocation) -> AllocationModel:
    return AllocationModel(
        id=entity.id,
        initiative_id=entity.initiative_id,
        sprint_id=entity.sprint_id,
        squad_id=entity.squad_id,
        member_id=entity.member_id,
    )


# --------------------------------------------------------------------------- #
# MutedAlert
# --------------------------------------------------------------------------- #


def muted_alert_to_entity(model: MutedAlertModel) -> MutedAlert:
    """Devolve o `tzinfo` que o SQLite não guarda.

    A entidade só aceita `datetime` com timezone (`InvalidTimestamp`) e grava
    sempre já convertido para UTC, então reanexar `UTC` na leitura é exato —
    não é um palpite sobre o fuso de quem escreveu.
    """
    created_at = model.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return MutedAlert(
        id=model.id,
        alert_type=model.alert_type,
        fingerprint=model.fingerprint,
        reason=model.reason,
        created_at=created_at,
    )


def muted_alert_to_model(entity: MutedAlert) -> MutedAlertModel:
    return MutedAlertModel(
        id=entity.id,
        alert_type=entity.alert_type,
        fingerprint=entity.fingerprint,
        reason=entity.reason,
        created_at=entity.created_at,
    )
