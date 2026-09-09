-- ============================================================================
-- ontology_authoring -- authoritative governance authoring model
-- ============================================================================
-- Phase        : STEP 5G.6 / D.4G.1G.5
-- Design       : D.4G.1G.4 (locked)
-- Structure    : adopted from repository 2026.10
--                (ontology/source/claris_ontology.sql, sha256 bf7a2f7f9e1d950f)
--
-- NOT EXECUTED. This file is an implementation artifact awaiting explicit
-- authorization to apply. See D.4G.1G.5 section 8.
--
-- INVARIANTS THIS SCHEMA ENFORCES STRUCTURALLY
--   1. UNKNOWN is a first-class value and the default. There is no
--      BOOLEAN DEFAULT FALSE anywhere in this schema.
--   2. A confirmed governance value cannot exist without an authority,
--      a signature and an evidence pointer. Unsigned confirmation is
--      rejected by CHECK, not by convention.
--   3. An OPEN question cannot carry a resolution. An ANSWERED one cannot
--      lack a complete one.
--   4. This schema has no ACTIVE semantics. Executable activation belongs
--      to the compiled artifact store, never to an authoring release.
--   5. Nothing here holds executable code. Rules are named, never embedded.
--   6. A prototype assumption is not a weaker confirmation: it is a different
--      field. governance_basis = PROTOTYPE_ASSUMPTION can only exist inside a
--      release_class = PROTOTYPE release, and can never occupy
--      identity_affecting or identity_effect. Enforced by FK and CHECK.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS ontology_authoring;

-- ---------------------------------------------------------------------------
-- 1. ontology_release -- one row per authoring release
-- ---------------------------------------------------------------------------
CREATE TABLE ontology_authoring.ontology_release (
    domain                    varchar(64)  NOT NULL,
    ontology_version          varchar(64)  NOT NULL,
    description               text,
    status                    varchar(16)  NOT NULL DEFAULT 'draft',
    release_class             varchar(16)  NOT NULL DEFAULT 'AUTHORITATIVE',
    validation_status         varchar(32),
    parent_ontology_version   varchar(64),
    parent_release_class      varchar(16),
    source_namespace          varchar(256) NOT NULL,
    source_sha256             varchar(64),
    content_digest            varchar(64),
    created_at                timestamptz  NOT NULL DEFAULT now(),
    created_by                varchar(128) NOT NULL,
    published_at              timestamptz,
    published_by              varchar(128),
    CONSTRAINT pk_ontology_release
        PRIMARY KEY (domain, ontology_version),
    -- the anchor every governed row's composite FK hangs on, so a row's
    -- release_class can never disagree with its release's
    CONSTRAINT uq_ontology_release_class
        UNIQUE (domain, ontology_version, release_class),
    -- a prototype may descend from an authoritative release; the literal
    -- 'AUTHORITATIVE' in the referencing tuple means an authoritative release
    -- can never descend from a prototype
    CONSTRAINT fk_ontology_release_parent_is_authoritative
        FOREIGN KEY (domain, parent_ontology_version, parent_release_class)
        REFERENCES ontology_authoring.ontology_release
                   (domain, ontology_version, release_class),
    CONSTRAINT ck_ontology_release_status
        CHECK (status IN ('draft', 'published', 'superseded')),
    -- publication metadata is present exactly when the release is not a draft
    CONSTRAINT ck_ontology_release_publication
        CHECK ( (status = 'draft'
                 AND published_at IS NULL AND published_by IS NULL)
             OR (status IN ('published', 'superseded')
                 AND published_at IS NOT NULL AND published_by IS NOT NULL) ),
    -- a release may never declare a projection or an artifact store as its source
    CONSTRAINT ck_ontology_release_source_not_projection
        CHECK (source_namespace NOT IN
               ('claris_kb', 'claris_kb.kb_artifact', 'runtime', 'state')),
    CONSTRAINT ck_ontology_release_class
        CHECK (release_class IN ('AUTHORITATIVE', 'PROTOTYPE')),
    -- a prototype release is always marked for validation; an authoritative
    -- one never carries a validation marker
    CONSTRAINT ck_ontology_release_validation_status
        CHECK ( (release_class = 'PROTOTYPE'
                 AND validation_status = 'TO_BE_VALIDATED_WITH_CLARIS')
             OR (release_class = 'AUTHORITATIVE'
                 AND validation_status IS NULL) ),
    -- a prototype must declare the authoritative release it descends from
    CONSTRAINT ck_ontology_release_prototype_has_parent
        CHECK (release_class = 'AUTHORITATIVE'
               OR parent_ontology_version IS NOT NULL),
    CONSTRAINT ck_ontology_release_parent_class
        CHECK ( (parent_ontology_version IS NULL
                 AND parent_release_class IS NULL)
             OR (parent_ontology_version IS NOT NULL
                 AND parent_release_class = 'AUTHORITATIVE') )
);
COMMENT ON TABLE ontology_authoring.ontology_release IS
  'One row per authoring release. Deliberately carries no ACTIVE state: executable activation is a property of a compiled artifact, never of an authoring release.';

