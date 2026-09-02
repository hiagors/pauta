"""Cria o schema inicial

Todas as tabelas do §6, incluindo `external_refs` — vazia na v1, que existe só
para que a v2 possa apontar para iniciativa ou sprint sem migração (§6.10, §12).

As constraints não são decoração: são as invariantes do domínio escritas
também no banco, para que um arquivo editado à mão ou uma restauração de
snapshot antigo não produza estado que o domínio considera impossível de
representar — "exatamente um responsável" (§6.7), `(initiative_id, sprint_id)`
único (RN8), `(squad_id, member_id, sprint_id)` único (§6.5),
`end_date > start_date` (§6.6).

O `downgrade` derruba o schema inteiro: é a primeira revisão, e "sobe e desce"
é o critério de aceite da Fase 3.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table('external_refs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('entity_type', sa.Text(), nullable=False),
    sa.Column('entity_id', sa.Uuid(), nullable=False),
    sa.Column('system', sa.Text(), nullable=False),
    sa.Column('external_id', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_external_refs'))
    )
    with op.batch_alter_table('external_refs', schema=None) as batch_op:
        batch_op.create_index('ix_external_refs_entity_type_entity_id', ['entity_type', 'entity_id'], unique=False)

    op.create_table('members',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('short_name', sa.Text(), nullable=False),
    sa.Column('role', sa.Text(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_members'))
    )
    op.create_table('muted_alerts',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('alert_type', sa.Enum('SQUAD_OVERLOADED', 'MEMBER_CONFLICT', 'MEMBER_IDLE', 'EMPTY_SQUAD', name='alert_type', native_enum=False), nullable=False),
    sa.Column('fingerprint', sa.String(length=64), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("alert_type IN ('SQUAD_OVERLOADED', 'MEMBER_CONFLICT', 'MEMBER_IDLE', 'EMPTY_SQUAD')", name=op.f('ck_muted_alerts_alert_type_known')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_muted_alerts')),
    sa.UniqueConstraint('fingerprint', name=op.f('uq_muted_alerts_fingerprint'))
    )
    op.create_table('projects',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('color', sa.String(length=7), nullable=True),
    sa.Column('is_capacity_reserve', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_projects')),
    sa.UniqueConstraint('name', name=op.f('uq_projects_name'))
    )
    op.create_table('sprints',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=False),
    sa.CheckConstraint('end_date > start_date', name=op.f('ck_sprints_dates_ordered')),
    sa.CheckConstraint('number >= 1', name=op.f('ck_sprints_number_positive')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sprints')),
    sa.UniqueConstraint('number', name=op.f('uq_sprints_number'))
    )
    op.create_table('initiatives',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('project_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('layer', sa.Text(), nullable=True),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('priority', sa.Enum('HIGH', 'MEDIUM', 'LOW', name='priority', native_enum=False), nullable=False),
    sa.Column('estimated_sprints', sa.Integer(), nullable=True),
    sa.Column('status', sa.Enum('BACKLOG', 'PLANNED', 'IN_PROGRESS', 'DEPRIORITIZED', 'DONE', 'CANCELLED', name='initiative_status', native_enum=False), nullable=False),
    sa.Column('entered_at', sa.Date(), nullable=False),
    sa.CheckConstraint("priority IN ('HIGH', 'MEDIUM', 'LOW')", name=op.f('ck_initiatives_priority_known')),
    sa.CheckConstraint("status IN ('BACKLOG', 'PLANNED', 'IN_PROGRESS', 'DEPRIORITIZED', 'DONE', 'CANCELLED')", name=op.f('ck_initiatives_status_known')),
    sa.CheckConstraint('estimated_sprints IS NULL OR estimated_sprints > 0', name=op.f('ck_initiatives_estimated_sprints_positive')),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_initiatives_project_id_projects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_initiatives')),
    sa.UniqueConstraint('project_id', 'name', name=op.f('uq_initiatives_project_id_name'))
    )
    op.create_table('squads',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('representative_member_id', sa.Uuid(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['representative_member_id'], ['members.id'], name=op.f('fk_squads_representative_member_id_members')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_squads')),
    sa.UniqueConstraint('name', name=op.f('uq_squads_name'))
    )
    op.create_table('allocations',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('initiative_id', sa.Uuid(), nullable=False),
    sa.Column('sprint_id', sa.Uuid(), nullable=False),
    sa.Column('squad_id', sa.Uuid(), nullable=True),
    sa.Column('member_id', sa.Uuid(), nullable=True),
    sa.CheckConstraint('(squad_id IS NULL) <> (member_id IS NULL)', name=op.f('ck_allocations_exactly_one_assignee')),
    sa.ForeignKeyConstraint(['initiative_id'], ['initiatives.id'], name=op.f('fk_allocations_initiative_id_initiatives')),
    sa.ForeignKeyConstraint(['member_id'], ['members.id'], name=op.f('fk_allocations_member_id_members')),
    sa.ForeignKeyConstraint(['sprint_id'], ['sprints.id'], name=op.f('fk_allocations_sprint_id_sprints')),
    sa.ForeignKeyConstraint(['squad_id'], ['squads.id'], name=op.f('fk_allocations_squad_id_squads')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_allocations')),
    sa.UniqueConstraint('initiative_id', 'sprint_id', name=op.f('uq_allocations_initiative_id_sprint_id'))
    )
    with op.batch_alter_table('allocations', schema=None) as batch_op:
        batch_op.create_index('ix_allocations_member_id', ['member_id'], unique=False)
        batch_op.create_index('ix_allocations_sprint_id', ['sprint_id'], unique=False)
        batch_op.create_index('ix_allocations_squad_id', ['squad_id'], unique=False)

    op.create_table('squad_memberships',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('squad_id', sa.Uuid(), nullable=False),
    sa.Column('member_id', sa.Uuid(), nullable=False),
    sa.Column('sprint_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['member_id'], ['members.id'], name=op.f('fk_squad_memberships_member_id_members')),
    sa.ForeignKeyConstraint(['sprint_id'], ['sprints.id'], name=op.f('fk_squad_memberships_sprint_id_sprints')),
    sa.ForeignKeyConstraint(['squad_id'], ['squads.id'], name=op.f('fk_squad_memberships_squad_id_squads')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_squad_memberships')),
    sa.UniqueConstraint('squad_id', 'member_id', 'sprint_id', name=op.f('uq_squad_memberships_squad_id_member_id_sprint_id'))
    )
    with op.batch_alter_table('squad_memberships', schema=None) as batch_op:
        batch_op.create_index('ix_squad_memberships_member_id', ['member_id'], unique=False)
        batch_op.create_index('ix_squad_memberships_sprint_id', ['sprint_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('squad_memberships', schema=None) as batch_op:
        batch_op.drop_index('ix_squad_memberships_sprint_id')
        batch_op.drop_index('ix_squad_memberships_member_id')

    op.drop_table('squad_memberships')
    with op.batch_alter_table('allocations', schema=None) as batch_op:
        batch_op.drop_index('ix_allocations_squad_id')
        batch_op.drop_index('ix_allocations_sprint_id')
        batch_op.drop_index('ix_allocations_member_id')

    op.drop_table('allocations')
    op.drop_table('squads')
    op.drop_table('initiatives')
    op.drop_table('sprints')
    op.drop_table('projects')
    op.drop_table('muted_alerts')
    op.drop_table('members')
    with op.batch_alter_table('external_refs', schema=None) as batch_op:
        batch_op.drop_index('ix_external_refs_entity_type_entity_id')

    op.drop_table('external_refs')
