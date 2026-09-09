# STEP 4J — Fold Idempotency Verification Guide

## Objective

Execute Fold Run #2 on the **exact same decision_horizon** (2026-06-20 10:45:00+00) without deleting the 51 snapshots from Run #1.

Verify that the fold function is **deterministic and idempotent**:
- ✅ No new snapshots inserted (all 51 already exist)
- ✅ No snapshots modified (fold_computed_at unchanged)
- ✅ Property distributions identical
- ✅ replay_mismatches = 0 (determinism verified)

## Authorization Constraints

- ✅ Execute Fold Run #2 idempotency test
- ❌ DO NOT delete the 51 snapshots from Run #1
- ❌ DO NOT modify Fold function code
- ❌ DO NOT modify upstream layers (Raw, Evidence, Assertions, KB, Policy)
- ❌ DO NOT start Canonical or Decisions layers

## Key Metrics to Track

### Fold Run #2 Expected Output (10 columns)
```
fold_snapshot_count:       51 (unchanged)
total_property_states:     177 (unchanged)
established_count:         107 (unchanged)
unreported_count:          70 (unchanged)
explicitly_undefined_count: 0 (unchanged)
contradicted_count:         0 (unchanged)
subjects_by_type:          {"configuration":22,"launch":13,"material":3,"sku":13} (unchanged)
new_snapshots_inserted:    0 ← CRITICAL: Must be 0 (idempotency)
deterministic_replays:     51 (unchanged)
replay_mismatches:         0 ← CRITICAL: Must be 0 (no mutations)
```

### Critical Idempotency Indicators

**PASS if:**
- `new_snapshots_inserted = 0` (no new rows inserted)
- `replay_mismatches = 0` (no content differences detected)
- `fold_computed_at` timestamps remain identical (no row rewrites)
- Property distribution unchanged (ESTABLISHED: 107, UNREPORTED: 70)
- Upstream counts unchanged (raw: 169, evidence: 107, assertion: 107)

**FAIL if:**
- `new_snapshots_inserted > 0` (indicates duplicate handling broken)
- `replay_mismatches > 0` (indicates non-deterministic computation)
- `fold_computed_at` timestamps changed (indicates unnecessary rewrites)
- Property distribution changed (indicates computation inconsistency)

## Execution Steps

### 1. Execute PGADMIN_FOLD_RUN_2_IDEMPOTENCY_VERIFICATION.sql

Copy the entire script into your database tool and run as a single batch.

The script will output:
- STEP 1: Pre-run state (snapshot count, fold_computed_at range)
- STEP 1B: Pre-run property distribution
- STEP 1C: Pre-run upstream counts
- STEP 2: Fold Run #2 execution result (10 columns)
- STEP 3: Post-run snapshot count
- STEP 4: Post-run fold_computed_at range
- STEP 5: Post-run property distribution
- STEP 6: Post-run upstream counts
- STEP 7: Post-run subject fold status
- STEP 8: Post-run subject distribution by type
- SUMMARY: Validation comparison table

### 2. Compare Pre/Post Values

**Snapshot Count:**
- Pre-run: 51
- Post-run: Should be 51
- Pass if: Identical

**fold_computed_at Timestamps:**
- Pre-run: MIN(fold_computed_at) and MAX(fold_computed_at)
- Post-run: Should be identical to pre-run
- Pass if: Identical (no rows were updated)

**Property Distribution:**
- Pre-run: ESTABLISHED: 107, UNREPORTED: 70
- Post-run: Should be identical
- Pass if: ESTABLISHED: 107, UNREPORTED: 70

**Upstream Counts:**
- Pre-run: raw: 169, evidence: 107, assertion: 107
- Post-run: Should be identical
- Pass if: All identical (no upstream mutations)

### 3. Validate Fold Run #2 Output

Check the 10-column result from STEP 2:

| Column | Expected | Reason |
|--------|----------|--------|
| fold_snapshot_count | 51 | Same 51 subjects computed |
| total_property_states | 177 | Same 107 ESTABLISHED + 70 UNREPORTED |
| established_count | 107 | Same established properties |
| unreported_count | 70 | Same unreported properties |
| new_snapshots_inserted | **0** | ON CONFLICT DO NOTHING (all exist) |
| deterministic_replays | 51 | All 51 subjects replayed |
| replay_mismatches | **0** | Computed content matches exactly |