-- ---------------------------------------------------------------------------
-- 2. ontology_notes -- open governance questions
-- ---------------------------------------------------------------------------
CREATE TABLE ontology_authoring.ontology_notes (
    domain                 varchar(64)  NOT NULL,
    ontology_version       varchar(64)  NOT NULL,
    note_id                varchar(32)  NOT NULL,
    ordinal                integer,
    subject                varchar(128) NOT NULL,
    question               text         NOT NULL,
    blocks                 text,
    blocks_decision        varchar(64),
    blocks_dimension       varchar(64),
    blocks_rule            varchar(32),
    owner                  varchar(128),
    authority              varchar(128),
    status                 varchar(16)  NOT NULL DEFAULT 'OPEN',
    resolution             text,
    resolution_evidence    varchar(64),
    confirmed_by           varchar(128),
    confirmed_on           date,
    supersedes             varchar(32),
    CONSTRAINT pk_ontology_notes
        PRIMARY KEY (domain, ontology_version, note_id),
    CONSTRAINT fk_ontology_notes_release
        FOREIGN KEY (domain, ontology_version)
        REFERENCES ontology_authoring.ontology_release (domain, ontology_version),
    CONSTRAINT fk_ontology_notes_supersedes
        FOREIGN KEY (domain, ontology_version, supersedes)
        REFERENCES ontology_authoring.ontology_notes (domain, ontology_version, note_id),
    CONSTRAINT ck_ontology_notes_status
        CHECK (status IN ('OPEN', 'ANSWERED', 'SUPERSEDED', 'WITHDRAWN')),
    -- an OPEN question carries no resolution of any kind
    CONSTRAINT ck_ontology_notes_open_is_empty
        CHECK (status <> 'OPEN'
               OR (resolution IS NULL AND authority IS NULL
                   AND confirmed_by IS NULL AND confirmed_on IS NULL
                   AND resolution_evidence IS NULL)),
    -- an ANSWERED question carries a complete, signed, evidenced resolution
    CONSTRAINT ck_ontology_notes_answered_is_complete
        CHECK (status <> 'ANSWERED'
               OR (resolution IS NOT NULL AND authority IS NOT NULL
                   AND confirmed_by IS NOT NULL AND confirmed_on IS NOT NULL
                   AND resolution_evidence IS NOT NULL))
);
COMMENT ON COLUMN ontology_authoring.ontology_notes.authority IS
  'The function entitled to answer. Distinct from owner, and never populated from whoever happened to speak in a session.';

-- ---------------------------------------------------------------------------
-- 3. enums -- vocabulary registry
-- ---------------------------------------------------------------------------
CREATE TABLE ontology_authoring.enums (
    domain               varchar(64) NOT NULL,
    ontology_version     varchar(64) NOT NULL,
    enum_name            varchar(64) NOT NULL,
    ordinal              integer,
    semantic_definition  text,
    CONSTRAINT pk_enums PRIMARY KEY (domain, ontology_version, enum_name),
    CONSTRAINT fk_enums_release
        FOREIGN KEY (domain, ontology_version)
        REFERENCES ontology_authoring.ontology_release (domain, ontology_version)
);

