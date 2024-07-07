-- Initial database setup for EASM platform
-- This script runs automatically when PostgreSQL container starts
-- Tables will be created by Alembic migrations when API starts

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search

-- Note: Demo data should be added after Alembic migrations run
-- You can add a tenant using the API or directly via SQL after startup:
--
-- INSERT INTO tenants (name, slug, contact_policy, created_at, updated_at)
-- VALUES ('Demo Tenant', 'demo', 'Contact: demo@example.com', NOW(), NOW());
--
-- Then add seeds:
-- INSERT INTO seeds (tenant_id, type, value, enabled, created_at)
-- VALUES (1, 'domain', 'example.com', true, NOW());
