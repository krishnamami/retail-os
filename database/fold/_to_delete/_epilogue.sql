  ),
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
  property_entries AS (
    SELECT
      pfr.subject_type,
      pfr.subject_id,
      jsonb_build_object(
        'property_name', pfr.property_name,
        'fold_state', pfr.fold_result->>'fold_state',
        'resolved_value', pfr.fold_result->'resolved_value',
        'property_value_type', pfr.fold_result->>'property_value_type',
        'effective_at', pfr.fold_result->>'effective_at',
        'latest_known_arrival_at', pfr.fold_result->>'latest_known_arrival_at',
        'basis_assertion_ids', pfr.fold_result->'basis_assertion_ids'
      ) AS property_json,
      COALESCE(
        (SELECT array_agg(val::uuid)
         FROM jsonb_array_elements_text(pfr.fold_result->'basis_assertion_ids') val
         WHERE val IS NOT NULL AND val != ''),
        '{}'::uuid[]
      ) AS basis_ids
    FROM property_fold_results pfr
  ),
  subject_snapshots AS (
    SELECT
      subject_type,
      subject_id,
      jsonb_agg(property_json ORDER BY property_json->>'property_name') AS folded_properties,
      array_agg(DISTINCT u.basis_id ORDER BY u.basis_id) FILTER (WHERE u.basis_id IS NOT NULL) AS all_basis_ids,
      CASE
        WHEN bool_or((property_json->>'fold_state')::TEXT = 'CONTRADICTED') THEN 'CONTRADICTED'
        WHEN bool_or((property_json->>'fold_state')::TEXT = 'EXPLICITLY_UNDEFINED') THEN 'EXPLICITLY_UNDEFINED'
        WHEN bool_or((property_json->>'fold_state')::TEXT = 'UNREPORTED') THEN 'UNREPORTED'
        ELSE 'ESTABLISHED'
      END AS computed_fold_status
    FROM property_entries pe
    LEFT JOIN LATERAL UNNEST(pe.basis_ids) AS u(basis_id) ON TRUE
    GROUP BY subject_type, subject_id
  )
  SELECT
    ss.subject_type,
    ss.subject_id,
    ss.folded_properties,
    ss.all_basis_ids,
    ss.computed_fold_status
  FROM subject_snapshots ss;

  INSERT INTO state.fold_state_snapshot (
    decision_horizon, subject_type, subject_id, fold_status,
    folded_properties, basis_assertion_ids, kb_version, policy_version,
    fold_computed_at
  )
  SELECT
    p_decision_horizon,
    subject_type,
    subject_id,
    computed_fold_status,
    folded_properties,
    all_basis_ids,
    v_kb_version,
    v_policy_version,
    CURRENT_TIMESTAMP
  FROM temp_subject_snapshots
  ON CONFLICT (decision_horizon, subject_type, subject_id)
  DO NOTHING;

  SELECT COUNT(*) INTO v_new_inserts
  FROM (
    SELECT 1
    FROM temp_subject_snapshots ss
    LEFT JOIN state.fold_state_snapshot fss
      ON fss.decision_horizon = p_decision_horizon
      AND fss.subject_type = ss.subject_type
      AND fss.subject_id = ss.subject_id
    WHERE fss.fold_state_id IS NULL
  ) t;

  SELECT COUNT(*) INTO v_replays
  FROM state.fold_state_snapshot
  WHERE decision_horizon = p_decision_horizon;

  SELECT COUNT(*) INTO v_mismatches
  FROM (
    SELECT ss.subject_type, ss.subject_id
    FROM temp_subject_snapshots ss
    INNER JOIN state.fold_state_snapshot fss
      ON fss.decision_horizon = p_decision_horizon
      AND fss.subject_type = ss.subject_type
      AND fss.subject_id = ss.subject_id
    WHERE ss.computed_fold_status IS DISTINCT FROM fss.fold_status
       OR ss.folded_properties IS DISTINCT FROM fss.folded_properties
       OR ss.all_basis_ids IS DISTINCT FROM fss.basis_assertion_ids
       OR v_kb_version IS DISTINCT FROM fss.kb_version
       OR v_policy_version IS DISTINCT FROM fss.policy_version
  ) t;

  IF v_mismatches > 0 THEN
    RAISE EXCEPTION 'Deterministic replay mismatch: % snapshots produced different content on second execution at horizon %. Assertion corpus, KB version, or policy version must have changed during fold execution (immutability violated).',
      v_mismatches, p_decision_horizon;
  END IF;

  SELECT COUNT(*) INTO v_snap_count FROM state.fold_state_snapshot
  WHERE decision_horizon = p_decision_horizon;

  SELECT
    COUNT(*) FILTER (WHERE fold_state = 'ESTABLISHED'),
    COUNT(*) FILTER (WHERE fold_state = 'UNREPORTED'),
    COUNT(*) FILTER (WHERE fold_state = 'EXPLICITLY_UNDEFINED'),
    COUNT(*) FILTER (WHERE fold_state = 'CONTRADICTED'),
    COUNT(*)
  INTO v_established_count, v_unreported_count, v_undefined_count, v_contradicted_count, v_total_properties
  FROM state.fold_state_snapshot fss,
       LATERAL jsonb_array_elements(fss.folded_properties) AS props
  WHERE fss.decision_horizon = p_decision_horizon;

  RETURN QUERY
  SELECT
    v_snap_count,
    v_total_properties,
    v_established_count,
    v_unreported_count,
    v_undefined_count,
    v_contradicted_count,
    (SELECT jsonb_object_agg(subject_type, cnt)
     FROM (
       SELECT subject_type, COUNT(DISTINCT subject_id) AS cnt
       FROM state.fold_state_snapshot
       WHERE decision_horizon = p_decision_horizon
       GROUP BY subject_type
     ) t)::TEXT,
    v_new_inserts,
    v_replays,
    v_mismatches;
END;
$function$;