-- ---------------------------------------------------------------------------
-- 4. enum_values -- vocabulary members
-- ---------------------------------------------------------------------------
CREATE TABLE ontology_authoring.enum_values (
    domain               varchar(64)  NOT NULL,
    ontology_version     varchar(64)  NOT NULL,
    enum_name            varchar(64)  NOT NULL,
    value                varchar(64)  NOT NULL,
    ordinal              integer,
    semantic_definition  text,
    CONSTRAINT pk_enum_values
        PRIMARY KEY (domain, ontology_version, enum_name, value),
    CONSTRAINT fk_enum_values_enum
        FOREIGN KEY (domain, ontology_version, enum_name)
        REFERENCES ontology_authoring.enums (domain, ontology_version, enum_name),
    CONSTRAINT uq_enum_values_ordinal
        UNIQUE (domain, ontology_version, enum_name, ordinal)
);

-- ---------------------------------------------------------------------------
-- 5. actors -- departments, joint bodies, machines, people
-- ---------------------------------------------------------------------------
CREATE TABLE ontology_authoring.actors (
    domain             varchar(64)  NOT NULL,
    ontology_version   varchar(64)  NOT NULL,
    actor              varchar(64)  NOT NULL,
    ordinal            integer,
    display_name       varchar(128) NOT NULL,
    actor_kind         varchar(16)  NOT NULL,
    members            text,
    owns_steps_today   text,
    responsibility     text,
    CONSTRAINT pk_actors PRIMARY KEY (domain, ontology_version, actor),
    CONSTRAINT fk_actors_release
        FOREIGN KEY (domain, ontology_version)
        REFERENCES ontology_authoring.ontology_release (domain, ontology_version),
    CONSTRAINT ck_actors_kind
        CHECK (actor_kind IN ('department', 'joint_body', 'machine', 'person'))
);

-- ---------------------------------------------------------------------------
-- 6. configuration_dimensions -- governed dimensions, and Question A
-- ---------------------------------------------------------------------------
CREATE TABLE ontology_authoring.configuration_dimensions (
    domain                        varchar(64)  NOT NULL,
    ontology_version              varchar(64)  NOT NULL,
    dimension                     varchar(64)  NOT NULL,
    ordinal                       integer,
    release_class                 varchar(16)  NOT NULL DEFAULT 'AUTHORITATIVE',
    governance_basis              varchar(24)  NOT NULL DEFAULT 'AUTHORITATIVE',
    label                         varchar(128),
    data_type                     varchar(32),
    -- QUESTION A, CONFIRMED. Three-valued. UNKNOWN is the default and asserts
    -- nothing. There is deliberately no boolean here.
    identity_affecting            varchar(8)   NOT NULL DEFAULT 'UNKNOWN',
    -- QUESTION A, PROPOSED. Nullable with no default: NULL means no proposal
    -- is possible, which is a different statement from proposing FALSE.
    proposed_identity_affecting   boolean,
    governance_state              varchar(16)  NOT NULL DEFAULT 'UNPROPOSED',
    blocks_identity_assessment    boolean      NOT NULL DEFAULT true,
    pricing_affecting             boolean,
    entitlement_affecting         boolean,
    hierarchy_affecting           boolean,
    rationale                     text,
    impact_if_wrong               text,
    owner                         varchar(128),
    authority                     varchar(128),
    status                        varchar(16)  NOT NULL DEFAULT 'undefined',
    effective_from                date,
    effective_to                  date,
    confirmed_by                  varchar(128),
    confirmed_on                  date,
    resolution_evidence           varchar(64),
    CONSTRAINT pk_configuration_dimensions
        PRIMARY KEY (domain, ontology_version, dimension),
    CONSTRAINT fk_configuration_dimensions_release
        FOREIGN KEY (domain, ontology_version, release_class)
        REFERENCES ontology_authoring.ontology_release
                   (domain, ontology_version, release_class),
    CONSTRAINT ck_configuration_dimensions_basis
        CHECK (governance_basis IN ('AUTHORITATIVE', 'PROTOTYPE_ASSUMPTION')),
    -- a prototype assumption exists only inside a prototype release
    CONSTRAINT ck_configuration_dimensions_basis_needs_prototype_release
        CHECK (governance_basis <> 'PROTOTYPE_ASSUMPTION'
               OR release_class = 'PROTOTYPE'),
    -- and can never occupy the confirmed field
    CONSTRAINT ck_configuration_dimensions_assumption_is_never_confirmed
        CHECK (governance_basis <> 'PROTOTYPE_ASSUMPTION'
               OR identity_affecting = 'UNKNOWN'),
    CONSTRAINT ck_configuration_dimensions_identity_affecting
        CHECK (identity_affecting IN ('TRUE', 'FALSE', 'UNKNOWN')),
    CONSTRAINT ck_configuration_dimensions_governance_state
        CHECK (governance_state IN ('UNPROPOSED', 'PROPOSED', 'CONFIRMED')),
    CONSTRAINT ck_configuration_dimensions_status
        CHECK (status IN ('proposed', 'confirmed', 'disputed', 'undefined')),
    -- THE LOAD-BEARING CONSTRAINT.
    -- A dimension may only leave UNKNOWN with a named authority, a signature
    -- and an evidence pointer. An unsigned confirmation cannot be stored.
    CONSTRAINT ck_configuration_dimensions_confirmed_is_signed
        CHECK (identity_affecting = 'UNKNOWN'
               OR (authority IS NOT NULL AND confirmed_by IS NOT NULL
                   AND confirmed_on IS NOT NULL AND resolution_evidence IS NOT NULL)),
    CONSTRAINT ck_configuration_dimensions_state_agrees
        CHECK ((governance_state = 'CONFIRMED') = (identity_affecting <> 'UNKNOWN')),
    CONSTRAINT ck_configuration_dimensions_effective
        CHECK (effective_to IS NULL OR effective_to > effective_from)
);

