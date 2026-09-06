-- Migration: Fix Evidence Identity Model
-- Corrected to use simple SQL (no DO blocks for asyncpg compatibility)

BEGIN;

-- Step 1: Add mapping_id column if it doesn't exist
-- (asyncpg will ignore if it already exists, so we'll add it unconditionally
--  and catch any "already exists" errors at runner level)
ALTER TABLE runtime.evidence ADD COLUMN mapping_id TEXT NOT NULL DEFAULT '';

-- Step 2: Drop the old incompatible UNIQUE constraint
ALTER TABLE runtime.evidence DROP CONSTRAINT evidence_subject_property_arrival;

-- Step 3: Add the new lineage-based UNIQUE constraint
ALTER TABLE runtime.evidence ADD CONSTRAINT evidence_lineage_identity_unique UNIQUE (raw_event_id, mapping_id);

COMMIT;
