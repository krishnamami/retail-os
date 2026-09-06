-- =====================================================================
-- Seed: 11 missing catalogue rules (agency_guidelines + regulatory_rules)
--
-- Closes the gaps found in the 2026-06-19 catalogue audit:
--   8 missing entries + 3 values promoted out of `conditions` free-text
--   into structured rows so a resolver can read them by key.
--
-- These two tables were "created out-of-band and are still NOT defined"
-- in infra/schema.sql (see note at schema.sql:1337) — this file is the
-- first versioned, reproducible seed for them.
--
-- Idempotent: each INSERT is guarded by WHERE NOT EXISTS on the
-- identifying (agency|authority, name) pair. There is no unique
-- constraint on those columns (only the uuid PK), so ON CONFLICT has no
-- target — the guard is what makes re-runs safe.
--
-- Convention: the machine key lives in guideline_name / rule_name; the
-- numeric value lives in guideline_value / rule_value JSONB shaped like
-- the existing rows: {"type":"threshold","value":N,"operator":"max"}.
-- =====================================================================

-- ── agency_guidelines (7 rows) ──────────────────────────────────────

-- FANNIE — missing LTV rows
INSERT INTO agency_guidelines
    (agency, category, guideline_name, guideline_value, display_value, description, citation, effective_date, is_active)
SELECT 'fannie', 'ltv', 'ltv_max_refi_rateterm',
       '{"type":"threshold","value":95,"operator":"max","loan_purpose":"rate_term_refinance"}'::jsonb,
       '95%',
       'Maximum LTV for a rate/term (limited cash-out) refinance, primary residence 1-unit.',
       'Selling Guide B2-1.3-02', DATE '2026-06-01', true
WHERE NOT EXISTS (SELECT 1 FROM agency_guidelines
                  WHERE agency='fannie' AND guideline_name='ltv_max_refi_rateterm');

INSERT INTO agency_guidelines
    (agency, category, guideline_name, guideline_value, display_value, description, citation, effective_date, is_active)
SELECT 'fannie', 'ltv', 'ltv_max_cashout',
       '{"type":"threshold","value":80,"operator":"max","loan_purpose":"cash_out"}'::jsonb,
       '80%',
       'Maximum LTV for a cash-out refinance, primary residence 1-unit.',
       'Selling Guide B2-1.3-03', DATE '2026-06-01', true
WHERE NOT EXISTS (SELECT 1 FROM agency_guidelines
                  WHERE agency='fannie' AND guideline_name='ltv_max_cashout');

-- FANNIE — MI required above 80% LTV
INSERT INTO agency_guidelines
    (agency, category, guideline_name, guideline_value, display_value, description, citation, effective_date, is_active)
SELECT 'fannie', 'mi', 'mi_required_above_ltv',
       '{"type":"threshold","value":80,"operator":"above","unit":"ltv_percent"}'::jsonb,
       'MI required when LTV > 80%',
       'Borrower-paid mortgage insurance is required on conventional loans when LTV exceeds 80%; cancellable per HPA.',
       'Selling Guide B7-1-01', DATE '2026-06-01', true
WHERE NOT EXISTS (SELECT 1 FROM agency_guidelines
                  WHERE agency='fannie' AND guideline_name='mi_required_above_ltv');

-- VA — DTI guideline (soft, not a hard cap)
INSERT INTO agency_guidelines
    (agency, category, guideline_name, guideline_value, display_value, description, conditions, citation, effective_date, is_active)
SELECT 'va', 'dti', 'dti_back_guideline',
       '{"type":"guideline","value":41,"operator":"max"}'::jsonb,
       '41%',
       'VA back-end DTI guideline (not a hard cap); loans above 41% are allowed with sufficient residual income.',
       'Soft guideline — exceedable with residual-income compensating factors.',
       'VA Lender''s Handbook Ch. 4', DATE '2026-06-01', true
WHERE NOT EXISTS (SELECT 1 FROM agency_guidelines
                  WHERE agency='va' AND guideline_name='dti_back_guideline');

-- FHA — promote upfront MIP from conditions free-text to a structured row
INSERT INTO agency_guidelines
    (agency, category, guideline_name, guideline_value, display_value, description, citation, effective_date, is_active)
SELECT 'fha', 'mi', 'mip_upfront_pct',
       '{"type":"threshold","unit":"percent_upfront","value":1.75}'::jsonb,
       '1.75%',
       'Upfront Mortgage Insurance Premium (UFMIP) charged on all FHA loans.',
       'HUD Mortgagee Letter 2023-05', DATE '2026-06-01', true
WHERE NOT EXISTS (SELECT 1 FROM agency_guidelines
                  WHERE agency='fha' AND guideline_name='mip_upfront_pct');

