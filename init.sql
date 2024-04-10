-- Initial database setup for EASM platform
-- This script runs automatically when PostgreSQL container starts

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search

-- Create demo tenant
INSERT INTO tenants (name, slug, contact_policy, created_at, updated_at)
VALUES ('Demo Tenant', 'demo', 'Contact: demo@example.com', NOW(), NOW())
ON CONFLICT DO NOTHING;

-- Create some demo seeds for the demo tenant
DO $$
DECLARE
    demo_tenant_id INTEGER;
BEGIN
    SELECT id INTO demo_tenant_id FROM tenants WHERE slug = 'demo' LIMIT 1;

    IF demo_tenant_id IS NOT NULL THEN
        -- Insert demo seeds
        INSERT INTO seeds (tenant_id, type, value, enabled, created_at)
        VALUES
            (demo_tenant_id, 'domain', 'example.com', true, NOW()),
            (demo_tenant_id, 'domain', 'example.org', true, NOW())
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

-- Create indexes for performance (if not already created by SQLAlchemy)
CREATE INDEX IF NOT EXISTS idx_assets_tenant_active ON assets(tenant_id, is_active);
CREATE INDEX IF NOT EXISTS idx_assets_risk_score ON assets(risk_score DESC);
CREATE INDEX IF NOT EXISTS idx_events_asset_created ON events(asset_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_findings_asset_status ON findings(asset_id, status);

-- Add comments for documentation
COMMENT ON TABLE tenants IS 'Multi-tenant isolation - each customer/organization';
COMMENT ON TABLE assets IS 'Discovered assets (domains, IPs, URLs, services)';
COMMENT ON TABLE services IS 'Services running on assets (HTTP, ports, etc.)';
COMMENT ON TABLE findings IS 'Security findings from vulnerability scans';
COMMENT ON TABLE events IS 'Timeline of changes to assets';
COMMENT ON TABLE seeds IS 'Input seeds for discovery (root domains, ASNs, keywords)';
