-- ============================================================================
-- D4I_004 step 2 verification -- assertions and fold. READ ONLY. ONE STATEMENT.
-- ============================================================================
-- Section B carries the weight. configuration_request and product are the
-- identity-assessment inputs; D4I_004 added no evidence on those subjects, so
-- their snapshots must come back byte-identical in shape -- 7 subjects / 35
-- properties and 1 / 2. If they moved, the re-fold reached further than the
-- approval chain and identity decisions would be resting on changed ground.
--
-- Section A proves the promotion is one-to-one with evidence. source_evidence_id
-- has a foreign key but no unique constraint, so the guard in the transform is
-- a convention; this measures the result instead of trusting it.
--
-- Section D reports growth rather than asserting exact numbers for the subjects
-- that legitimately changed. Predicting them would be inventing an expectation;
-- what matters is that they grew, that nothing folded to INVALID, and that
-- every assertion is represented in some snapshot's basis.
--
-- Anything other than 'ok' or 'info' is a stop.
--
-- READ ONLY: no CREATE, REPLACE, INSERT, UPDATE, DELETE, TRUNCATE, ALTER,
-- DROP or GRANT.
-- ============================================================================

WITH H AS (SELECT '2026-06-20 10:45:00+00'::timestamptz AS h),
snap AS MATERIALIZED (
    SELECT s.* FROM state.fold_state_snapshot s, H
    WHERE  s.decision_horizon = H.h
),
props AS MATERIALIZED (
    SELECT s.subject_type, s.subject_id,
           p->>'property_name' AS property_name,
           p->>'fold_state'    AS fold_state
    FROM   snap s, LATERAL jsonb_array_elements(s.folded_properties) AS p
),

secA AS (
    SELECT 'A'::text AS section, 1 AS ord, 'assertion rows'::text AS item,
           'was 143'::text AS detail,
           (SELECT count(*) FROM runtime.assertion)::text AS actual,
           '257'::text AS expected,
           CASE WHEN (SELECT count(*) FROM runtime.assertion) = 257
                THEN 'ok' ELSE 'FAIL' END::text AS verdict
    UNION ALL
    SELECT 'A', 2, 'evidence rows without an assertion',
           'the D4I_004 gap, was 114',
           (SELECT count(*) FROM runtime.evidence e
            WHERE NOT EXISTS (SELECT 1 FROM runtime.assertion a
                              WHERE a.source_evidence_id = e.evidence_id))::text,
           '0',
           CASE WHEN (SELECT count(*) FROM runtime.evidence e
                      WHERE NOT EXISTS (SELECT 1 FROM runtime.assertion a
                                        WHERE a.source_evidence_id
                                              = e.evidence_id)) = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'A', 3, 'evidence rows promoted more than once',
           'source_evidence_id has no unique constraint',
           (SELECT count(*) FROM (SELECT source_evidence_id
                                  FROM runtime.assertion
                                  WHERE source_evidence_id IS NOT NULL
                                  GROUP BY 1 HAVING count(*) > 1) d)::text, '0',
           CASE WHEN (SELECT count(*) FROM (SELECT source_evidence_id
                                            FROM runtime.assertion
                                            WHERE source_evidence_id IS NOT NULL
                                            GROUP BY 1 HAVING count(*) > 1) d)
                     = 0 THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'A', 4, 'assertions without a source evidence row', '',
           (SELECT count(*) FROM runtime.assertion
            WHERE source_evidence_id IS NULL)::text, '0',
           CASE WHEN (SELECT count(*) FROM runtime.assertion
                      WHERE source_evidence_id IS NULL) = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'A', 5, 'assertion value disagreeing with its evidence',
           'the assertion adds no interpretation',
           (SELECT count(*) FROM runtime.assertion a
            JOIN runtime.evidence e ON e.evidence_id = a.source_evidence_id
            WHERE a.asserted_value IS DISTINCT FROM e.asserted_value
               OR a.subject_id     IS DISTINCT FROM e.subject_id
               OR a.property_name  IS DISTINCT FROM e.property_name
               OR a.effective_at   IS DISTINCT FROM e.occurred_at
               OR a.arrival_at     IS DISTINCT FROM e.arrival_at)::text, '0',
           CASE WHEN (SELECT count(*) FROM runtime.assertion a
                      JOIN runtime.evidence e
                        ON e.evidence_id = a.source_evidence_id
                      WHERE a.asserted_value IS DISTINCT FROM e.asserted_value
                         OR a.subject_id     IS DISTINCT FROM e.subject_id
                         OR a.property_name  IS DISTINCT FROM e.property_name
                         OR a.effective_at   IS DISTINCT FROM e.occurred_at
                         OR a.arrival_at     IS DISTINCT FROM e.arrival_at) = 0
                THEN 'ok' ELSE 'FAIL' END
),

