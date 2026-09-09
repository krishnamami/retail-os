-- =====================================================================
-- Fold State Logic — Property-Level Evaluation Algorithm
-- =====================================================================
-- Purpose: Deterministically resolve fold_state for each (subject, property) pair
--          at decision_horizon T
-- Algorithm: effective_at → max effective_at → select all at that max → check values
-- =====================================================================

CREATE OR REPLACE FUNCTION runtime.fold_resolve_value(
  p_decision_horizon timestamptz,
  p_subject_type TEXT,
  p_subject_id TEXT,
  p_property_name TEXT
)
RETURNS jsonb AS $$
DECLARE
  v_applicable_assertions RECORD;
  v_max_effective_at timestamptz;
  v_count_at_max INTEGER;
  v_distinct_values INTEGER;
  v_fold_state TEXT;
  v_resolved_value TEXT;
  v_value_type TEXT;
  v_effective_at TEXT;
  v_latest_arrival_at TEXT;
  v_basis_ids uuid[];
  v_result jsonb;
BEGIN
  -- =====================================================================
  -- Step 1: Select Assertions applicable to (subject, property, horizon)
  -- =====================================================================
  -- Criteria:
  -- - subject_type and subject_id match
  -- - property_name matches
  -- - arrival_at <= decision_horizon
  -- - effective_at <= decision_horizon

  -- Step 2: Find MAX(effective_at) among applicable Assertions
  SELECT MAX(effective_at)
  INTO v_max_effective_at
  FROM runtime.assertion
  WHERE subject_type = p_subject_type
    AND subject_id = p_subject_id
    AND property_name = p_property_name
    AND arrival_at <= p_decision_horizon
    AND effective_at <= p_decision_horizon;

  -- Step 3: If no Assertions exist, fold_state = UNREPORTED
  IF v_max_effective_at IS NULL THEN
    v_fold_state := 'UNREPORTED';
    v_resolved_value := NULL;
    v_value_type := NULL;
    v_effective_at := NULL;
    v_latest_arrival_at := NULL;
    v_basis_ids := ARRAY[]::uuid[];
  ELSE
    -- Step 4: Select ALL Assertions at max(effective_at)
    SELECT
      COUNT(*),
      COUNT(DISTINCT asserted_value),
      MAX(arrival_at),
      array_agg(DISTINCT assertion_id)
    INTO
      v_count_at_max,
      v_distinct_values,
      v_latest_arrival_at,
      v_basis_ids
    FROM runtime.assertion
    WHERE subject_type = p_subject_type
      AND subject_id = p_subject_id
      AND property_name = p_property_name
      AND arrival_at <= p_decision_horizon
      AND effective_at <= p_decision_horizon
      AND effective_at = v_max_effective_at;

    -- Step 5: Determine distinct business values
    -- Step 6: Single value → ESTABLISHED
    IF v_distinct_values = 1 THEN
      v_fold_state := 'ESTABLISHED';
      SELECT asserted_value, value_type
      INTO v_resolved_value, v_value_type
      FROM runtime.assertion
      WHERE subject_type = p_subject_type
        AND subject_id = p_subject_id
        AND property_name = p_property_name
        AND arrival_at <= p_decision_horizon
        AND effective_at <= p_decision_horizon
        AND effective_at = v_max_effective_at
      LIMIT 1;
      v_effective_at := v_max_effective_at::TEXT;

    -- Step 7: Multiple incompatible values → CONTRADICTED
    ELSIF v_distinct_values > 1 THEN
      v_fold_state := 'CONTRADICTED';
      v_resolved_value := NULL;
      v_value_type := NULL;
      v_effective_at := v_max_effective_at::TEXT;
      -- basis_ids already set to all conflicting assertions

    ELSE
      -- Unexpected internal state
      RAISE EXCEPTION 'Internal Fold algorithm error: assertion count % but distinct values %',
        v_count_at_max, v_distinct_values;
    END IF;
  END IF;

  -- =====================================================================
  -- Build result JSONB
  -- =====================================================================
  v_result := jsonb_build_object(
    'fold_state', v_fold_state,
    'resolved_value', COALESCE(to_jsonb(v_resolved_value), NULL::jsonb),
    'property_value_type', COALESCE(v_value_type, NULL::TEXT),
    'effective_at', COALESCE(v_effective_at, NULL::TEXT),
    'latest_known_arrival_at', COALESCE(v_latest_arrival_at::TEXT, NULL::TEXT),
    'basis_assertion_ids', jsonb_agg(
      to_jsonb(basis_id)
      ORDER BY basis_id
    ) FILTER (WHERE basis_id IS NOT NULL)
  );

  -- Handle NULL basis_ids edge case
  IF v_basis_ids IS NULL OR array_length(v_basis_ids, 1) IS NULL THEN
    v_result := jsonb_set(v_result, '{basis_assertion_ids}', '[]'::jsonb);
  ELSE
    v_result := jsonb_set(
      v_result,
      '{basis_assertion_ids}',
      jsonb_agg(to_jsonb(basis_id) ORDER BY basis_id)
        FILTER (WHERE basis_id IS NOT NULL)
    );
  END IF;

  -- Direct array insertion (simpler approach)
  IF v_basis_ids IS NOT NULL AND array_length(v_basis_ids, 1) > 0 THEN
    v_result := jsonb_set(
      v_result,
      '{basis_assertion_ids}',
      jsonb_build_array(
        (SELECT jsonb_agg(to_jsonb(id) ORDER BY id)
         FROM UNNEST(v_basis_ids) AS id)
      )
    );
  ELSE
    v_result := jsonb_set(v_result, '{basis_assertion_ids}', '[]'::jsonb);
  END IF;

  RETURN v_result;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- =====================================================================
-- Helper: Aggregate property basis_assertion_ids to subject level
-- =====================================================================
CREATE OR REPLACE FUNCTION runtime.aggregate_basis_ids(
  p_folded_properties jsonb
)
RETURNS uuid[] AS $$
DECLARE
  v_result uuid[] := ARRAY[]::uuid[];
  v_prop jsonb;
  v_id TEXT;
BEGIN
  FOR v_prop IN SELECT jsonb_array_elements(p_folded_properties)
  LOOP
    FOR v_id IN SELECT jsonb_array_elements_text(v_prop->'basis_assertion_ids')
    LOOP
      v_result := array_append(v_result, v_id::uuid);
    END LOOP;
  END LOOP;
  RETURN array_agg(DISTINCT elem) FROM UNNEST(v_result) AS elem;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- =====================================================================
-- Helper: Compute subject-level fold_status from properties
-- =====================================================================
CREATE OR REPLACE FUNCTION runtime.compute_subject_fold_status(
  p_folded_properties jsonb
)
RETURNS TEXT AS $$
DECLARE
  v_fold_states TEXT[];
BEGIN
  SELECT array_agg(DISTINCT (elem->>'fold_state')::TEXT)
  INTO v_fold_states
  FROM jsonb_array_elements(p_folded_properties) AS elem;

  IF 'CONTRADICTED' = ANY(v_fold_states) THEN
    RETURN 'CONTRADICTED';
  ELSIF 'EXPLICITLY_UNDEFINED' = ANY(v_fold_states) THEN
    RETURN 'EXPLICITLY_UNDEFINED';
  ELSIF 'UNREPORTED' = ANY(v_fold_states) THEN
    RETURN 'UNREPORTED';
  ELSE
    RETURN 'ESTABLISHED';
  END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
