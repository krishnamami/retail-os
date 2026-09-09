-- ============================================================================
-- D4I_004 step 2 -- apply the approval-chain evidence. ONE STATEMENT.
-- ============================================================================
-- Expected result line: INSERT 0 114
--
-- ADDITIVE BY CONSTRUCTION
--   ON CONFLICT (raw_event_id, mapping_id) DO NOTHING uses the identity the
--   database itself declares via evidence_lineage_identity_unique, and
--   D4I_004_01v proves zero projected rows collide with an existing one. So
--   this can only add rows: the 143 existing facts are not in its path, and
--   re-running it inserts nothing.
--
-- WHY value_provenance IS LISTED EXPLICITLY
--   The column is NOT NULL with no DEFAULT. A writer that omitted it would be
--   refused rather than quietly recorded as certain -- which is the point of
--   D4I_003c, and this is the first new writer to live under that contract.
--
-- NOT SET: simulator_classification stays NULL on these rows, as it is on the
-- other 107. It is an independent dimension and D4I_004 does not touch it.
--
-- Verify with D4I_004_02v_verify.sql.
-- APPLY IN ONE TRANSACTION, THEN COMMIT.
-- ============================================================================

INSERT INTO runtime.evidence
    (raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
     property_name, asserted_value, value_type, source_system, source_actor_id,
     source_actor_role, occurred_at, recorded_at, arrival_at, evidence_lineage,
     value_provenance)
SELECT raw_event_id, mapping_id, evidence_type, subject_type, subject_id,
       property_name, asserted_value, value_type, source_system,
       source_actor_id, source_actor_role, occurred_at, recorded_at,
       arrival_at, evidence_lineage, value_provenance
FROM   runtime.approval_projection_v1()
ON CONFLICT (raw_event_id, mapping_id) DO NOTHING;
