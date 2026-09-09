-- ============================================================================
-- VERTICAL SLICE -- promote 2026.10-prototype.2 and retire prototype.1
-- ============================================================================
-- RUN ONLY AFTER vslice_verify_artifact.py exits 0 for 2026.10-prototype.2.
--
-- Four transitions, in this order, each naming the status it expects to find so
-- running against an artifact in the wrong state changes nothing rather than
-- forcing it forward:
--
--   1. prototype.2  COMPILED -> VERIFIED
--   2. prototype.1  ACTIVE   -> ARCHIVED      (must precede step 3)
--   3. prototype.2  VERIFIED -> ACTIVE
--
-- STEP 2 BEFORE STEP 3 IS NOT STYLE. uq_kb_artifact_one_active_per_class is a
-- partial unique index on (release_class) WHERE status='ACTIVE', so two ACTIVE
-- PROTOTYPE artifacts cannot coexist even momentarily. Activating first would
-- fail on the index; the index is doing its job.
--
-- ARCHIVED, not deleted and not rewritten. prototype.1 keeps its payload, its
-- digest 888b202b... and its row. Every decision already recorded against it --
-- there are none yet, but the rule is the rule -- stays resolvable.
--
-- THE AUTHORING RELEASE prototype.1 IS DELIBERATELY LEFT 'published'.
-- Marking it 'superseded' would make the D.4G.4 verifier's recompilation refuse
-- it, because the compiler only compiles a published release. A published
-- release is an immutable historical record; which one EXECUTES is the artifact
-- store's business, and that separation is the whole point of having two.
--
-- PRODUCTION IS NOT TOUCHED. No statement here names KB 1.0, 1.0.1 or 1.1, and
-- v_active_kb is scoped to AUTHORITATIVE, so it returns KB 1.1 throughout.
--
-- APPLY IN ONE TRANSACTION.
-- ============================================================================

-- 1. prototype.2: COMPILED -> VERIFIED
UPDATE claris_kb.kb_artifact
SET    status = 'VERIFIED'
WHERE  kb_version = '2026.10-prototype.2'
  AND  release_class = 'PROTOTYPE'
  AND  status = 'COMPILED';

-- 2. prototype.1: ACTIVE -> ARCHIVED
UPDATE claris_kb.kb_artifact
SET    status = 'ARCHIVED'
WHERE  kb_version = '2026.10-prototype.1'
  AND  release_class = 'PROTOTYPE'
  AND  status = 'ACTIVE';

-- 3. prototype.2: VERIFIED -> ACTIVE
UPDATE claris_kb.kb_artifact
SET    status = 'ACTIVE'
WHERE  kb_version = '2026.10-prototype.2'
  AND  release_class = 'PROTOTYPE'
  AND  status = 'VERIFIED';

-- ---------------------------------------------------------------------------
-- proof
-- ---------------------------------------------------------------------------
SELECT 'production' AS resolver, kb_version, ontology_version, status
FROM   claris_kb.v_active_kb
UNION ALL
SELECT 'prototype', kb_version, ontology_version, status
FROM   claris_kb.v_active_prototype_kb
ORDER  BY 1;

SELECT kb_version, status, release_class, governance_basis, validation_status,
       left(content_digest, 16) || '...' AS digest
FROM   claris_kb.kb_artifact
ORDER  BY release_class, kb_version;

-- exactly one ACTIVE per class, which is what the partial unique index permits
SELECT release_class, count(*) AS active_artifacts
FROM   claris_kb.kb_artifact
WHERE  status = 'ACTIVE'
GROUP  BY release_class
ORDER  BY 1;

-- prototype.1's payload is byte-identical to what it always was
SELECT kb_version, content_digest,
       content_digest = '888b202b179806c5d5844a0f78739cecae2634d58d6ff106c321e52b5bcde559'
           AS digest_unchanged
FROM   claris_kb.kb_artifact
WHERE  kb_version = '2026.10-prototype.1';
