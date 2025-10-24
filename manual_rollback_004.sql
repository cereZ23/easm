-- Rollback for Migration 004
-- Removes enrichment models and reverts to migration 003

BEGIN;

-- Drop endpoints table and indexes
DROP INDEX IF EXISTS idx_asset_url;
DROP INDEX IF EXISTS idx_is_api;
DROP INDEX IF EXISTS idx_endpoint_type;
DROP INDEX IF EXISTS idx_asset_endpoint;
DROP TABLE IF EXISTS endpoints;

-- Drop certificates table and indexes
DROP INDEX IF EXISTS idx_asset_serial;
DROP INDEX IF EXISTS idx_expired;
DROP INDEX IF EXISTS idx_expiry;
DROP INDEX IF EXISTS idx_asset_cert;
DROP TABLE IF EXISTS certificates;

-- Drop services enrichment indexes
DROP INDEX IF EXISTS idx_has_tls;
DROP INDEX IF EXISTS idx_enrichment_source;

-- Remove services enrichment columns
ALTER TABLE services DROP COLUMN IF EXISTS enrichment_source;
ALTER TABLE services DROP COLUMN IF EXISTS enriched_at;
ALTER TABLE services DROP COLUMN IF EXISTS tls_version;
ALTER TABLE services DROP COLUMN IF EXISTS has_tls;
ALTER TABLE services DROP COLUMN IF EXISTS screenshot_url;
ALTER TABLE services DROP COLUMN IF EXISTS redirect_url;
ALTER TABLE services DROP COLUMN IF EXISTS content_length;
ALTER TABLE services DROP COLUMN IF EXISTS response_time_ms;
ALTER TABLE services DROP COLUMN IF EXISTS http_headers;
ALTER TABLE services DROP COLUMN IF EXISTS http_technologies;
ALTER TABLE services DROP COLUMN IF EXISTS web_server;

-- Drop assets enrichment indexes
DROP INDEX IF EXISTS idx_enrichment_status;
DROP INDEX IF EXISTS idx_asset_priority_enrichment;

-- Remove assets enrichment columns
ALTER TABLE assets DROP COLUMN IF EXISTS priority_auto_calculated;
ALTER TABLE assets DROP COLUMN IF EXISTS priority_updated_at;
ALTER TABLE assets DROP COLUMN IF EXISTS priority;
ALTER TABLE assets DROP COLUMN IF EXISTS enrichment_status;
ALTER TABLE assets DROP COLUMN IF EXISTS last_enriched_at;

-- Update alembic version
UPDATE alembic_version SET version_num = '003';

COMMIT;

SELECT '✅ Migration 004 rolled back: Enrichment models removed' AS status;
