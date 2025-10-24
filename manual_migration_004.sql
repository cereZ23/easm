-- Migration 004: Add enrichment models and priority system
-- Manual execution script (in case alembic has connection issues)

BEGIN;

-- ========================================
-- 1. Enhance assets table
-- ========================================

-- Add enrichment tracking columns
ALTER TABLE assets ADD COLUMN IF NOT EXISTS last_enriched_at TIMESTAMP;
ALTER TABLE assets ADD COLUMN IF NOT EXISTS enrichment_status VARCHAR(50) DEFAULT 'pending';

-- Add priority system columns
ALTER TABLE assets ADD COLUMN IF NOT EXISTS priority VARCHAR(20) DEFAULT 'normal';
ALTER TABLE assets ADD COLUMN IF NOT EXISTS priority_updated_at TIMESTAMP;
ALTER TABLE assets ADD COLUMN IF NOT EXISTS priority_auto_calculated BOOLEAN DEFAULT true;

-- Create composite indexes for efficient priority-based enrichment queries
CREATE INDEX IF NOT EXISTS idx_asset_priority_enrichment ON assets(tenant_id, priority, last_enriched_at);
CREATE INDEX IF NOT EXISTS idx_enrichment_status ON assets(enrichment_status);

-- ========================================
-- 2. Enhance services table
-- ========================================

-- HTTPx enrichment fields
ALTER TABLE services ADD COLUMN IF NOT EXISTS web_server VARCHAR(200);
ALTER TABLE services ADD COLUMN IF NOT EXISTS http_technologies JSONB;
ALTER TABLE services ADD COLUMN IF NOT EXISTS http_headers JSONB;
ALTER TABLE services ADD COLUMN IF NOT EXISTS response_time_ms INTEGER;
ALTER TABLE services ADD COLUMN IF NOT EXISTS content_length INTEGER;
ALTER TABLE services ADD COLUMN IF NOT EXISTS redirect_url VARCHAR(2048);
ALTER TABLE services ADD COLUMN IF NOT EXISTS screenshot_url VARCHAR(500);

-- TLSx enrichment fields
ALTER TABLE services ADD COLUMN IF NOT EXISTS has_tls BOOLEAN DEFAULT false;
ALTER TABLE services ADD COLUMN IF NOT EXISTS tls_version VARCHAR(50);

-- Enrichment tracking
ALTER TABLE services ADD COLUMN IF NOT EXISTS enriched_at TIMESTAMP;
ALTER TABLE services ADD COLUMN IF NOT EXISTS enrichment_source VARCHAR(50);

-- Create indexes for enrichment queries
CREATE INDEX IF NOT EXISTS idx_enrichment_source ON services(enrichment_source);
CREATE INDEX IF NOT EXISTS idx_has_tls ON services(has_tls);

-- ========================================
-- 3. Create certificates table
-- ========================================

CREATE TABLE IF NOT EXISTS certificates (
    id SERIAL PRIMARY KEY,
    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,

    -- Certificate Identity
    subject_cn VARCHAR(500),
    issuer VARCHAR(500),
    serial_number VARCHAR(255),

    -- Validity
    not_before TIMESTAMP,
    not_after TIMESTAMP,
    is_expired BOOLEAN DEFAULT false,
    days_until_expiry INTEGER,

    -- Subject Alternative Names (SANs) - JSON array
    san_domains JSONB,

    -- Security Configuration
    signature_algorithm VARCHAR(100),
    public_key_algorithm VARCHAR(100),
    public_key_bits INTEGER,

    -- Cipher Suites - JSON array
    cipher_suites JSONB,

    -- Certificate Chain - JSON array
    chain JSONB,

    -- Vulnerabilities
    is_self_signed BOOLEAN DEFAULT false,
    is_wildcard BOOLEAN DEFAULT false,
    has_weak_signature BOOLEAN DEFAULT false,

    -- Metadata
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_data JSONB
);

-- Create indexes for certificates
CREATE INDEX IF NOT EXISTS idx_asset_cert ON certificates(asset_id);
CREATE INDEX IF NOT EXISTS idx_expiry ON certificates(not_after);
CREATE INDEX IF NOT EXISTS idx_expired ON certificates(is_expired);
CREATE UNIQUE INDEX IF NOT EXISTS idx_asset_serial ON certificates(asset_id, serial_number);

-- ========================================
-- 4. Create endpoints table
-- ========================================

CREATE TABLE IF NOT EXISTS endpoints (
    id SERIAL PRIMARY KEY,
    asset_id INTEGER NOT NULL REFERENCES assets(id) ON DELETE CASCADE,

    -- Endpoint Identity
    url VARCHAR(2048) NOT NULL,
    path VARCHAR(1024),
    method VARCHAR(10) DEFAULT 'GET',

    -- Request Parameters - JSON objects
    query_params JSONB,
    body_params JSONB,
    headers JSONB,

    -- Response
    status_code INTEGER,
    content_type VARCHAR(200),
    content_length INTEGER,

    -- Classification
    endpoint_type VARCHAR(50),
    is_external BOOLEAN DEFAULT false,
    is_api BOOLEAN DEFAULT false,

    -- Discovery Source
    source_url VARCHAR(2048),
    depth INTEGER DEFAULT 0,

    -- Metadata
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_data JSONB
);

-- Create indexes for endpoints
CREATE INDEX IF NOT EXISTS idx_asset_endpoint ON endpoints(asset_id);
CREATE INDEX IF NOT EXISTS idx_endpoint_type ON endpoints(endpoint_type);
CREATE INDEX IF NOT EXISTS idx_is_api ON endpoints(is_api);
CREATE UNIQUE INDEX IF NOT EXISTS idx_asset_url ON endpoints(asset_id, url, method);

-- ========================================
-- 5. Backfill priority values
-- ========================================

-- Automatically set priority based on existing risk_score
-- critical: risk_score >= 8.0
-- high: 6.0 <= risk_score < 8.0
-- normal: 3.0 <= risk_score < 6.0
-- low: risk_score < 3.0

UPDATE assets
SET priority = 'critical',
    priority_updated_at = CURRENT_TIMESTAMP,
    priority_auto_calculated = true
WHERE risk_score >= 8.0 AND priority = 'normal';

UPDATE assets
SET priority = 'high',
    priority_updated_at = CURRENT_TIMESTAMP,
    priority_auto_calculated = true
WHERE risk_score >= 6.0 AND risk_score < 8.0 AND priority = 'normal';

UPDATE assets
SET priority = 'normal',
    priority_updated_at = CURRENT_TIMESTAMP,
    priority_auto_calculated = true
WHERE risk_score >= 3.0 AND risk_score < 6.0 AND priority = 'normal';

UPDATE assets
SET priority = 'low',
    priority_updated_at = CURRENT_TIMESTAMP,
    priority_auto_calculated = true
WHERE risk_score < 3.0 AND priority = 'normal';

-- ========================================
-- 6. Update alembic version
-- ========================================

UPDATE alembic_version SET version_num = '004';

COMMIT;

SELECT '✅ Migration 004 complete: Enrichment models and priority system added' AS status;
