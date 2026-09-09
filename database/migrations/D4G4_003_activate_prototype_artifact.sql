-- ============================================================================
-- D.4G.4 -- promote the prototype artifact COMPILED -> VERIFIED -> ACTIVE
-- ============================================================================
-- RUN ONLY AFTER d4g4_verify_artifact.py exits 0.
--
-- Two separate transitions, in order, because they mean different things:
-- VERIFIED says the stored payload was independently checked against the
-- release it was compiled from; ACTIVE says it may be resolved. KB 1.1 was
-- ACTIVE while internally READY_FOR_VERIFICATION, and keeping these apart is
-- the correction.
--
-- Each UPDATE names the status it expects to find, so running this against an
-- artifact in the wrong state changes nothing rather than forcing it forward.
--
-- ACTIVATION IS SCOPED. uq_kb_artifact_one_active_per_class permits one ACTIVE
-- artifact per release_class, so this becomes the single ACTIVE PROTOTYPE
-- while KB 1.1 remains the single ACTIVE AUTHORITATIVE. v_active_kb is scoped
-- to AUTHORITATIVE and will not see this row. No existing artifact is
-- archived, retired, updated or read.
-- ============================================================================

-- 1. VERIFIED
UPDATE claris_kb.kb_artifact
SET    status = 'VERIFIED'
WHERE  kb_version = '2026.10-prototype.1'
  AND  release_class = 'PROTOTYPE'
  AND  status = 'COMPILED';

-- 2. ACTIVE
UPDATE claris_kb.kb_artifact
SET    status = 'ACTIVE'
WHERE  kb_version = '2026.10-prototype.1'
  AND  release_class = 'PROTOTYPE'
  AND  status = 'VERIFIED';

-- 3. proof: two doors, one artifact each, neither seeing the other
SELECT 'production' AS resolver, kb_version, ontology_version, status
FROM   claris_kb.v_active_kb
UNION ALL
SELECT 'prototype', kb_version, ontology_version, status
FROM   claris_kb.v_active_prototype_kb
ORDER  BY 1;

SELECT kb_version, status, release_class, governance_basis, validation_status
FROM   claris_kb.kb_artifact ORDER BY kb_version;
