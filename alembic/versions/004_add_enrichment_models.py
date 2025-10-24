"""Add enrichment models and priority system

Revision ID: 004
Revises: 003
Create Date: 2025-10-23

Sprint 2: Adds support for tiered enrichment with HTTPx, Naabu, TLSx, and Katana.

Changes:
- Add enrichment tracking fields to assets table (priority, last_enriched_at, enrichment_status)
- Add HTTPx/TLSx enrichment fields to services table
- Create certificates table for TLS/SSL certificate data
- Create endpoints table for Katana web crawling results
- Add composite indexes for priority-based enrichment queries
- Backfill priority values for existing assets based on risk_score
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    """Apply enrichment model changes"""

    # ========================================
    # 1. Enhance assets table
    # ========================================

    # Add enrichment tracking columns
    op.add_column('assets', sa.Column('last_enriched_at', sa.DateTime(), nullable=True))
    op.add_column('assets', sa.Column('enrichment_status', sa.String(length=50), nullable=True, server_default='pending'))

    # Add priority system columns
    op.add_column('assets', sa.Column('priority', sa.String(length=20), nullable=True, server_default='normal'))
    op.add_column('assets', sa.Column('priority_updated_at', sa.DateTime(), nullable=True))
    op.add_column('assets', sa.Column('priority_auto_calculated', sa.Boolean(), nullable=True, server_default='true'))

    # Create composite indexes for efficient priority-based enrichment queries
    op.create_index('idx_asset_priority_enrichment', 'assets', ['tenant_id', 'priority', 'last_enriched_at'])
    op.create_index('idx_enrichment_status', 'assets', ['enrichment_status'])

    # ========================================
    # 2. Enhance services table
    # ========================================

    # HTTPx enrichment fields
    op.add_column('services', sa.Column('web_server', sa.String(length=200), nullable=True))
    op.add_column('services', sa.Column('http_technologies', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('services', sa.Column('http_headers', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('services', sa.Column('response_time_ms', sa.Integer(), nullable=True))
    op.add_column('services', sa.Column('content_length', sa.Integer(), nullable=True))
    op.add_column('services', sa.Column('redirect_url', sa.String(length=2048), nullable=True))
    op.add_column('services', sa.Column('screenshot_url', sa.String(length=500), nullable=True))

    # TLSx enrichment fields
    op.add_column('services', sa.Column('has_tls', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('services', sa.Column('tls_version', sa.String(length=50), nullable=True))

    # Enrichment tracking
    op.add_column('services', sa.Column('enriched_at', sa.DateTime(), nullable=True))
    op.add_column('services', sa.Column('enrichment_source', sa.String(length=50), nullable=True))

    # Create indexes for enrichment queries
    op.create_index('idx_enrichment_source', 'services', ['enrichment_source'])
    op.create_index('idx_has_tls', 'services', ['has_tls'])

    # ========================================
    # 3. Create certificates table
    # ========================================

    op.create_table('certificates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=False),

        # Certificate Identity
        sa.Column('subject_cn', sa.String(length=500), nullable=True),
        sa.Column('issuer', sa.String(length=500), nullable=True),
        sa.Column('serial_number', sa.String(length=255), nullable=True),

        # Validity
        sa.Column('not_before', sa.DateTime(), nullable=True),
        sa.Column('not_after', sa.DateTime(), nullable=True),
        sa.Column('is_expired', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('days_until_expiry', sa.Integer(), nullable=True),

        # Subject Alternative Names (SANs) - JSON array
        sa.Column('san_domains', postgresql.JSON(astext_type=sa.Text()), nullable=True),

        # Security Configuration
        sa.Column('signature_algorithm', sa.String(length=100), nullable=True),
        sa.Column('public_key_algorithm', sa.String(length=100), nullable=True),
        sa.Column('public_key_bits', sa.Integer(), nullable=True),

        # Cipher Suites - JSON array
        sa.Column('cipher_suites', postgresql.JSON(astext_type=sa.Text()), nullable=True),

        # Certificate Chain - JSON array
        sa.Column('chain', postgresql.JSON(astext_type=sa.Text()), nullable=True),

        # Vulnerabilities
        sa.Column('is_self_signed', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('is_wildcard', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('has_weak_signature', sa.Boolean(), nullable=True, server_default='false'),

        # Metadata
        sa.Column('first_seen', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('last_seen', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('raw_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),

        # Primary Key and Foreign Key
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
    )

    # Create indexes for certificates
    op.create_index('idx_asset_cert', 'certificates', ['asset_id'])
    op.create_index('idx_expiry', 'certificates', ['not_after'])
    op.create_index('idx_expired', 'certificates', ['is_expired'])
    op.create_index('idx_asset_serial', 'certificates', ['asset_id', 'serial_number'], unique=True)

    # ========================================
    # 4. Create endpoints table
    # ========================================

    op.create_table('endpoints',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=False),

        # Endpoint Identity
        sa.Column('url', sa.String(length=2048), nullable=False),
        sa.Column('path', sa.String(length=1024), nullable=True),
        sa.Column('method', sa.String(length=10), nullable=True, server_default='GET'),

        # Request Parameters - JSON objects
        sa.Column('query_params', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('body_params', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('headers', postgresql.JSON(astext_type=sa.Text()), nullable=True),

        # Response
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('content_type', sa.String(length=200), nullable=True),
        sa.Column('content_length', sa.Integer(), nullable=True),

        # Classification
        sa.Column('endpoint_type', sa.String(length=50), nullable=True),
        sa.Column('is_external', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('is_api', sa.Boolean(), nullable=True, server_default='false'),

        # Discovery Source
        sa.Column('source_url', sa.String(length=2048), nullable=True),
        sa.Column('depth', sa.Integer(), nullable=True, server_default='0'),

        # Metadata
        sa.Column('first_seen', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('last_seen', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('raw_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),

        # Primary Key and Foreign Key
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
    )

    # Create indexes for endpoints
    op.create_index('idx_asset_endpoint', 'endpoints', ['asset_id'])
    op.create_index('idx_endpoint_type', 'endpoints', ['endpoint_type'])
    op.create_index('idx_is_api', 'endpoints', ['is_api'])
    op.create_index('idx_asset_url', 'endpoints', ['asset_id', 'url', 'method'], unique=True)

    # ========================================
    # 5. Backfill priority values
    # ========================================

    # Automatically set priority based on existing risk_score
    # critical: risk_score >= 8.0
    # high: 6.0 <= risk_score < 8.0
    # normal: 3.0 <= risk_score < 6.0
    # low: risk_score < 3.0

    connection = op.get_bind()

    connection.execute(sa.text("""
        UPDATE assets
        SET priority = 'critical',
            priority_updated_at = CURRENT_TIMESTAMP,
            priority_auto_calculated = true
        WHERE risk_score >= 8.0
    """))

    connection.execute(sa.text("""
        UPDATE assets
        SET priority = 'high',
            priority_updated_at = CURRENT_TIMESTAMP,
            priority_auto_calculated = true
        WHERE risk_score >= 6.0 AND risk_score < 8.0
    """))

    connection.execute(sa.text("""
        UPDATE assets
        SET priority = 'normal',
            priority_updated_at = CURRENT_TIMESTAMP,
            priority_auto_calculated = true
        WHERE risk_score >= 3.0 AND risk_score < 6.0
    """))

    connection.execute(sa.text("""
        UPDATE assets
        SET priority = 'low',
            priority_updated_at = CURRENT_TIMESTAMP,
            priority_auto_calculated = true
        WHERE risk_score < 3.0
    """))

    print("✅ Migration 004 complete: Enrichment models and priority system added")


def downgrade():
    """Rollback enrichment model changes"""

    # Drop endpoints table and indexes
    op.drop_index('idx_asset_url', table_name='endpoints')
    op.drop_index('idx_is_api', table_name='endpoints')
    op.drop_index('idx_endpoint_type', table_name='endpoints')
    op.drop_index('idx_asset_endpoint', table_name='endpoints')
    op.drop_table('endpoints')

    # Drop certificates table and indexes
    op.drop_index('idx_asset_serial', table_name='certificates')
    op.drop_index('idx_expired', table_name='certificates')
    op.drop_index('idx_expiry', table_name='certificates')
    op.drop_index('idx_asset_cert', table_name='certificates')
    op.drop_table('certificates')

    # Drop services enrichment indexes
    op.drop_index('idx_has_tls', table_name='services')
    op.drop_index('idx_enrichment_source', table_name='services')

    # Remove services enrichment columns
    op.drop_column('services', 'enrichment_source')
    op.drop_column('services', 'enriched_at')
    op.drop_column('services', 'tls_version')
    op.drop_column('services', 'has_tls')
    op.drop_column('services', 'screenshot_url')
    op.drop_column('services', 'redirect_url')
    op.drop_column('services', 'content_length')
    op.drop_column('services', 'response_time_ms')
    op.drop_column('services', 'http_headers')
    op.drop_column('services', 'http_technologies')
    op.drop_column('services', 'web_server')

    # Drop assets enrichment indexes
    op.drop_index('idx_enrichment_status', table_name='assets')
    op.drop_index('idx_asset_priority_enrichment', table_name='assets')

    # Remove assets enrichment columns
    op.drop_column('assets', 'priority_auto_calculated')
    op.drop_column('assets', 'priority_updated_at')
    op.drop_column('assets', 'priority')
    op.drop_column('assets', 'enrichment_status')
    op.drop_column('assets', 'last_enriched_at')

    print("✅ Migration 004 rolled back: Enrichment models removed")
