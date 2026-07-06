-- ──────────────────────────────────────────────────────────────────────────────
-- VulnForge — PostgreSQL Database Initialization Script
-- Runs once when the Docker postgres container first starts.
-- ──────────────────────────────────────────────────────────────────────────────

-- Enable pgcrypto for gen_random_uuid() — required by all models
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Enable pg_trgm for future full-text fuzzy search on vulnerability titles
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ── Audit Log: Create updated_at trigger function ──────────────────────────
-- This trigger maintains updated_at on every table that has it.
-- SQLAlchemy's onupdate handles ORM-level updates; this trigger handles
-- bulk SQL updates that bypass the ORM (e.g., direct psql operations).
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ── Audit Log: Row-level security scaffolding ──────────────────────────────
-- The audit_logs table is append-only. This policy prevents any UPDATE
-- or DELETE from being executed against it by any role except superuser.
-- Note: Alembic migrations run as superuser and are exempt.
-- The full RLS enablement happens in the first Alembic migration.
