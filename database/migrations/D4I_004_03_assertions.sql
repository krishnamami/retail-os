-- ============================================================================
-- D4I_004 step 2a -- promote the approval-chain evidence to assertions.
-- ONE STATEMENT. Expected result line: INSERT 0 114
-- ============================================================================
-- WHY THE EXISTING TRANSFORM COULD NOT DO THIS
--   transform_prototype_evidence_to_assertions.sql is scoped to seven
--   mapping_ids AND simulator_classification = 'PROTOTYPE_ASSUMPTION'. The 114
--   approval rows match neither. Widening that file would also re-scope a
--   historical artifact; this is a new, general statement instead: promote
--   every evidence row that has no assertion yet, whatever produced it.
--
-- WHY THAT IS SAFE TO GENERALISE
--   Measured, not assumed: all 143 existing assertions carry a
--   source_evidence_id and cover exactly the 143 pre-D4I_004 evidence rows,
--   one to one. So "every evidence row without an assertion" is precisely the
--   114 new ones, and the NOT EXISTS guard makes a second run insert nothing.
--
--   source_evidence_id has a foreign key but NO unique constraint, so that
--   guard is a convention rather than a rule the database enforces. The
--   verifier therefore checks the one-to-one relationship afterwards instead
--   of trusting it.
--
-- COLUMN CHOICES, ALL FOLLOWING THE EXISTING TRANSFORM
--   authority          'evidence_direct'  -- permitted by
--                      assertion_authority_valid; the assertion adds no
--                      interpretation beyond the evidence
--   assertion_type     property_name || '_ASSERTION'
--   effective_at       e.occurred_at   -- when the fact became true
--   arrival_at         e.arrival_at    -- when we learned it; the fold needs
--                      both, and collapsing them would destroy late-arrival
--   simulator_classification NULL, exactly as the prototype transform sets it
--
-- PROVENANCE DOES NOT PROPAGATE HERE, DELIBERATELY
--   runtime.assertion has no provenance column and D4I_003c did not add one.
--   Readiness reaches provenance through source_evidence_id rather than
--   through a second copy that could disagree. Nothing is lost: the join is
--   one hop and the FK guarantees it resolves.
--
-- APPLY IN ONE TRANSACTION, THEN COMMIT.
-- ============================================================================

INSERT INTO runtime.assertion
    (subject_type, subject_id, property_name, asserted_value,
     property_value_type, property_value_json, assertion_type, authority,
     authority_policy_id, effective_at, validity_horizon, arrival_at,
     source_evidence_id, supersedes_assertion_id, simulator_classification)
SELECT e.subject_type,
       e.subject_id,
       e.property_name,
       e.asserted_value,
       e.value_type,
       e.value_json,
       e.property_name || '_ASSERTION',
       'evidence_direct',
       NULL,
       e.occurred_at,
       NULL,
       e.arrival_at,
       e.evidence_id,
       NULL,
       NULL
FROM   runtime.evidence e
WHERE  NOT EXISTS (SELECT 1 FROM runtime.assertion a
                   WHERE a.source_evidence_id = e.evidence_id)
ORDER  BY e.evidence_id;
