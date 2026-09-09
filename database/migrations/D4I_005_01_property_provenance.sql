-- ============================================================================
-- D4I_005 step 1 -- runtime.property_provenance_at(timestamptz)
-- ONE STATEMENT. Deliberately.
-- ============================================================================
-- WHAT IT IS
--   Every folded property at a horizon, with the provenance of the evidence
--   underneath it. Pure: RETURNS TABLE, STABLE, writes nothing.
--
-- WHY IT EXISTS IN THE DATABASE RATHER THAN IN EACH CONSUMER
--   Provenance sits two joins from the fold:
--       folded property -> basis_assertion_ids -> assertion
--                       -> source_evidence_id  -> evidence.value_provenance
--   Readiness needs it, the Workbench needs it, and the agent needs it. Three
--   implementations of the same join would eventually disagree about what
--   OBSERVED means, and the whole point of D4I_003c was to stop that word
--   meaning different things in different places.
--
-- THE PRECEDENCE RULE, AND WHY IT IS THE CONSERVATIVE ONE
--   A folded property can rest on several assertions. This reports:
--       DEFAULTED  if ANY basis evidence was defaulted
--       DERIVED    if any was derived and none defaulted
--       OBSERVED   only when every basis row was observed
--       NULL       when the property has no basis at all (UNREPORTED)
--   Weakest link wins. A resolved value that is even partly manufactured must
--   not present as fully observed -- a readiness rule reading OBSERVED is
--   entitled to assume a source asserted every part of it.
--
--   basis_count and defaulted_count are returned alongside so a caller can
--   show the mix rather than only the verdict.
--
-- WHAT IT DOES NOT DO
--   No policy. It does not decide whether a DEFAULTED value is acceptable --
--   that is a governed decision, and different readiness rules may answer it
--   differently for different properties. This function only makes the
--   distinction visible.
--
-- APPLY IN ONE TRANSACTION, THEN COMMIT.
-- ============================================================================

CREATE OR REPLACE FUNCTION runtime.property_provenance_at(
    p_decision_horizon timestamp with time zone)
RETURNS TABLE (
    subject_type      varchar,
    subject_id        varchar,
    property_name     text,
    fold_state        text,
    resolved_value    jsonb,
    property_value_type text,
    effective_at      text,
    latest_known_arrival_at text,
    value_provenance  text,
    basis_count       integer,
    observed_count    integer,
    defaulted_count   integer,
    derived_count     integer
)
LANGUAGE sql
STABLE
AS $provenance$

WITH prop AS (
    SELECT s.subject_type,
           s.subject_id,
           p AS property,
           s.fold_state_id
    FROM   state.fold_state_snapshot s
    CROSS  JOIN LATERAL jsonb_array_elements(s.folded_properties) AS p
    WHERE  s.decision_horizon = p_decision_horizon
),
basis AS (
    SELECT pr.fold_state_id,
           pr.subject_type,
           pr.subject_id,
           pr.property ->> 'property_name' AS property_name,
           ev.value_provenance
    FROM   prop pr
    CROSS  JOIN LATERAL jsonb_array_elements_text(
                   COALESCE(pr.property -> 'basis_assertion_ids',
                            '[]'::jsonb)) AS b(assertion_id)
    JOIN   runtime.assertion a ON a.assertion_id = b.assertion_id::uuid
    JOIN   runtime.evidence  ev ON ev.evidence_id = a.source_evidence_id
)
SELECT pr.subject_type,
       pr.subject_id,
       (pr.property ->> 'property_name')::text,
       (pr.property ->> 'fold_state')::text,
       pr.property -> 'resolved_value',
       (pr.property ->> 'property_value_type')::text,
       (pr.property ->> 'effective_at')::text,
       (pr.property ->> 'latest_known_arrival_at')::text,
       CASE
         WHEN count(b.value_provenance) = 0 THEN NULL
         WHEN count(*) FILTER (WHERE b.value_provenance = 'DEFAULTED') > 0
              THEN 'DEFAULTED'
         WHEN count(*) FILTER (WHERE b.value_provenance = 'DERIVED') > 0
              THEN 'DERIVED'
         ELSE 'OBSERVED'
       END::text,
       count(b.value_provenance)::int,
       count(*) FILTER (WHERE b.value_provenance = 'OBSERVED')::int,
       count(*) FILTER (WHERE b.value_provenance = 'DEFAULTED')::int,
       count(*) FILTER (WHERE b.value_provenance = 'DERIVED')::int
FROM   prop pr
LEFT   JOIN basis b
  ON   b.fold_state_id = pr.fold_state_id
 AND   b.property_name = pr.property ->> 'property_name'
GROUP  BY pr.subject_type, pr.subject_id, pr.property, pr.fold_state_id

$provenance$;
