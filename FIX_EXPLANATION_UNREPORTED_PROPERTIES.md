# CRITICAL FIX: UNREPORTED Properties Filtered by UNNEST

## Problem Diagnosis

The fold function was correctly computing UNREPORTED properties (with empty basis_ids = `[]`), but they were being **silently dropped** during the subject aggregation step.

### Evidence from Diagnostic Results

**STEP 5 Output:**
```
fold_snapshot_count: 51 ✓
total_property_states: 107 ✗ (expected 177)
established_count: 107 ✓
unreported_count: 0 ✗ (expected 70)
new_snapshots_inserted: 51 ✓
```

**STEP 7 Output:**
```
Only: ESTABLISHED = 107
Missing: UNREPORTED = 70 (100% missing)
```

**STEP 8 (SKU-006 technical_review_result):**
```
Result: NULL (property doesn't exist in snapshot)
Expected: UNREPORTED with basis_count = 0
```

This indicates that:
1. The fold function INSERT worked (51 snapshots created)
2. But the snapshots contain ONLY ESTABLISHED properties
3. All UNREPORTED properties were filtered out during computation

## Root Cause: CROSS JOIN with UNNEST

In the `subject_snapshots` CTE (line ~256-258), the code was:

```sql
FROM property_entries,
     LATERAL UNNEST(basis_ids) AS basis_id
GROUP BY subject_type, subject_id
```

**Why this fails for UNREPORTED properties:**

1. For ESTABLISHED properties: `basis_ids` = `[uuid1, uuid2, ...]` (non-empty array)
   - UNNEST produces rows (one per UUID)
   - Property is included in aggregation ✓

2. For UNREPORTED properties: `basis_ids` = `[]` (empty array)
   - UNNEST produces NO rows (empty array expands to nothing)
   - Property_entry never reaches the GROUP BY clause
   - Property is silently dropped ✗

### Visual Example

**Table: property_entries before aggregation**
```
subject_id | property_name              | basis_ids
-----------|---------------------------|------------------
SKU-006    | pricing_confirmed          | [uuid1]
SKU-006    | pricing_status             | [uuid2]
SKU-006    | technical_review_result    | []             ← UNREPORTED
SKU-013    | pricing_confirmed          | [uuid3]
SKU-013    | technical_review_result    | [uuid4]
```

**When CROSS JOIN UNNEST applied:**
```
FROM property_entries, LATERAL UNNEST(basis_ids) AS basis_id

Result: Only rows where basis_ids is non-empty
  ↓
SKU-006 | pricing_confirmed       [included in GROUP BY]
SKU-006 | pricing_status          [included in GROUP BY]
SKU-006 | technical_review_result [DROPPED - UNNEST returns no rows!]
SKU-013 | pricing_confirmed       [included in GROUP BY]
SKU-013 | technical_review_result [included in GROUP BY]

Aggregation result per subject:
SKU-006: 2 properties (missing technical_review_result)
SKU-013: 2 properties
```

## The Solution: LEFT JOIN LATERAL UNNEST

Change line ~257 from:
```sql
FROM property_entries,
     LATERAL UNNEST(basis_ids) AS basis_id
```

To:
```sql
FROM property_entries
LEFT JOIN LATERAL UNNEST(basis_ids) AS basis_id ON true
```

**Why this works:**

1. `LEFT JOIN LATERAL UNNEST` preserves all rows from `property_entries`
2. When `basis_ids` is empty, UNNEST still produces no rows, BUT the LEFT JOIN keeps the property_entry row
3. The NULL basis_id is handled by the FILTER clause: `FILTER (WHERE basis_id IS NOT NULL)`
4. UNREPORTED properties are now included in folded_properties aggregation ✓

### Corrected Aggregation Result

