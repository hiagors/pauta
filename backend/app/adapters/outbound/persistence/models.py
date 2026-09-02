"""Mapeamento SQLAlchemy das tabelas (§9).

Explícito de propósito: uma classe por tabela, uma coluna por campo do §6, sem
`relationship` nenhuma. Navegar entre entidades é trabalho do use case, com as
portas; aqui só existe a linha e o que a mantém válida.

As invariantes que o domínio já valida aparecem **também** como constraint:
"exatamente um responsável" (§6.7), unicidade `(initiative_id, sprint_id)`
(RN8), `(squad_id, member_id, sprint_id)` (§6.5), `end_date > start_date`
(§6.6). Duplicar não é desconfiança do domínio — é o que impede que um banco
editado à mão, ou uma restauração de snapshot antigo, entre num estado que o
domínio considera impossível de representar.

Nenhuma tabela guarda dado derivado: alerta é calculado sob demanda (§7.3) e
`is_capacity_reserve` mora só no projeto (§6.2).
"""

from datetime import date, datetime
from typing import Final
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.value_objects.alert import AlertType
from app.domain.value_objects.initiative_status import InitiativeStatus
from app.domain.value_objects.priority import Priority

#: Nomes previsíveis para índices e constraints. Sem isso o SQLite ganha
#: constraint anônima, e o `render_as_batch` do Alembic (que recria a tabela
#: para alterá-la) não tem como referenciá-la na migration seguinte.
NAMING_CONVENTION: Final = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


#: Os enums do domínio que viram coluna.
type StoredEnum = type[InitiativeStatus | Priority | AlertType]


def _enum(python_type: StoredEnum, name: str) -> Enum:
    """Enum como VARCHAR, guardando o **valor** e não o nome.

    `native_enum=False` porque o SQLite não tem tipo enum, e
    `values_callable` porque o default do SQLAlchemy grava `Priority.HIGH.name`
    — hoje idêntico ao valor, mas nada garante que continue.

    O `CHECK` que restringe os valores é `_enum_check`, declarado à parte: o
    `create_constraint=True` do próprio `Enum` cria a constraint no DDL sem
    deixá-la no metadata como objeto nomeado, e o `alembic check` passa a
    acusar, em toda rodada, a remoção de uma constraint que está no banco.
    """
    return Enum(
        python_type,
        name=name,
        native_enum=False,
        create_constraint=False,
        validate_strings=True,
        values_callable=lambda enum: [member.value for member in enum],
    )


def _enum_check(column: str, python_type: StoredEnum, name: str) -> CheckConstraint:
    """`CHECK col IN (...)`, com a lista tirada do próprio enum.

    Escrever os valores à mão aqui seria uma segunda fonte da verdade, que um
    valor novo no domínio deixaria desatualizada em silêncio.
    """
    values = ", ".join(f"'{member.value}'" for member in python_type)
    return CheckConstraint(f"{column} IN ({values})", name=name)


class ProjectModel(Base):
    """§6.1 — agrupador. Sem status, sem prioridade, sem alocação."""

    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    #: Nulo usa `DEFAULT_PROJECT_COLOR` (§6.1); a coluna não repete o default.
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    is_capacity_reserve: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)


