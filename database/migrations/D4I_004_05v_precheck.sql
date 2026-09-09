-- ============================================================================
-- D4I_004 step 2c pre-check -- READ ONLY. ONE STATEMENT. RUN BEFORE THE FOLD.
-- ============================================================================
-- Two things must hold before fold_snapshot_at_horizon_v2 is called, and both
-- caused real failures already:
--
--   A  every subject must have at least one assertion arriving at or before
--      the horizon. A subject whose properties all resolve UNREPORTED
--      aggregates to a NULL basis and basis_assertion_ids is uuid[] NOT NULL,
--      so the fold aborts mid-run. That is what PRD-001 did.
--
--   B  every (subject_type, property_name) that assertions actually carry
--      must appear in the v2 triple list. A property missing from that list
--      is not an error -- it is worse, it is silent: the fact exists, the
--      fold never enumerates it, and readiness decides without it. That is
--      exactly how the approval chain stayed invisible.
--
-- The horizon is 2026-07-31, chosen because the latest assertion arrives
-- 2026-07-16 08:30 -- a month after the old 2026-06-20 horizon. Two facts
-- arrive that late. Folding at the old horizon would correctly exclude them;
-- readiness should see current state, so the horizon moves.
--
-- READ ONLY.
-- ============================================================================

WITH H AS (SELECT '2026-07-31 00:00:00+00'::timestamptz AS h),
v2_properties(subject_type, property_name) AS (
    VALUES ('configuration','sap_con_hierarchy_code'),
           ('configuration','sap_con_load_actor'),
           ('configuration','sap_con_load_status'),
           ('configuration','con_verification_status'),
           ('configuration','sap_con_test_status'),
           ('configuration','sap_con_test_actor'),
           ('configuration','sap_prd_hierarchy_code'),
           ('configuration','sap_prd_load_status'),
           ('configuration','sap_prd_promotion_hierarchy_code'),
           ('configuration','sap_prd_promotion_actor'),
           ('launch','change_requested_by'),
           ('launch','change_requester_role'),
           ('launch','intent_classification'),
           ('launch','hierarchy_approval_code'),
           ('launch','hierarchy_approval_authority'),
           ('material','material_status'),
           ('sku','pricing_confirmed'),
           ('sku','pricing_status'),
           ('sku','pricing_value_usd'),
           ('sku','sku_activation_status'),
           ('sku','sku_status'),
           ('sku','technical_review_result'),
           ('sku','final_pricing_approval_status'),
           ('sku','pricing_upload_status'),
           ('sku','pricing_uploaded_price_usd'),
           ('sku','pricing_publication_status'),
           ('sku','pricing_list_price'),
           ('sku','pricing_currency'),
           ('sku','pricing_published_by'),
           ('sku','overnight_push_status'),
           ('sku','overnight_push_run_date'),
           ('sku','zupdm_approval_status'),
           ('sku','all_gates_cleared'),
           ('sku','go_live_approval_requested'),
           ('sku','go_live_approval_level'),
           ('sku','go_live_requested_by'),
           ('sku','go_live_approval_status'),
           ('sku','go_live_approved_by'),
           ('sku','supply_chain_notification_status'),
           ('sku','supply_chain_notification_type'),
           ('sku','supply_chain_notified_by'),
           ('sku','material_activation_status'),
           ('sku','material_activated_by'),
           ('product','product_name'),
           ('product','launch_reference'),
           ('configuration_request','product_reference'),
           ('configuration_request','launch_reference'),
           ('configuration_request','geography'),
           ('configuration_request','term_months'),
           ('configuration_request','customer_segment')
),
subj AS (
    SELECT a.subject_type, a.subject_id,
           count(*) AS assertions,
           count(*) FILTER (WHERE a.arrival_at <= (SELECT h FROM H))
             AS in_horizon
    FROM   runtime.assertion a
    GROUP  BY a.subject_type, a.subject_id
),
carried AS (
    SELECT a.subject_type, a.property_name, count(*) AS n
    FROM   runtime.assertion a
    GROUP  BY a.subject_type, a.property_name
),
secA AS (
    SELECT 'A'::text AS section, 1 AS ord,
           'subjects with no assertion inside the horizon'::text AS item,
           'each one would abort the fold'::text AS detail,
           (SELECT count(*) FROM subj WHERE in_horizon = 0)::text AS actual,
           '0'::text AS expected,
           CASE WHEN (SELECT count(*) FROM subj WHERE in_horizon = 0) = 0
                THEN 'ok' ELSE 'FAIL' END::text AS verdict
    UNION ALL
    SELECT 'A', 1 + row_number() OVER (ORDER BY subject_type, subject_id)::int,
           (subject_type || ' / ' || subject_id), 'no assertion in horizon',
           in_horizon::text, '> 0', 'FAIL'
    FROM   subj WHERE in_horizon = 0
    UNION ALL
    SELECT 'A', 90, 'subjects to be folded', '',
           (SELECT count(*) FROM subj)::text, '', 'info'
    UNION ALL
    SELECT 'A', 91, 'assertions visible at this horizon',
           'of 257 total',
           (SELECT count(*) FROM runtime.assertion
            WHERE arrival_at <= (SELECT h FROM H))::text, '257',
           CASE WHEN (SELECT count(*) FROM runtime.assertion
                      WHERE arrival_at <= (SELECT h FROM H)) = 257
                THEN 'ok' ELSE 'info -- some facts arrive later still' END
),
secB AS (
    SELECT 'B'::text, 1,
           'properties carried by assertions but absent from the v2 list'::text,
           'these would fold silently to nothing'::text,
           (SELECT count(*) FROM carried c
            WHERE NOT EXISTS (SELECT 1 FROM v2_properties v
                              WHERE v.subject_type = c.subject_type
                                AND v.property_name = c.property_name))::text,
           '0',
           CASE WHEN (SELECT count(*) FROM carried c
                      WHERE NOT EXISTS (SELECT 1 FROM v2_properties v
                                        WHERE v.subject_type = c.subject_type
                                          AND v.property_name
                                              = c.property_name)) = 0
                THEN 'ok' ELSE 'FAIL -- a fact would never be folded' END
    UNION ALL
    SELECT 'B', 1 + row_number() OVER (ORDER BY c.subject_type,
                                                c.property_name)::int,
           (c.subject_type || ' . ' || c.property_name), 'not in the v2 list',
           c.n::text, 'must be listed', 'FAIL'
    FROM   carried c
    WHERE  NOT EXISTS (SELECT 1 FROM v2_properties v
                       WHERE v.subject_type = c.subject_type
                         AND v.property_name = c.property_name)
    UNION ALL
    SELECT 'B', 90, 'v2 list entries with no assertion anywhere',
           'enumerated but never asserted -- fold as UNREPORTED, which is fine',
           (SELECT count(*) FROM v2_properties v
            WHERE NOT EXISTS (SELECT 1 FROM carried c
                              WHERE c.subject_type = v.subject_type
                                AND c.property_name = v.property_name))::text,
           '', 'info'
    UNION ALL
    SELECT 'B', 91, 'v2 triple list size', '22 deployed + 28 new',
           (SELECT count(*) FROM v2_properties)::text, '50',
           CASE WHEN (SELECT count(*) FROM v2_properties) = 50
                THEN 'ok' ELSE 'FAIL' END
),
secC AS (
    SELECT 'C'::text, row_number() OVER (ORDER BY c.subject_type,
                                                  c.property_name)::int,
           c.subject_type::text, c.property_name::text, c.n::text,
           (SELECT count(DISTINCT a.subject_id)::text FROM runtime.assertion a
            WHERE a.subject_type = c.subject_type
              AND a.property_name = c.property_name) || ' subjects',
           'info'::text
    FROM   carried c
),
body AS (
    SELECT * FROM secA UNION ALL SELECT * FROM secB UNION ALL SELECT * FROM secC
)
SELECT section, ord AS seq, item, detail, actual, expected, verdict,
       CASE WHEN (SELECT count(*) FROM body
                  WHERE verdict NOT IN ('ok','info')
                    AND verdict NOT LIKE 'info --%') = 0
            THEN 'PRE-CHECK OK -- safe to fold at 2026-07-31'
            ELSE 'STOP -- do not fold' END AS overall
FROM   body
ORDER  BY section, ord;
