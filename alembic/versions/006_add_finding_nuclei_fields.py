"""add nuclei metadata fields to findings

Adds the Sprint 3 Nuclei-integration columns that exist on the Finding model
but were never migrated onto the findings table:
  - matched_at   (URL where the finding was discovered)
  - host         (hostname extracted from matched_at)
  - matcher_name (Nuclei matcher name, used for deduplication)

Also adds the deduplication index (asset_id, template_id, matcher_name).

Without these, run_nuclei_scan fails with
"column findings.matched_at does not exist".

Revision ID: 006
Revises: 005
"""
from alembic import op
import sqlalchemy as sa


revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    # Add columns only if they are not already present (idempotent-friendly)
    with op.batch_alter_table('findings') as batch_op:
        batch_op.add_column(sa.Column('matched_at', sa.String(length=2048), nullable=True))
        batch_op.add_column(sa.Column('host', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('matcher_name', sa.String(length=255), nullable=True))

    op.create_index(
        'idx_finding_dedup',
        'findings',
        ['asset_id', 'template_id', 'matcher_name'],
        unique=False,
    )


def downgrade():
    op.drop_index('idx_finding_dedup', table_name='findings')
    with op.batch_alter_table('findings') as batch_op:
        batch_op.drop_column('matcher_name')
        batch_op.drop_column('host')
        batch_op.drop_column('matched_at')