class InitiativeModel(Base):
    """§6.2 — a unidade de trabalho e a linha do Gantt."""

    __tablename__ = "initiatives"
    __table_args__ = (
        UniqueConstraint("project_id", "name"),
        CheckConstraint(
            "estimated_sprints IS NULL OR estimated_sprints > 0",
            name="estimated_sprints_positive",
        ),
        _enum_check("priority", Priority, "priority_known"),
        _enum_check("status", InitiativeStatus, "status_known"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    #: `ondelete` nenhum de propósito: quem apaga as iniciativas do projeto é o
    #: use case, depois de checar que nenhuma tem alocação (RN-I2, §8).
    project_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("projects.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    layer: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[Priority] = mapped_column(
        _enum(Priority, "priority"), nullable=False
    )
    estimated_sprints: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[InitiativeStatus] = mapped_column(
        _enum(InitiativeStatus, "initiative_status"), nullable=False
    )
    entered_at: Mapped[date] = mapped_column(Date, nullable=False)


class MemberModel(Base):
    """§6.4 — pessoa. Nunca é apagada: `is_active = false`."""

    __tablename__ = "members"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    short_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)


class SquadModel(Base):
    """§6.5 — agrupamento com prazo. Sem lista de membros: ver `squad_memberships`."""

    __tablename__ = "squads"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    #: RN-S1: basta referenciar um membro existente. Que esteja ativo é regra
    #: do use case, e a composição da squad não é checada aqui de propósito.
    representative_member_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("members.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)


class SquadMembershipModel(Base):
    """§6.5 — quem está na squad em cada sprint.

    Uma linha por (squad, membro, sprint), no mesmo idioma de `Allocation`.
    """

    __tablename__ = "squad_memberships"
    __table_args__ = (
        UniqueConstraint("squad_id", "member_id", "sprint_id"),
        Index("ix_squad_memberships_member_id", "member_id"),
        Index("ix_squad_memberships_sprint_id", "sprint_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    squad_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("squads.id"), nullable=False
    )
    member_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("members.id"), nullable=False
    )
    sprint_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("sprints.id"), nullable=False
    )


class SprintModel(Base):
    """§6.6 — marcação de tempo. Nunca é excluída (D13), por isso não há `delete`."""

    __tablename__ = "sprints"
    __table_args__ = (
        CheckConstraint("number >= 1", name="number_positive"),
        CheckConstraint("end_date > start_date", name="dates_ordered"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)


class AllocationModel(Base):
    """§6.7 — uma linha por sprint ocupada, com um responsável só."""

    __tablename__ = "allocations"
    __table_args__ = (
        #: RN8: uma iniciativa tem **um** responsável por sprint.
        UniqueConstraint("initiative_id", "sprint_id"),
        #: §6.7: exatamente um de squad_id / member_id. O `<>` sobre dois
        #: `IS NULL` compara 0 com 1 — é o "ou exclusivo" do SQLite.
        CheckConstraint(
            "(squad_id IS NULL) <> (member_id IS NULL)",
            name="exactly_one_assignee",
        ),
        Index("ix_allocations_sprint_id", "sprint_id"),
        Index("ix_allocations_squad_id", "squad_id"),
        Index("ix_allocations_member_id", "member_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    initiative_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("initiatives.id"), nullable=False
    )
    sprint_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("sprints.id"), nullable=False
    )
    squad_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("squads.id"), nullable=True
    )
    member_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("members.id"), nullable=True
    )


class MutedAlertModel(Base):
    """§6.9 — o único resíduo persistido do §7.3: o silenciamento.

    `created_at` é `DateTime(timezone=True)`, mas o SQLite não guarda offset:
    grava-se o instante já normalizado em UTC pela entidade e o mapper devolve
    o `tzinfo` na leitura. Ver `mappers.muted_alert_to_entity`.
    """

    __tablename__ = "muted_alerts"
    __table_args__ = (_enum_check("alert_type", AlertType, "alert_type_known"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    alert_type: Mapped[AlertType] = mapped_column(
        _enum(AlertType, "alert_type"), nullable=False
    )
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ExternalRefModel(Base):
    """§6.10 — pavimento da v2. Tabela **vazia** na v1.

    Sem porta, sem repositório, sem endpoint e sem UI: existe só para que um
    relatório importado no futuro aponte para iniciativa ou sprint sem
    migração. `entity_id` é polimórfico e por isso não tem chave estrangeira.
    """

    __tablename__ = "external_refs"
    __table_args__ = (
        Index("ix_external_refs_entity_type_entity_id", "entity_type", "entity_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    system: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