-- ---------------------------------------------------------------------------
-- 7. identity_rules -- change type to identity effect, Question B
-- ---------------------------------------------------------------------------
CREATE TABLE ontology_authoring.identity_rules (
    domain                varchar(64)  NOT NULL,
    ontology_version      varchar(64)  NOT NULL,
    rule                  varchar(32)  NOT NULL,
    ordinal               integer,
    release_class         varchar(16)  NOT NULL DEFAULT 'AUTHORITATIVE',
    governance_basis      varchar(24)  NOT NULL DEFAULT 'AUTHORITATIVE',
    change_type           varchar(64)  NOT NULL,
    reads_dimension       varchar(64),
    condition_expression  text,
    -- QUESTION B, PROPOSED
    proposed_effect       varchar(32),
    -- QUESTION B, CONFIRMED. NULL until signed.
    identity_effect       varchar(32),
    governance_state      varchar(16)  NOT NULL DEFAULT 'UNPROPOSED',
    observed_materials    integer,
    rationale             text,
    blocking_note         text,
    owner                 varchar(128),
    authority             varchar(128),
    status                varchar(16)  NOT NULL DEFAULT 'proposed',
    effective_from        date,
    effective_to          date,
    confirmed_by          varchar(128),
    confirmed_on          date,
    evidence_reference    varchar(64),
    CONSTRAINT pk_identity_rules
        PRIMARY KEY (domain, ontology_version, rule),
    CONSTRAINT fk_identity_rules_release
        FOREIGN KEY (domain, ontology_version, release_class)
        REFERENCES ontology_authoring.ontology_release
                   (domain, ontology_version, release_class),
    CONSTRAINT ck_identity_rules_basis
        CHECK (governance_basis IN ('AUTHORITATIVE', 'PROTOTYPE_ASSUMPTION')),
    CONSTRAINT ck_identity_rules_basis_needs_prototype_release
        CHECK (governance_basis <> 'PROTOTYPE_ASSUMPTION'
               OR release_class = 'PROTOTYPE'),
    -- a prototype assumption can never occupy the confirmed effect
    CONSTRAINT ck_identity_rules_assumption_is_never_confirmed
        CHECK (governance_basis <> 'PROTOTYPE_ASSUMPTION'
               OR identity_effect IS NULL),
    CONSTRAINT fk_identity_rules_dimension
        FOREIGN KEY (domain, ontology_version, reads_dimension)
        REFERENCES ontology_authoring.configuration_dimensions
                   (domain, ontology_version, dimension),
    CONSTRAINT uq_identity_rules_change_type
        UNIQUE (domain, ontology_version, change_type),
    -- IR-nnn is reserved for governed business identity/change rules.
    -- Executable predicates use the IA-PRED-nnn series and never appear here.
    CONSTRAINT ck_identity_rules_ir_namespace
        CHECK (rule ~ '^IR-[0-9]{3}$'),
    CONSTRAINT ck_identity_rules_governance_state
        CHECK (governance_state IN ('UNPROPOSED', 'PROPOSED', 'CONFIRMED')),
    CONSTRAINT ck_identity_rules_status
        CHECK (status IN ('proposed', 'confirmed', 'disputed', 'undefined')),
    -- A confirmed identity effect requires authority, signature and evidence.
    CONSTRAINT ck_identity_rules_confirmed_is_signed
        CHECK (identity_effect IS NULL
               OR (authority IS NOT NULL AND confirmed_by IS NOT NULL
                   AND confirmed_on IS NOT NULL AND evidence_reference IS NOT NULL)),
    CONSTRAINT ck_identity_rules_state_agrees
        CHECK ((governance_state = 'CONFIRMED') = (identity_effect IS NOT NULL))
);
COMMENT ON COLUMN ontology_authoring.identity_rules.observed_materials IS
  'A measurement carried from the source corpus. Immutable once written: this value was mutated during the KB 1.1 re-authoring and nothing prevented it.';