## What Each Step Validates

**STEP 1-1C:** Captures baseline state before Run #2
- Proves there ARE 51 existing snapshots
- Proves fold_computed_at timestamp range
- Proves upstream is unchanged

**STEP 2:** Executes Fold Run #2
- Key metric: `new_snapshots_inserted = 0` (ON CONFLICT DO NOTHING worked)
- Key metric: `replay_mismatches = 0` (computed values identical)

**STEP 3:** Verifies snapshot count unchanged
- Must be 51 (no inserts, no deletes)
- Proves idempotency at row level

**STEP 4:** Verifies timestamps unchanged
- MIN/MAX fold_computed_at must match pre-run
- Proves no rows were modified/rewritten
- If timestamps changed, indicates unnecessary UPDATE

**STEP 5:** Verifies property distribution unchanged
- Must still show ESTABLISHED: 107, UNREPORTED: 70
- Proves property computation is deterministic

**STEP 6:** Verifies upstream immutability
- All counts must match pre-run
- Proves Fold doesn't mutate upstream layers

**STEP 7-8:** Verifies subject-level structure unchanged
- Subject fold status distributions must match
- Subject type distributions must match

## Success Criteria: PASS

**ALL of the following must be true:**

1. ✅ Fold Run #2 returns without error
2. ✅ new_snapshots_inserted = 0
3. ✅ replay_mismatches = 0
4. ✅ Post-run snapshot count = 51
5. ✅ fold_computed_at timestamps identical
6. ✅ Property distribution unchanged (ESTABLISHED: 107, UNREPORTED: 70)
7. ✅ Upstream counts unchanged
8. ✅ All 9 validation steps show "PASS"

**Final Status:** `FOLD STEP 4J COMPLETE — IDEMPOTENCY VERIFIED ✓`

## Failure Criteria: FAIL

**If ANY of the following occur:**

1. ❌ Fold Run #2 throws an error
2. ❌ new_snapshots_inserted > 0 (duplicate handling broken)
3. ❌ replay_mismatches > 0 (non-deterministic computation)
4. ❌ Post-run snapshot count ≠ 51 (rows modified)
5. ❌ fold_computed_at timestamps changed (unnecessary rewrites)
6. ❌ Property distribution changed (inconsistent computation)
7. ❌ Upstream counts changed (mutation detected)

**Final Status:** `FOLD STEP 4J FAILED — <specific reason>`

## Next Steps

### If STEP 4J PASSES:
1. Document results in checklist
2. Mark idempotency as verified ✓
3. **STOP** — Do not proceed to Canonical or Decisions without separate authorization
4. Await next authorization for downstream layers

### If STEP 4J FAILS:
1. **STOP immediately**
2. Investigate which validation failed
3. Review Fold logs for error messages
4. Do NOT proceed to Canonical
5. Determine root cause before retrying

## Key Concepts

### ON CONFLICT DO NOTHING
When the fold function attempts to INSERT computed snapshots but they already exist (same decision_horizon, subject_type, subject_id), the unique constraint triggers and the INSERT silently does nothing.

This is the idempotency mechanism:
- First execution: All 51 rows INSERT successfully → new_snapshots_inserted = 51
- Second execution: All 51 rows exist → ON CONFLICT DO NOTHING → new_snapshots_inserted = 0

### Deterministic Replay
The fold function computes snapshots in two phases:
1. **Compute Phase:** Calculates property states for all (subject, property) pairs
2. **Verification Phase:** Replays the same computation to detect mutations

If ANY upstream data changed during fold execution:
- Computed snapshots would differ
- `replay_mismatches` would be > 0
- Function raises exception (immutability violation)

Second execution can re-verify that computed content matches exactly.

### fold_computed_at Immutability
The fold function records when each snapshot was computed (fold_computed_at timestamp).

In idempotent execution:
- The function attempts to INSERT but finds existing rows
- The ON CONFLICT DO NOTHING clause silently skips the insert
- Existing fold_computed_at timestamps are untouched

If fold_computed_at changes, it means:
- Rows were UPDATEd (not idempotent)
- Or old rows were deleted and new ones inserted (not idempotent)

Either case is a failure.

---

**Date:** 2026-09-07  
**Authorization:** STEP 4J Idempotency Verification  
**Status:** Ready for execution