**When LEFT JOIN LATERAL UNNEST applied:**
```
FROM property_entries
LEFT JOIN LATERAL UNNEST(basis_ids) AS basis_id ON true
GROUP BY subject_type, subject_id

Result: All property_entries included, even with empty basis_ids
  ↓
SKU-006 | pricing_confirmed          [included in GROUP BY]
SKU-006 | pricing_status             [included in GROUP BY]
SKU-006 | technical_review_result    [INCLUDED via LEFT JOIN!]
SKU-013 | pricing_confirmed          [included in GROUP BY]
SKU-013 | technical_review_result    [included in GROUP BY]

Aggregation result per subject:
SKU-006: 3 properties ✓ (includes technical_review_result: UNREPORTED)
SKU-013: 2 properties
Total: 5 properties (correct)
```

## Expected Results After Fix

**STEP 2 of PGADMIN_FOLD_RUN_1_FIXED_UNREPORTED.sql should return:**

```
Fold Run #1 Output:
  fold_snapshot_count: 51 ✓
  total_property_states: 177 ✓ (107 + 70)
  established_count: 107 ✓
  unreported_count: 70 ✓
  new_snapshots_inserted: 51 ✓

STEP 3 Validation:
  V1: Snapshot count = 51 ✓
  V2: ESTABLISHED = 107, UNREPORTED = 70 ✓
  V3: config=22, launch=13, material=3, sku=13 ✓
  V4: SKU-006 technical_review_result = UNREPORTED, basis_count=0 ✓
  V5: SKU-013 technical_review_result = ESTABLISHED, basis_count=1 ✓
  V6: KB-v1.0.0, POLICY-v1.0.0 ✓
  V7: 51 total, 51 non_null ✓
  V8: 107 referenced assertions ✓
  V9: 0 (no violations) ✓
  V10: 0 (no violations) ✓
  V11: 107 total assertions ✓
  V12: ESTABLISHED=51, UNREPORTED=51 ✓
```

## SQL Change Summary

**File:** fold_snapshot_at_horizon function, subject_snapshots CTE (line ~257)

**Before (BROKEN):**
```sql
SELECT
  subject_type,
  subject_id,
  jsonb_agg(property_json ORDER BY property_json->>'property_name') AS folded_properties,
  array_agg(DISTINCT basis_id ORDER BY basis_id) FILTER (WHERE basis_id IS NOT NULL) AS all_basis_ids,
  CASE ... END AS computed_fold_status
FROM property_entries,
     LATERAL UNNEST(basis_ids) AS basis_id  ← CROSS JOIN filters out empty arrays
GROUP BY subject_type, subject_id
```

**After (FIXED):**
```sql
SELECT
  subject_type,
  subject_id,
  jsonb_agg(property_json ORDER BY property_json->>'property_name') AS folded_properties,
  array_agg(DISTINCT basis_id ORDER BY basis_id) FILTER (WHERE basis_id IS NOT NULL) AS all_basis_ids,
  CASE ... END AS computed_fold_status
FROM property_entries
LEFT JOIN LATERAL UNNEST(basis_ids) AS basis_id ON true  ← LEFT JOIN preserves empty arrays
GROUP BY subject_type, subject_id
```

## Execution Instructions

1. **Run:** PGADMIN_FOLD_RUN_1_FIXED_UNREPORTED.sql (includes DELETE cleanup + functions + Fold Run #1 + 12 validations)
2. **Expected:** All 12 validations PASS with correct property counts
3. **Verify:** 
   - total_property_states = 177
   - unreported_count = 70
   - V2 shows both ESTABLISHED and UNREPORTED
   - V4 shows SKU-006 with UNREPORTED

## Status

✅ **Fix Applied:** PGADMIN_FOLD_RUN_1_FIXED_UNREPORTED.sql ready for execution
✅ **Root Cause:** LEFT JOIN LATERAL UNNEST preserves empty-basis UNREPORTED properties
✅ **Authorization:** Covered under STEP 4I (clean failed Run #1 & re-execute corrected)

---

**Date:** 2026-09-07  
**Impact:** Enables STEP 4I validation with complete 177-property dataset including UNREPORTED state