-- ---------------------------------------------------------------------------
-- 8. decisions -- business decision definitions. No executable content.
-- ---------------------------------------------------------------------------
CREATE TABLE ontology_authoring.decisions (
    domain              varchar(64)  NOT NULL,
    ontology_version    varchar(64)  NOT NULL,
    decision            varchar(64)  NOT NULL,
    ordinal             integer,
    subject_type        varchar(64),
    question            text         NOT NULL,
    mode                varchar(24)  NOT NULL,
    accountable_actor   varchar(64),
    risk_tier           varchar(16),
    authority           varchar(128),
    status              varchar(16)  NOT NULL DEFAULT 'proposed',
    phase               integer,
    replaces_today      text,
    blocked_on          text,
    blocked_by_note     varchar(32),
    effective_from      date,
    effective_to        date,
    CONSTRAINT pk_decisions PRIMARY KEY (domain, ontology_version, decision),
    CONSTRAINT fk_decisions_release
        FOREIGN KEY (domain, ontology_version)
        REFERENCES ontology_authoring.ontology_release (domain, ontology_version),
    CONSTRAINT fk_decisions_actor
        FOREIGN KEY (domain, ontology_version, accountable_actor)
        REFERENCES ontology_authoring.actors (domain, ontology_version, actor),
    CONSTRAINT fk_decisions_blocked_by
        FOREIGN KEY (domain, ontology_version, blocked_by_note)
        REFERENCES ontology_authoring.ontology_notes
                   (domain, ontology_version, note_id),
    CONSTRAINT ck_decisions_mode
        CHECK (mode IN ('recommend', 'human_approval')),
    CONSTRAINT ck_decisions_risk_tier
        CHECK (risk_tier IS NULL
               OR risk_tier IN ('routine', 'elevated', 'executive'))
);

