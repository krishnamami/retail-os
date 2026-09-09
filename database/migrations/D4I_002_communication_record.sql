-- ============================================================================
-- AGENT SUPPORT -- communication as business evidence
-- ============================================================================
-- WHY A TABLE AND NOT A MAIL CLIENT
--   "Finance was asked for a pricing decision on the 3rd and has not answered"
--   is a fact about a launch. A Workbench that cannot show it cannot explain
--   why a launch stalled -- and explaining stalls is the product. So a
--   communication is recorded as evidence: who was asked, by whom, why, when,
--   about which decision, and what happened to it.
--
-- NOTHING HERE SENDS ANYTHING
--   The channel vocabulary is WORKBENCH_NOTE and EMAIL_DRAFT, and the status
--   vocabulary has no SENT value. There is no SMTP, no Gmail, no external
--   integration, and no column that could claim a message left the building.
--   When sending is built later it will need its own column values and its own
--   deliberate act; it cannot be arrived at by accident from here.
--
-- NO FABRICATED PEOPLE
--   to_actor_id and from_actor_id are NULLABLE and expected to be null in this
--   prototype: every actor id in the corpus is a simulation marker, and roles
--   are what is genuinely known. ck_communication_role_present enforces that a
--   communication always names at least a recipient ROLE, so a message can
--   never be addressed to nobody.
--
-- APPEND-FIRST
--   No UPDATE path is provided for subject or body. A draft that needs changing
--   is superseded by a new draft; the audit value of the table comes from it
--   being a record of what was actually prepared, not a mutable scratchpad.
--
-- APPLY IN ONE TRANSACTION. Idempotent throughout.
-- ============================================================================

CREATE TABLE IF NOT EXISTS claris.communication (
    communication_id      varchar(64)  NOT NULL,
    subject_id            varchar(64)  NOT NULL,
    launch_id             varchar(64),
    from_actor_id         varchar(128),
    from_role             varchar(64)  NOT NULL,
    to_actor_id           varchar(128),
    to_role               varchar(64),
    channel               varchar(32)  NOT NULL,
    communication_type    varchar(32)  NOT NULL,
    related_decision_id   uuid,
    subject               varchar(256) NOT NULL,
    body                  text         NOT NULL,
    status                varchar(16)  NOT NULL DEFAULT 'DRAFT',
    created_at            timestamptz  NOT NULL DEFAULT now(),
    created_by            varchar(128) NOT NULL DEFAULT 'coordination-agent',
    governance_basis      varchar(24)  NOT NULL,
    ontology_version      varchar(64)  NOT NULL,

    CONSTRAINT pk_communication PRIMARY KEY (communication_id),

    CONSTRAINT fk_communication_decision
        FOREIGN KEY (related_decision_id)
        REFERENCES claris.decision (decision_id),

    -- the channel vocabulary IS the send guarantee: neither value describes a
    -- message that has left this system
    CONSTRAINT ck_communication_channel
        CHECK (channel IN ('WORKBENCH_NOTE', 'EMAIL_DRAFT')),

    CONSTRAINT ck_communication_type
        CHECK (communication_type IN
               ('REQUEST_EVIDENCE', 'REQUEST_DECISION',
                'ESTABLISH_DECISION_OWNER', 'RESOLVE_GOVERNANCE_AMBIGUITY',
                'NOTE')),

    -- DRAFT only. There is deliberately no SENT: adding one is a separate,
    -- visible act that has to pass review.
    CONSTRAINT ck_communication_status
        CHECK (status IN ('DRAFT', 'SUPERSEDED')),

    -- a communication must reach SOMEONE. A role is enough; a person is not
    -- required and is never invented.
    CONSTRAINT ck_communication_role_present
        CHECK (to_role IS NOT NULL OR to_actor_id IS NOT NULL),

    CONSTRAINT ck_communication_basis
        CHECK (governance_basis IN ('AUTHORITATIVE', 'PROTOTYPE_ASSUMPTION'))
);

CREATE INDEX IF NOT EXISTS ix_communication_subject
    ON claris.communication (subject_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_communication_decision
    ON claris.communication (related_decision_id)
    WHERE related_decision_id IS NOT NULL;

COMMENT ON TABLE claris.communication IS
  'Coordination recorded as business evidence: who was asked what, about which '
  'decision, and when. Append-first. Nothing in this table has been sent -- the '
  'channel vocabulary (WORKBENCH_NOTE, EMAIL_DRAFT) and the status vocabulary '
  '(DRAFT, SUPERSEDED) contain no value meaning delivered, and no external '
  'messaging integration exists.';

COMMENT ON COLUMN claris.communication.to_actor_id IS
  'NULL whenever the person is not established. Every actor id in the prototype '
  'corpus is a simulation marker, so this is expected to be NULL and to_role '
  'carries the real information. A name is never invented to fill it.';

GRANT SELECT ON claris.communication TO claris_ingestion;

-- ---------------------------------------------------------------------------
-- proof
-- ---------------------------------------------------------------------------
SELECT column_name, data_type, character_maximum_length, is_nullable
FROM   information_schema.columns
WHERE  table_schema = 'claris' AND table_name = 'communication'
ORDER  BY ordinal_position;

SELECT conname, pg_get_constraintdef(oid) AS definition
FROM   pg_constraint
WHERE  conrelid = 'claris.communication'::regclass
ORDER  BY conname;

SELECT count(*) AS communications FROM claris.communication;