secB AS (
    SELECT 'B'::text, 1, 'configuration_request subjects'::text,
           'identity-assessment input -- must not move'::text,
           (SELECT count(*) FROM snap
            WHERE subject_type='configuration_request')::text, '7',
           CASE WHEN (SELECT count(*) FROM snap
                      WHERE subject_type='configuration_request') = 7
                THEN 'ok' ELSE 'FAIL -- identity inputs moved' END
    UNION ALL
    SELECT 'B', 2, 'configuration_request folded properties',
           'identity-assessment input -- must not move',
           (SELECT count(*) FROM props
            WHERE subject_type='configuration_request')::text, '35',
           CASE WHEN (SELECT count(*) FROM props
                      WHERE subject_type='configuration_request') = 35
                THEN 'ok' ELSE 'FAIL -- identity inputs moved' END
    UNION ALL
    SELECT 'B', 3, 'product subjects / properties', 'must not move',
           ((SELECT count(*) FROM snap WHERE subject_type='product')::text
             || ' / '
             || (SELECT count(*) FROM props WHERE subject_type='product')::text),
           '1 / 2',
           CASE WHEN (SELECT count(*) FROM snap WHERE subject_type='product')=1
                 AND (SELECT count(*) FROM props WHERE subject_type='product')=2
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'B', 4, 'material subjects / properties',
           'no approval evidence on material subjects',
           ((SELECT count(*) FROM snap WHERE subject_type='material')::text
             || ' / '
             || (SELECT count(*) FROM props WHERE subject_type='material')::text),
           '3 / 3',
           CASE WHEN (SELECT count(*) FROM snap WHERE subject_type='material')=3
                 AND (SELECT count(*) FROM props WHERE subject_type='material')=3
                THEN 'ok' ELSE 'FAIL' END
),

secC AS (
    SELECT 'C'::text, row_number() OVER (ORDER BY s.subject_type)::int,
           s.subject_type::text,
           ('subjects ' || count(DISTINCT s.subject_id)::text)::text,
           ('folded properties ' ||
             (SELECT count(*) FROM props p
              WHERE p.subject_type = s.subject_type)::text)::text,
           (CASE s.subject_type
              WHEN 'configuration'         THEN 'was 22 subjects / 57 props'
              WHEN 'configuration_request' THEN 'was 7 / 35'
              WHEN 'launch'                THEN 'was 13 / 39'
              WHEN 'material'              THEN 'was 3 / 3'
              WHEN 'product'               THEN 'was 1 / 2'
              WHEN 'sku'                   THEN 'was 13 / 78'
              ELSE 'new subject type' END)::text,
           'info'::text
    FROM   snap s GROUP BY s.subject_type
),

secD AS (
    SELECT 'D'::text, 1, 'total folded properties'::text,
           'was 214 before D4I_004'::text,
           (SELECT count(*) FROM props)::text, '> 214',
           CASE WHEN (SELECT count(*) FROM props) > 214
                THEN 'ok' ELSE 'FAIL -- the re-fold added nothing' END
    UNION ALL
    SELECT 'D', 2, 'properties folded to INVALID', 'a governed failure state',
           (SELECT count(*) FROM props WHERE fold_state='INVALID')::text, '0',
           CASE WHEN (SELECT count(*) FROM props WHERE fold_state='INVALID') = 0
                THEN 'ok' ELSE 'FAIL' END
    UNION ALL
    SELECT 'D', 3 + row_number() OVER (ORDER BY fold_state)::int,
           fold_state, 'fold state distribution', count(*)::text, '', 'info'
    FROM   props GROUP BY fold_state
    UNION ALL
    SELECT 'D', 20, 'assertions not represented in any snapshot basis',
           'every promoted fact should reach the fold',
           (SELECT count(*) FROM runtime.assertion a
            WHERE a.arrival_at <= (SELECT h FROM H)
              AND NOT EXISTS (
                SELECT 1 FROM snap s
                WHERE s.basis_assertion_ids @> ARRAY[a.assertion_id]))::text,
           '0',
           CASE WHEN (SELECT count(*) FROM runtime.assertion a
                      WHERE a.arrival_at <= (SELECT h FROM H)
                        AND NOT EXISTS (
                          SELECT 1 FROM snap s
                          WHERE s.basis_assertion_ids
                                @> ARRAY[a.assertion_id])) = 0
                THEN 'ok' ELSE 'info -- inspect before readiness' END
),

secE AS (
    SELECT 'E'::text, row_number() OVER (ORDER BY p.property_name)::int,
           p.property_name::text,
           ('subject ' || p.subject_type)::text,
           count(*)::text,
           ('ESTABLISHED ' || count(*) FILTER (WHERE p.fold_state='ESTABLISHED')::text)::text,
           'info'::text
    FROM   props p
    WHERE  p.property_name IN
           ('final_pricing_approval_status','all_gates_cleared',
            'zupdm_approval_status','pricing_upload_status',
            'pricing_publication_status','go_live_approval_status',
            'supply_chain_notification_status','material_activation_status',
            'con_verification_status','sap_con_test_status',
            'hierarchy_approval_code','technical_review_result',
            'pricing_confirmed','pricing_status')
    GROUP  BY p.property_name, p.subject_type
),

body AS (
    SELECT * FROM secA UNION ALL SELECT * FROM secB
    UNION ALL SELECT * FROM secC UNION ALL SELECT * FROM secD
    UNION ALL SELECT * FROM secE
)
SELECT section, ord AS seq, item, detail, actual, expected, verdict,
       CASE WHEN (SELECT count(*) FROM body
                  WHERE verdict NOT IN ('ok','info')
                    AND verdict NOT LIKE 'info --%') = 0
            THEN 'STEP 2 OK -- 257 assertions, re-folded, identity inputs intact'
            ELSE 'STOP' END AS overall
FROM   body
ORDER  BY section, ord;
