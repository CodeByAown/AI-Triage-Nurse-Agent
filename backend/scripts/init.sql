-- Neural Hub AI Triage Nurse — Database Init Script
-- Runs once on first Postgres container start

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For full-text search

-- Ensure timezone is UTC
SET timezone = 'UTC';
