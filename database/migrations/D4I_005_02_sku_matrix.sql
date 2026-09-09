-- ============================================================================
-- D4I_005 step 2 -- the per-SKU readiness matrix. READ ONLY. ONE STATEMENT.
-- ============================================================================
-- Readiness policy has to be written against what the corpus actually holds,
-- not against what a launch process is supposed to produce. This prints, for
-- every sku subject, each readiness-relevant property as
--     value [provenance]
-- with UNREPORTED shown as a dash.
--
-- What it will settle:
--   * which SKUs carry an OBSERVED technical review, which carry a DEFAULTED
--     one, and which carry none
--   * whether the two pricing-approval populations (PRICING_CONFIRMED for the
--     early SKUs, FINAL_PRICING_APPROVAL for the later ones) overlap at all
--   * whether ANY SKU has complete observed evidence across technical,
--     pricing and go-live -- which decides whether demo scenario A is
--     achievable from real data or must be reported as not demonstrable
--
-- READ ONLY.
-- ============================================================================

WITH pp AS MATERIALIZED (
    SELECT * FROM runtime.property_provenance_at('2026-07-31 00:00:00+00'::timestamptz)
    WHERE  subject_type = 'sku'
),
cell AS (
    SELECT subject_id, property_name,
           CASE WHEN fold_state <> 'ESTABLISHED' THEN '-'
                ELSE COALESCE(resolved_value #>> '{}', '?')
                     || ' [' || left(COALESCE(value_provenance,'?'),1) || ']'
           END AS v
    FROM   pp
),
g AS (
    SELECT subject_id,
           max(v) FILTER (WHERE property_name='sku_status')                  AS sku_status,
           max(v) FILTER (WHERE property_name='technical_review_result')     AS tech_review,
           max(v) FILTER (WHERE property_name='sku_activation_status')       AS activated,
           max(v) FILTER (WHERE property_name='pricing_status')              AS pricing_status,
           max(v) FILTER (WHERE property_name='pricing_value_usd')           AS pricing_value,
           max(v) FILTER (WHERE property_name='pricing_confirmed')           AS pricing_confirmed,
           max(v) FILTER (WHERE property_name='final_pricing_approval_status') AS final_appr,
           max(v) FILTER (WHERE property_name='zupdm_approval_status')       AS zupdm,
           max(v) FILTER (WHERE property_name='all_gates_cleared')           AS all_gates,
           max(v) FILTER (WHERE property_name='pricing_upload_status')       AS uploaded,
           max(v) FILTER (WHERE property_name='pricing_publication_status')  AS published,
           max(v) FILTER (WHERE property_name='go_live_approval_status')     AS go_live,
           max(v) FILTER (WHERE property_name='material_activation_status')  AS material,
           max(v) FILTER (WHERE property_name='supply_chain_notification_status') AS supply,
           count(*) FILTER (WHERE v <> '-')                                  AS established,
           count(*) FILTER (WHERE v LIKE '%[D]')                             AS defaulted
    FROM   cell GROUP BY subject_id
)
SELECT subject_id,
       sku_status, tech_review, activated,
       pricing_status, pricing_value, pricing_confirmed, final_appr,
       zupdm, all_gates, uploaded, published,
       go_live, material, supply,
       established || ' est / ' || defaulted || ' dflt' AS coverage
FROM   g
ORDER  BY subject_id;