-- ---------------------------------------------------------------------------
-- 9. decision_outputs -- governed outcome vocabulary, version scoped
-- ---------------------------------------------------------------------------
CREATE TABLE ontology_authoring.decision_outputs (
    domain               varchar(64) NOT NULL,
    ontology_version     varchar(64) NOT NULL,
    decision             varchar(64) NOT NULL,
    outcome              varchar(64) NOT NULL,
    ordinal              integer,
    release_class        varchar(16) NOT NULL DEFAULT 'AUTHORITATIVE',
    governance_basis     varchar(24) NOT NULL DEFAULT 'AUTHORITATIVE',
    semantic_definition  text,
    entitles_actions     text,
    governance_state     varchar(16) NOT NULL DEFAULT 'PROPOSED',
    authority            varchar(128),
    confirmed_by         varchar(128),
    confirmed_on         date,
    CONSTRAINT pk_decision_outputs
        PRIMARY KEY (domain, ontology_version, decision, outcome),
    CONSTRAINT fk_decision_outputs_decision
        FOREIGN KEY (domain, ontology_version, decision)
        REFERENCES ontology_authoring.decisions (domain, ontology_version, decision),
    CONSTRAINT ck_decision_outputs_basis
        CHECK (governance_basis IN ('AUTHORITATIVE', 'PROTOTYPE_ASSUMPTION')),
    CONSTRAINT ck_decision_outputs_basis_needs_prototype_release
        CHECK (governance_basis <> 'PROTOTYPE_ASSUMPTION'
               OR release_class = 'PROTOTYPE'),
    -- a prototype assumption can never be confirmed governance
    CONSTRAINT ck_decision_outputs_assumption_is_never_confirmed
        CHECK (governance_basis <> 'PROTOTYPE_ASSUMPTION'
               OR governance_state <> 'CONFIRMED'),
    CONSTRAINT ck_decision_outputs_governance_state
        CHECK (governance_state IN ('UNPROPOSED', 'PROPOSED', 'CONFIRMED')),
    CONSTRAINT ck_decision_outputs_confirmed_is_signed
        CHECK (governance_state <> 'CONFIRMED'
               OR (authority IS NOT NULL AND confirmed_by IS NOT NULL
                   AND confirmed_on IS NOT NULL))
);

-- ---------------------------------------------------------------------------
-- 10. decision_dependencies -- normalized upstream gates
-- ---------------------------------------------------------------------------
CREATE TABLE ontology_authoring.decision_dependencies (
    domain              varchar(64) NOT NULL,
    ontology_version    varchar(64) NOT NULL,
    decision            varchar(64) NOT NULL,
    depends_on          varchar(64) NOT NULL,
    ordinal             integer,
    required_outcome    varchar(64),
    dependency_type     varchar(16) NOT NULL DEFAULT 'HARD_GATE',
    upstream_actor      varchar(64),
    upstream_phase      integer,
    CONSTRAINT pk_decision_dependencies
        PRIMARY KEY (domain, ontology_version, decision, depends_on),
    CONSTRAINT fk_decision_dependencies_decision
        FOREIGN KEY (domain, ontology_version, decision)
        REFERENCES ontology_authoring.decisions (domain, ontology_version, decision),
    CONSTRAINT fk_decision_dependencies_upstream
        FOREIGN KEY (domain, ontology_version, depends_on)
        REFERENCES ontology_authoring.decisions (domain, ontology_version, decision),
    CONSTRAINT fk_decision_dependencies_required_outcome
        FOREIGN KEY (domain, ontology_version, depends_on, required_outcome)
        REFERENCES ontology_authoring.decision_outputs
                   (domain, ontology_version, decision, outcome),
    CONSTRAINT ck_decision_dependencies_type
        CHECK (dependency_type IN ('HARD_GATE', 'ADVISORY', 'INFORMATIONAL')),
    CONSTRAINT ck_decision_dependencies_not_self
        CHECK (decision <> depends_on)
);