-- FHA — promote annual MIP (LTV <=95%, 30yr) from conditions to a structured row
INSERT INTO agency_guidelines
    (agency, category, guideline_name, guideline_value, display_value, description, conditions, citation, effective_date, is_active)
SELECT 'fha', 'mi', 'mip_annual_lt95_30yr',
       '{"type":"threshold","unit":"percent_annual","value":0.80}'::jsonb,
       '0.80%',
       'Annual MIP rate for 30-year FHA loans with LTV at or below 95%.',
       'Loans with LTV > 95% are 0.85% annual MIP.',
       'HUD Mortgagee Letter 2023-05', DATE '2026-06-01', true
WHERE NOT EXISTS (SELECT 1 FROM agency_guidelines
                  WHERE agency='fha' AND guideline_name='mip_annual_lt95_30yr');

-- FHA — promote AUS-stretch DTI from conditions to a structured row
INSERT INTO agency_guidelines
    (agency, category, guideline_name, guideline_value, display_value, description, conditions, citation, effective_date, is_active)
SELECT 'fha', 'dti', 'dti_back_max_aus',
       '{"type":"threshold","value":57,"operator":"max"}'::jsonb,
       '57%',
       'Maximum back-end DTI for FHA with TOTAL Scorecard / AUS approval and compensating factors.',
       'Requires AUS approval; manual-underwrite cap is lower (43% base).',
       'HUD Handbook 4000.1 II.A.5.d', DATE '2026-06-01', true
WHERE NOT EXISTS (SELECT 1 FROM agency_guidelines
                  WHERE agency='fha' AND guideline_name='dti_back_max_aus');

-- ── regulatory_rules (4 rows) ───────────────────────────────────────

-- CFPB — HPML first-lien rate threshold (bps over APOR)
INSERT INTO regulatory_rules
    (authority, category, rule_name, rule_value, display_value, description, citation, effective_date, is_active)
SELECT 'cfpb', 'hpml', 'hpml_rate_threshold_1st_lien',
       '{"type":"threshold","unit":"basis_points","value":150,"operator":"max"}'::jsonb,
       '150 bps over APOR',
       'A first-lien is a Higher-Priced Mortgage Loan when its APR exceeds the Average Prime Offer Rate by 150 basis points or more.',
       '12 CFR 1026.35(a)', DATE '2013-06-01', true
WHERE NOT EXISTS (SELECT 1 FROM regulatory_rules
                  WHERE authority='cfpb' AND rule_name='hpml_rate_threshold_1st_lien');

-- CFPB — TRID 7-business-day waiting period from LE delivery
INSERT INTO regulatory_rules
    (authority, category, rule_name, rule_value, display_value, description, citation, effective_date, is_active)
SELECT 'cfpb', 'trid', 'trid_waiting_days_from_le',
       '{"type":"threshold","unit":"business_days","value":7}'::jsonb,
       '7 business days',
       'Consummation may not occur until 7 business days after the Loan Estimate is delivered or placed in the mail.',
       '12 CFR 1026.19(e)(1)(iii)(B)', DATE '2015-10-03', true
WHERE NOT EXISTS (SELECT 1 FROM regulatory_rules
                  WHERE authority='cfpb' AND rule_name='trid_waiting_days_from_le');

-- CFPB — ATR required documentation factors
INSERT INTO regulatory_rules
    (authority, category, rule_name, rule_value, display_value, description, citation, effective_date, is_active)
SELECT 'cfpb', 'atr', 'atr_required_factors',
       '{"type":"requirement","unit":"factors","value":8}'::jsonb,
       '8 factors',
       'Creditors must consider and verify 8 underwriting factors to satisfy the Ability-to-Repay rule.',
       '12 CFR 1026.43(c)(2)', DATE '2014-01-10', true
WHERE NOT EXISTS (SELECT 1 FROM regulatory_rules
                  WHERE authority='cfpb' AND rule_name='atr_required_factors');

-- CFPB — QM points-and-fees cap (% of loan amount)
INSERT INTO regulatory_rules
    (authority, category, rule_name, rule_value, display_value, description, citation, effective_date, is_active)
SELECT 'cfpb', 'qm', 'qm_points_fees_max_pct',
       '{"type":"threshold","unit":"percent","value":3,"operator":"max","basis":"loan_amount"}'::jsonb,
       '3% of loan amount',
       'Total points and fees on a Qualified Mortgage may not exceed 3% of the loan amount (for loans at or above the points-and-fees threshold).',
       '12 CFR 1026.43(e)(3)', DATE '2014-01-10', true
WHERE NOT EXISTS (SELECT 1 FROM regulatory_rules
                  WHERE authority='cfpb' AND rule_name='qm_points_fees_max_pct');
