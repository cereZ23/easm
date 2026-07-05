"""make idx_finding_dedup a UNIQUE index so finding upserts work

FindingRepository.bulk_upsert_findings uses
``ON CONFLICT (asset_id, template_id, matcher_name)``, which requires a UNIQUE
index on exactly those columns. Migration 006 (and the model) created it as a
plain, non-unique index, so every finding insert failed with:
  "there is no unique or exclusion constraint matching the ON CONFLICT
   specification"
=> nuclei found issues but NONE were ever persisted (silent 0 findings).

matcher_name is nullable and many findings share (asset_id, template_id, NULL);
Postgres treats NULLs as distinct by default, which would defeat dedup, so the
unique index is created with NULLS NOT DISTINCT (Postgres 15+).

Revision ID: 007
Revises: 006
"""
from alembic import op


revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade():
    # Replace the non-unique index with a UNIQUE one (NULLS NOT DISTINCT so
    # findings with a null matcher_name still deduplicate).
    op.drop_index('idx_finding_dedup', table_name='findings')
    op.execute(
        "CREATE UNIQUE INDEX idx_finding_dedup "
        "ON findings (asset_id, template_id, matcher_name) NULLS NOT DISTINCT"
    )


def downgrade():
    op.drop_index('idx_finding_dedup', table_name='findings')
    op.create_index(
        'idx_finding_dedup', 'findings',
        ['asset_id', 'template_id', 'matcher_name'], unique=False,
    )