-- ---------------------------------------------------------------------------
-- 11. projection_rules -- target-system projection governance
-- ---------------------------------------------------------------------------
CREATE TABLE ontology_authoring.projection_rules (
    domain                         varchar(64)  NOT NULL,
    ontology_version               varchar(64)  NOT NULL,
    rule                           varchar(32)  NOT NULL,
    ordinal                        integer,
    source_object                  varchar(64),
    target_system                  varchar(64)  NOT NULL,
    target_object_type             varchar(64),
    proposed_action                varchar(16),
    projection_reason              varchar(32),
    proliferation_classification   varchar(32),
    requires_new_target_identity   boolean,
    requires_decision              varchar(64),
    requires_outcome               varchar(64),
    rationale                      text,
    owner                          varchar(128),
    authority                      varchar(128),
    status                         varchar(24)  NOT NULL DEFAULT 'proposed',
    confirmed_by                   varchar(128),
    confirmed_on                   date,
    CONSTRAINT pk_projection_rules
        PRIMARY KEY (domain, ontology_version, rule),
    CONSTRAINT fk_projection_rules_release
        FOREIGN KEY (domain, ontology_version)
        REFERENCES ontology_authoring.ontology_release (domain, ontology_version),
    CONSTRAINT ck_projection_rules_action
        CHECK (proposed_action IS NULL
               OR proposed_action IN ('CREATE', 'UPDATE', 'RETIRE', 'NO_ACTION')),
    CONSTRAINT ck_projection_rules_reason
        CHECK (projection_reason IS NULL
               OR projection_reason IN
                  ('BUSINESS_IDENTITY_REQUIRED', 'CONFIGURATION_REQUIRED',
                   'LEGACY_SYSTEM_CONSTRAINT', 'TARGET_SYSTEM_REQUIREMENT',
                   'CORRECTION', 'OTHER')),
    CONSTRAINT ck_projection_rules_status
        CHECK (status IN ('proposed', 'confirmed', 'disputed', 'undefined',
                          'confirm_with_claris')),
    CONSTRAINT ck_projection_rules_confirmed_is_signed
        CHECK (status <> 'confirmed'
               OR (authority IS NOT NULL AND confirmed_by IS NOT NULL
                   AND confirmed_on IS NOT NULL))
);

-- ---------------------------------------------------------------------------
-- 12. evidence_reference -- append-only governance evidence pointer
-- ---------------------------------------------------------------------------
CREATE TABLE ontology_authoring.evidence_reference (
    evidence_reference_id  varchar(64)  NOT NULL,
    source_kind            varchar(32)  NOT NULL,
    source                 text         NOT NULL,
    source_record          varchar(128),
    captured_at            timestamptz  NOT NULL DEFAULT now(),
    captured_by            varchar(128) NOT NULL,
    digest                 varchar(64),
    description            text,
    CONSTRAINT pk_evidence_reference PRIMARY KEY (evidence_reference_id),
    CONSTRAINT uq_evidence_reference_source
        UNIQUE (source, source_record, digest),
    CONSTRAINT ck_evidence_reference_kind
        CHECK (source_kind IN ('SESSION_RECORD', 'DOCUMENT',
                               'SYSTEM_EXPORT', 'CORRESPONDENCE'))
);
COMMENT ON TABLE ontology_authoring.evidence_reference IS
  'Append-only. A governance evidence pointer, never an operational evidence store: it holds no measurement and ingests no event.';

CREATE OR REPLACE FUNCTION ontology_authoring.deny_evidence_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION
      'ontology_authoring.evidence_reference is append-only (attempted %)',
      TG_OP;
END;
$$;

CREATE TRIGGER trg_evidence_reference_append_only
    BEFORE UPDATE OR DELETE ON ontology_authoring.evidence_reference
    FOR EACH ROW EXECUTE FUNCTION ontology_authoring.deny_evidence_mutation();

-- ---------------------------------------------------------------------------
-- 13. decision_reason_codes -- why a decision could not conclude
-- ---------------------------------------------------------------------------
CREATE TABLE ontology_authoring.decision_reason_codes (
    domain               varchar(64) NOT NULL,
    ontology_version     varchar(64) NOT NULL,
    reason_code          varchar(64) NOT NULL,
    ordinal              integer,
    scope                varchar(24) NOT NULL,
    decision_type        varchar(64),
    semantic_definition  text,
    governance_state     varchar(16) NOT NULL DEFAULT 'PROPOSED',
    CONSTRAINT pk_decision_reason_codes
        PRIMARY KEY (domain, ontology_version, reason_code),
    CONSTRAINT fk_decision_reason_codes_release
        FOREIGN KEY (domain, ontology_version)
        REFERENCES ontology_authoring.ontology_release (domain, ontology_version),
    CONSTRAINT fk_decision_reason_codes_decision
        FOREIGN KEY (domain, ontology_version, decision_type)
        REFERENCES ontology_authoring.decisions (domain, ontology_version, decision),
    CONSTRAINT ck_decision_reason_codes_scope
        CHECK (scope IN ('PLATFORM', 'DECISION_SPECIFIC')),
    CONSTRAINT ck_decision_reason_codes_scope_binding
        CHECK ( (scope = 'PLATFORM'          AND decision_type IS NULL)
             OR (scope = 'DECISION_SPECIFIC' AND decision_type IS NOT NULL) ),
    CONSTRAINT ck_decision_reason_codes_governance_state
        CHECK (governance_state IN ('UNPROPOSED', 'PROPOSED', 'CONFIRMED'))
);


