-- =====================================================================
-- Fold State Snapshot Module — Main Entry Point
-- =====================================================================
-- Purpose:
--   Deterministic state computation answering:
--   "What was knowable for each governed subject/property at horizon T?"
--
-- Physical grain:
--   (decision_horizon, subject_type, subject_id)
--
-- IMPORTANT:
--   - Computes snapshots once into a session-local TEMP table
--   - Validates deterministic replay BEFORE persistent insert
--   - Never deletes/replaces historical Fold snapshots
--   - Identical replay produces zero writes
--   - Different replay raises exception
-- =====================================================================

CREATE OR REPLACE FUNCTION runtime.fold_snapshot_at_horizon(
    p_decision_horizon timestamptz
)
RETURNS TABLE (
    fold_snapshot_count INTEGER,
    total_property_states INTEGER,
    established_count INTEGER,
    unreported_count INTEGER,
    explicitly_undefined_count INTEGER,
    contradicted_count INTEGER,
    subjects_by_type TEXT,
    new_snapshots_inserted INTEGER,
    deterministic_replays INTEGER,
    replay_mismatches INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_established_count       INTEGER := 0;
    v_unreported_count        INTEGER := 0;
    v_undefined_count         INTEGER := 0;
    v_contradicted_count      INTEGER := 0;
    v_total_properties        INTEGER := 0;
    v_snap_count              INTEGER := 0;

    v_kb_version              TEXT;
    v_policy_version          TEXT;
    v_kb_active_count         INTEGER := 0;
    v_policy_active_count     INTEGER := 0;

    v_new_inserts             INTEGER := 0;
    v_replays                 INTEGER := 0;
    v_mismatches              INTEGER := 0;
    v_duplicate_count         INTEGER := 0;

BEGIN

    -- =================================================================
    -- 1. Resolve active governed KB
    -- =================================================================

    SELECT
        COUNT(*),
        MAX(kb_version)
    INTO
        v_kb_active_count,
        v_kb_version
    FROM runtime.governed_knowledge_base
    WHERE is_active = TRUE;

    IF v_kb_active_count = 0 THEN
        RAISE EXCEPTION
            'Fold execution failed: no active KB version found.';
    END IF;

    IF v_kb_active_count > 1 THEN
        RAISE EXCEPTION
            'Fold execution failed: % active KB versions found; expected exactly 1.',
            v_kb_active_count;
    END IF;


    -- =================================================================
    -- 2. Resolve active governed policy
    -- =================================================================

    SELECT
        COUNT(*),
        MAX(policy_version)
    INTO
        v_policy_active_count,
        v_policy_version
    FROM runtime.governed_policy
    WHERE is_active = TRUE;

    IF v_policy_active_count = 0 THEN
        RAISE EXCEPTION
            'Fold execution failed: no active policy version found.';
    END IF;

    IF v_policy_active_count > 1 THEN
        RAISE EXCEPTION
            'Fold execution failed: % active policy versions found; expected exactly 1.',
            v_policy_active_count;
    END IF;


    -- =================================================================
    -- 3. Prepare reusable session-local computed snapshot set
    -- =================================================================
    -- Safe for repeated calls in the same PostgreSQL session/transaction.

    DROP TABLE IF EXISTS pg_temp.fold_computed_snapshots;

    CREATE TEMP TABLE fold_computed_snapshots (
        decision_horizon       timestamptz NOT NULL,
        subject_type           TEXT NOT NULL,
        subject_id             TEXT NOT NULL,
        computed_fold_status   TEXT NOT NULL,
        folded_properties      JSONB NOT NULL,
        all_basis_ids          UUID[] NOT NULL,
        kb_version             TEXT NOT NULL,
        policy_version         TEXT NOT NULL
    ) ON COMMIT DROP;


    -- =================================================================
    -- 4. Compute complete Fold result ONCE
    -- =================================================================

    INSERT INTO fold_computed_snapshots (
        decision_horizon,
        subject_type,
        subject_id,
        computed_fold_status,
        folded_properties,
        all_basis_ids,
        kb_version,
        policy_version
    )

    WITH applicable_properties AS (

        -- -------------------------------------------------------------
        -- CON configuration domain
        -- -------------------------------------------------------------

        SELECT
            'configuration'::TEXT AS subject_type,
            subject_id,
            'sap_con_hierarchy_code'::TEXT AS property_name
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'configuration'
              AND subject_id LIKE 'CON-%'
        ) a

        UNION ALL

        SELECT
            'configuration',
            subject_id,
            'sap_con_load_actor'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'configuration'
              AND subject_id LIKE 'CON-%'
        ) a

        UNION ALL

        SELECT
            'configuration',
            subject_id,
            'sap_con_load_status'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'configuration'
              AND subject_id LIKE 'CON-%'
        ) a


        -- -------------------------------------------------------------
        -- PRD configuration domain
        -- -------------------------------------------------------------

        UNION ALL

        SELECT
            'configuration',
            subject_id,
            'sap_prd_hierarchy_code'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'configuration'
              AND subject_id LIKE 'PRD-%'
        ) a

        UNION ALL

        SELECT
            'configuration',
            subject_id,
            'sap_prd_load_status'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'configuration'
              AND subject_id LIKE 'PRD-%'
        ) a


        -- -------------------------------------------------------------
        -- Launch domain
        -- -------------------------------------------------------------

        UNION ALL

        SELECT
            'launch',
            subject_id,
            'change_requested_by'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'launch'
        ) a

        UNION ALL

        SELECT
            'launch',
            subject_id,
            'change_requester_role'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'launch'
        ) a

        UNION ALL

        SELECT
            'launch',
            subject_id,
            'intent_classification'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'launch'
        ) a


        -- -------------------------------------------------------------
        -- Material domain
        -- -------------------------------------------------------------

        UNION ALL

        SELECT
            'material',
            subject_id,
            'material_status'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'material'
        ) a


        -- -------------------------------------------------------------
        -- SKU domain
        -- -------------------------------------------------------------

        UNION ALL

        SELECT
            'sku',
            subject_id,
            'pricing_confirmed'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'sku'
        ) a

        UNION ALL

        SELECT
            'sku',
            subject_id,
            'pricing_status'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'sku'
        ) a

        UNION ALL

        SELECT
            'sku',
            subject_id,
            'pricing_value_usd'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'sku'
        ) a

        UNION ALL

        SELECT
            'sku',
            subject_id,
            'sku_activation_status'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'sku'
        ) a

        UNION ALL

        SELECT
            'sku',
            subject_id,
            'sku_status'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'sku'
        ) a

        UNION ALL

        SELECT
            'sku',
            subject_id,
            'technical_review_result'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'sku'
        ) a

        -- =================================================================
        -- Product domain
        -- =================================================================

        UNION ALL

        SELECT
            'product'::TEXT AS subject_type,
            subject_id,
            'product_name'::TEXT AS property_name
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'product'
        ) a

        UNION ALL

        SELECT
            'product',
            subject_id,
            'launch_reference'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'product'
        ) a

        -- =================================================================
        -- Configuration Request domain
        -- =================================================================

        UNION ALL

        SELECT
            'configuration_request'::TEXT AS subject_type,
            subject_id,
            'product_reference'::TEXT AS property_name
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'configuration_request'
        ) a

        UNION ALL

        SELECT
            'configuration_request',
            subject_id,
            'launch_reference'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'configuration_request'
        ) a

        UNION ALL

        SELECT
            'configuration_request',
            subject_id,
            'geography'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'configuration_request'
        ) a

        UNION ALL

        SELECT
            'configuration_request',
            subject_id,
            'term_months'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'configuration_request'
        ) a

        UNION ALL

        SELECT
            'configuration_request',
            subject_id,
            'customer_segment'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'configuration_request'
        ) a
    ),


    -- =================================================================
    -- Resolve each property
    -- =================================================================

    property_fold_results AS (

        SELECT
            ap.subject_type,
            ap.subject_id,
            ap.property_name,

            runtime.fold_resolve_value(
                p_decision_horizon,
                ap.subject_type,
                ap.subject_id,
                ap.property_name
            ) AS fold_result

        FROM applicable_properties ap
    ),


    -- =================================================================
    -- Construct deterministic property entries
    -- =================================================================

    property_entries AS (

        SELECT
            pfr.subject_type,
            pfr.subject_id,
            pfr.property_name,

            jsonb_build_object(
                'property_name',
                    pfr.property_name,

                'fold_state',
                    pfr.fold_result ->> 'fold_state',

                'resolved_value',
                    pfr.fold_result -> 'resolved_value',

                'property_value_type',
                    pfr.fold_result ->> 'property_value_type',

                'effective_at',
                    pfr.fold_result ->> 'effective_at',

                'latest_known_arrival_at',
                    pfr.fold_result ->> 'latest_known_arrival_at',

                'basis_assertion_ids',
                    COALESCE(
                        pfr.fold_result -> 'basis_assertion_ids',
                        '[]'::jsonb
                    )
            ) AS property_json,


            -- ---------------------------------------------------------
            -- Correct JSONB array -> deterministic UUID[] conversion
            -- ---------------------------------------------------------

            COALESCE(
                (
                    SELECT
                        array_agg(
                            x.elem::uuid
                            ORDER BY x.elem::uuid
                        )

                    FROM jsonb_array_elements_text(
                        COALESCE(
                            pfr.fold_result -> 'basis_assertion_ids',
                            '[]'::jsonb
                        )
                    ) AS x(elem)
                ),
                ARRAY[]::uuid[]
            ) AS basis_ids

        FROM property_fold_results pfr
    ),


    -- =================================================================
    -- Aggregate properties into one deterministic snapshot per subject
    -- =================================================================

    subject_snapshots AS (

        SELECT
            pe.subject_type,
            pe.subject_id,

            -- deterministic property ordering
            jsonb_agg(
                pe.property_json
                ORDER BY pe.property_name
            ) AS folded_properties,


            -- deterministic unique subject-level lineage
            COALESCE(
                array_agg(
                    DISTINCT u.basis_id
                    ORDER BY u.basis_id
                )
                FILTER (
                    WHERE u.basis_id IS NOT NULL
                ),
                ARRAY[]::uuid[]
            ) AS all_basis_ids,


            -- subject summary only; NOT readiness/authorization
            CASE

                WHEN bool_or(
                    pe.property_json ->> 'fold_state'
                    = 'CONTRADICTED'
                )
                THEN 'CONTRADICTED'

                WHEN bool_or(
                    pe.property_json ->> 'fold_state'
                    = 'EXPLICITLY_UNDEFINED'
                )
                THEN 'EXPLICITLY_UNDEFINED'

                WHEN bool_or(
                    pe.property_json ->> 'fold_state'
                    = 'UNREPORTED'
                )
                THEN 'UNREPORTED'

                ELSE 'ESTABLISHED'

            END AS computed_fold_status

        FROM property_entries pe

        -- LEFT JOIN preserves properties whose basis array is empty.
        LEFT JOIN LATERAL
            unnest(pe.basis_ids) AS u(basis_id)
            ON TRUE

        GROUP BY
            pe.subject_type,
            pe.subject_id
    )

    SELECT
        p_decision_horizon,
        ss.subject_type,
        ss.subject_id,
        ss.computed_fold_status,
        ss.folded_properties,
        ss.all_basis_ids,
        v_kb_version,
        v_policy_version

    FROM subject_snapshots ss;


    -- =================================================================
    -- 5. Deterministic replay validation BEFORE persistent INSERT
    -- =================================================================

    SELECT COUNT(*)
    INTO v_mismatches

    FROM fold_computed_snapshots cs

    INNER JOIN state.fold_state_snapshot fss
        ON fss.decision_horizon = cs.decision_horizon
       AND fss.subject_type = cs.subject_type
       AND fss.subject_id = cs.subject_id

    WHERE cs.computed_fold_status
              IS DISTINCT FROM fss.fold_status

       OR cs.folded_properties
              IS DISTINCT FROM fss.folded_properties

       OR cs.all_basis_ids
              IS DISTINCT FROM fss.basis_assertion_ids

       OR cs.kb_version
              IS DISTINCT FROM fss.kb_version

       OR cs.policy_version
              IS DISTINCT FROM fss.policy_version;


    IF v_mismatches > 0 THEN

        RAISE EXCEPTION
            'Deterministic replay mismatch: % snapshot(s) differ at horizon %. Existing historical Fold state will not be changed.',
            v_mismatches,
            p_decision_horizon;

    END IF;


    -- =================================================================
    -- 6. Count identical deterministic replays BEFORE insert
    -- =================================================================

    SELECT COUNT(*)
    INTO v_replays

    FROM fold_computed_snapshots cs

    INNER JOIN state.fold_state_snapshot fss
        ON fss.decision_horizon = cs.decision_horizon
       AND fss.subject_type = cs.subject_type
       AND fss.subject_id = cs.subject_id;


    -- =================================================================
    -- 7. Persist only snapshots that do not already exist
    -- =================================================================

    INSERT INTO state.fold_state_snapshot (
        decision_horizon,
        subject_type,
        subject_id,
        fold_status,
        folded_properties,
        basis_assertion_ids,
        kb_version,
        policy_version,
        fold_computed_at
    )

    SELECT
        cs.decision_horizon,
        cs.subject_type,
        cs.subject_id,
        cs.computed_fold_status,
        cs.folded_properties,
        cs.all_basis_ids,
        cs.kb_version,
        cs.policy_version,
        CURRENT_TIMESTAMP

    FROM fold_computed_snapshots cs

    ON CONFLICT (
        decision_horizon,
        subject_type,
        subject_id
    )
    DO NOTHING;


    GET DIAGNOSTICS v_new_inserts = ROW_COUNT;


    -- =================================================================
    -- 8. Defensive duplicate-key validation
    -- =================================================================

    SELECT COUNT(*)
    INTO v_duplicate_count

    FROM (
        SELECT
            decision_horizon,
            subject_type,
            subject_id,
            COUNT(*) AS row_count

        FROM state.fold_state_snapshot

        WHERE decision_horizon = p_decision_horizon

        GROUP BY
            decision_horizon,
            subject_type,
            subject_id

        HAVING COUNT(*) > 1
    ) duplicate_keys;


    IF v_duplicate_count > 0 THEN

        RAISE EXCEPTION
            'Fold execution produced % duplicate snapshot key(s).',
            v_duplicate_count;

    END IF;


    -- =================================================================
    -- 9. Snapshot count
    -- =================================================================

    SELECT COUNT(*)
    INTO v_snap_count

    FROM state.fold_state_snapshot

    WHERE decision_horizon = p_decision_horizon;


    -- =================================================================
    -- 10. Property-state distribution
    -- =================================================================

    SELECT

        COUNT(*) FILTER (
            WHERE prop.property_json ->> 'fold_state'
                = 'ESTABLISHED'
        ),

        COUNT(*) FILTER (
            WHERE prop.property_json ->> 'fold_state'
                = 'UNREPORTED'
        ),

        COUNT(*) FILTER (
            WHERE prop.property_json ->> 'fold_state'
                = 'EXPLICITLY_UNDEFINED'
        ),

        COUNT(*) FILTER (
            WHERE prop.property_json ->> 'fold_state'
                = 'CONTRADICTED'
        ),

        COUNT(*)

    INTO
        v_established_count,
        v_unreported_count,
        v_undefined_count,
        v_contradicted_count,
        v_total_properties

    FROM state.fold_state_snapshot fss

    CROSS JOIN LATERAL
        jsonb_array_elements(
            fss.folded_properties
        ) AS prop(property_json)

    WHERE fss.decision_horizon = p_decision_horizon;


    -- =================================================================
    -- 11. Return execution summary
    -- =================================================================

    RETURN QUERY

    SELECT
        v_snap_count,
        v_total_properties,
        v_established_count,
        v_unreported_count,
        v_undefined_count,
        v_contradicted_count,

        (
            SELECT jsonb_object_agg(
                x.subject_type,
                x.subject_count
            )

            FROM (
                SELECT
                    subject_type,
                    COUNT(DISTINCT subject_id) AS subject_count

                FROM state.fold_state_snapshot

                WHERE decision_horizon = p_decision_horizon

                GROUP BY subject_type

                ORDER BY subject_type
            ) x
        )::TEXT,

        v_new_inserts,
        v_replays,
        v_mismatches;

END;
$$;