"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create tenants table
    op.create_table('tenants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('contact_policy', sa.Text(), nullable=True),
        sa.Column('api_keys', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )

    # Create assets table
    op.create_table('assets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.Enum('DOMAIN', 'SUBDOMAIN', 'IP', 'URL', 'SERVICE', name='assettype'), nullable=False),
        sa.Column('identifier', sa.String(length=500), nullable=False),
        sa.Column('first_seen', sa.DateTime(), nullable=True),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.Column('risk_score', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('raw_metadata', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_identifier', 'assets', ['identifier'], unique=False)
    op.create_index('idx_tenant_identifier', 'assets', ['tenant_id', 'identifier'], unique=False)
    op.create_index('idx_tenant_type', 'assets', ['tenant_id', 'type'], unique=False)
    # Unique constraint for bulk upsert ON CONFLICT
    op.create_index('idx_unique_asset', 'assets', ['tenant_id', 'identifier', 'type'], unique=True)

    # Create seeds table
    op.create_table('seeds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=True),
        sa.Column('value', sa.String(length=500), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_tenant_enabled', 'seeds', ['tenant_id', 'enabled'], unique=False)

    # Create events table
    op.create_table('events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.Enum('NEW_ASSET', 'OPEN_PORT', 'NEW_CERT', 'NEW_PATH', 'TECH_CHANGE', name='eventkind'), nullable=False),
        sa.Column('payload', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_created_at', 'events', ['created_at'], unique=False)
    op.create_index('idx_kind_created', 'events', ['kind', 'created_at'], unique=False)

    # Create findings table
    op.create_table('findings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.Column('template_id', sa.String(length=255), nullable=True),
        sa.Column('name', sa.String(length=500), nullable=False),
        sa.Column('severity', sa.Enum('INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='findingseverity'), nullable=False),
        sa.Column('cvss_score', sa.Float(), nullable=True),
        sa.Column('cve_id', sa.String(length=50), nullable=True),
        sa.Column('evidence', sa.Text(), nullable=True),
        sa.Column('first_seen', sa.DateTime(), nullable=True),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.Column('status', sa.Enum('OPEN', 'SUPPRESSED', 'FIXED', name='findingstatus'), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_asset_severity', 'findings', ['asset_id', 'severity'], unique=False)
    op.create_index('idx_severity_status', 'findings', ['severity', 'status'], unique=False)
    op.create_index('idx_status', 'findings', ['status'], unique=False)

    # Create services table
    op.create_table('services',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('port', sa.Integer(), nullable=True),
        sa.Column('protocol', sa.String(length=50), nullable=True),
        sa.Column('product', sa.String(length=255), nullable=True),
        sa.Column('version', sa.String(length=100), nullable=True),
        sa.Column('tls_fingerprint', sa.String(length=255), nullable=True),
        sa.Column('http_title', sa.String(length=500), nullable=True),
        sa.Column('http_status', sa.Integer(), nullable=True),
        sa.Column('technologies', sa.Text(), nullable=True),
        sa.Column('first_seen', sa.DateTime(), nullable=True),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_asset_port', 'services', ['asset_id', 'port'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_asset_port', table_name='services')
    op.drop_table('services')
    op.drop_index('idx_status', table_name='findings')
    op.drop_index('idx_severity_status', table_name='findings')
    op.drop_index('idx_asset_severity', table_name='findings')
    op.drop_table('findings')
    op.drop_index('idx_kind_created', table_name='events')
    op.drop_index('idx_created_at', table_name='events')
    op.drop_table('events')
    op.drop_index('idx_tenant_enabled', table_name='seeds')
    op.drop_table('seeds')
    op.drop_index('idx_unique_asset', table_name='assets')
    op.drop_index('idx_tenant_type', table_name='assets')
    op.drop_index('idx_tenant_identifier', table_name='assets')
    op.drop_index('idx_identifier', table_name='assets')
    op.drop_table('assets')
    op.drop_table('tenants')