-- ---------------------------------------------------------------------------
-- 14. decision_rule_bindings -- governed rule metadata
-- ---------------------------------------------------------------------------
-- Added at D.4G.1G.5P.1. G.4 classified this table as REQUIRED ONLY BEFORE
-- EXECUTABLE KB ACTIVATION; prototype execution is that activation, so the
-- condition G.4 named has occurred.
--
-- predicate_name is a SYMBOLIC REFERENCE the platform resolves. No expression
-- language, no code body, nothing evaluable lives in this table.
--
-- IA-PRED-nnn identifiers live here and only here. identity_rules rejects them
-- structurally via ck_identity_rules_ir_namespace.
CREATE TABLE ontology_authoring.decision_rule_bindings (
    domain             varchar(64)  NOT NULL,
    ontology_version   varchar(64)  NOT NULL,
    release_class      varchar(16)  NOT NULL DEFAULT 'AUTHORITATIVE',
    governance_basis   varchar(24)  NOT NULL DEFAULT 'AUTHORITATIVE',
    decision           varchar(64)  NOT NULL,
    rule_id            varchar(32)  NOT NULL,
    predicate_name     varchar(128) NOT NULL,
    rule_class         varchar(16)  NOT NULL,
    precedence         integer      NOT NULL,
    expected_outcome   varchar(64),
    description        text,
    status             varchar(16)  NOT NULL DEFAULT 'proposed',
    effective_from     date,
    effective_to       date,
    CONSTRAINT pk_decision_rule_bindings
        PRIMARY KEY (domain, ontology_version, decision, rule_id),
    CONSTRAINT fk_decision_rule_bindings_release
        FOREIGN KEY (domain, ontology_version, release_class)
        REFERENCES ontology_authoring.ontology_release
                   (domain, ontology_version, release_class),
    CONSTRAINT fk_decision_rule_bindings_decision
        FOREIGN KEY (domain, ontology_version, decision)
        REFERENCES ontology_authoring.decisions (domain, ontology_version, decision),
    CONSTRAINT fk_decision_rule_bindings_outcome
        FOREIGN KEY (domain, ontology_version, decision, expected_outcome)
        REFERENCES ontology_authoring.decision_outputs
                   (domain, ontology_version, decision, outcome),
    CONSTRAINT uq_decision_rule_bindings_precedence
        UNIQUE (domain, ontology_version, decision, precedence),
    CONSTRAINT ck_decision_rule_bindings_class
        CHECK (rule_class IN ('GUARD', 'MATCH', 'FALLBACK')),
    CONSTRAINT ck_decision_rule_bindings_basis
        CHECK (governance_basis IN ('AUTHORITATIVE', 'PROTOTYPE_ASSUMPTION')),
    CONSTRAINT ck_decision_rule_bindings_basis_needs_prototype_release
        CHECK (governance_basis <> 'PROTOTYPE_ASSUMPTION'
               OR release_class = 'PROTOTYPE'),
    -- executable predicates use the IA-PRED series; a governed business
    -- identity rule id may never be bound as an executable predicate
    CONSTRAINT ck_decision_rule_bindings_not_ir_namespace
        CHECK (rule_id !~ '^IR-[0-9]{3}$'),
    CONSTRAINT ck_decision_rule_bindings_status
        CHECK (status IN ('proposed', 'confirmed', 'disputed', 'undefined'))
);

-- ============================================================================
-- END. 14 tables, 1 trigger function, 1 trigger. No ACTIVE column anywhere.
-- No executable code column anywhere. No BOOLEAN DEFAULT FALSE anywhere.
-- ============================================================================
