"""D.4G.4 -- artifact governance classification migration."""

from __future__ import annotations

import io
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MIGRATION = os.path.join(ROOT, "database", "migrations",
                         "D4G4_001_artifact_governance_classification.sql")

#: the live v_active_kb column list, in order, captured by the D.4G.4 gate.
#: CREATE OR REPLACE VIEW requires these to be unchanged; changing one would
#: force a DROP, which would cascade into v_active_decision_rules and the five
#: other ACTIVE-filtered views.
LIVE_ACTIVE_KB_COLUMNS = ["kb_version", "ontology_version", "content_digest",
                          "status", "deployed_at", "source_system"]


def _read(path):
    with io.open(path, encoding="utf-8") as handle:
        return handle.read()


def _body(sql):
    return "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))


@pytest.fixture(scope="module")
def migration():
    return _read(MIGRATION)


# ---------------------------------------------------------------------------
# safety
# ---------------------------------------------------------------------------

def test_the_migration_is_additive_only(migration):
    body = _body(migration)
    for banned in ("DROP TABLE", "DROP VIEW", "DROP COLUMN", "DROP INDEX",
                   "TRUNCATE", "DELETE FROM", "DROP SCHEMA", "CASCADE"):
        assert banned not in body, banned


def test_the_migration_never_reads_or_writes_artifact_content(migration):
    """The payloads of KB 1.0, 1.0.1 and 1.1 must survive untouched."""
    body = _body(migration)
    assert "kb_json" not in body
    assert not re.search(r"\b(UPDATE|INSERT INTO|MERGE INTO)\s+claris_kb", body)


def test_the_migration_targets_only_the_artifact_model(migration):
    body = _body(migration)
    targets = set(re.findall(r"ALTER TABLE (\S+)", body))
    assert targets == {"claris_kb.kb_artifact"}
    for untouched in ("claris.decision", "ontology.", "ontology_authoring.",
                      "raw.", "state.", "runtime."):
        assert untouched not in body


def test_v_active_decision_rules_is_not_edited(migration):
    """It chains off v_active_kb and inherits the scoping for free."""
    assert "v_active_decision_rules" not in _body(migration)


# ---------------------------------------------------------------------------
# classification
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("column,default", [
    ("release_class", "'AUTHORITATIVE'"),
    ("governance_basis", "'AUTHORITATIVE'"),
    ("validation_status", None),
])
def test_classification_columns_are_added(column, default, migration):
    added = re.search(r"ADD COLUMN IF NOT EXISTS %s\s+varchar\(\d+\)([^,;]*)"
                      % column, migration)
    assert added
    if default:
        assert "NOT NULL" in added.group(1)
        assert default in added.group(1)
    else:
        assert "NOT NULL" not in added.group(1)


def test_existing_artifacts_become_authoritative_by_default(migration):
    """The defaults are what make this non-breaking: everything deployed today
    IS production governance, and the migration says so rather than guessing."""
    for column in ("release_class", "governance_basis"):
        assert re.search(
            r"ADD COLUMN IF NOT EXISTS %s\s+varchar\(\d+\) NOT NULL\s*\n?\s*"
            r"DEFAULT 'AUTHORITATIVE'" % column, migration)


def test_basis_class_and_validation_move_together(migration):
    assert "ck_kb_artifact_basis_matches_class" in migration
    block = migration.split("ADD CONSTRAINT ck_kb_artifact_basis_matches_class")[1]
    block = block.split("END")[0]
    assert "release_class = 'AUTHORITATIVE'" in block
    assert "governance_basis = 'AUTHORITATIVE'" in block
    assert "validation_status IS NULL" in block
    assert "release_class = 'PROTOTYPE'" in block
    assert "governance_basis = 'PROTOTYPE_ASSUMPTION'" in block
    assert "validation_status = 'TO_BE_VALIDATED_WITH_CLARIS'" in block


def test_a_prototype_artifact_cannot_hide_its_status(migration):
    """There is no combination that yields a prototype without the marker."""
    block = migration.split("ADD CONSTRAINT ck_kb_artifact_basis_matches_class")[1]
    block = block.split("END")[0]
    # the only branch permitting PROTOTYPE also mandates the validation status
    prototype_branch = block[block.index("release_class = 'PROTOTYPE'"):]
    assert "TO_BE_VALIDATED_WITH_CLARIS" in prototype_branch


# ---------------------------------------------------------------------------
# activation scoping
# ---------------------------------------------------------------------------

def test_one_active_artifact_per_class_is_enforced_by_an_index(migration):
    """An index refuses the write; a view could only report it afterwards."""
    assert re.search(
        r"CREATE UNIQUE INDEX IF NOT EXISTS uq_kb_artifact_one_active_per_class\s*\n"
        r"\s*ON claris_kb\.kb_artifact \(release_class\)\s*\n"
        r"\s*WHERE status = 'ACTIVE';", migration)


def test_v_active_kb_keeps_its_exact_column_list(migration):
    """CREATE OR REPLACE requires it; changing one would force a DROP and
    cascade into every dependent ACTIVE view."""
    definition = migration.split("CREATE OR REPLACE VIEW claris_kb.v_active_kb AS")[1]
    definition = definition.split("FROM")[0]
    columns = [c.strip().rstrip(",") for c in definition.strip().split("\n")]
    columns = [c.replace("SELECT ", "").strip() for c in columns if c.strip()]
    assert columns == LIVE_ACTIVE_KB_COLUMNS


def test_v_active_kb_is_scoped_to_authoritative(migration):
    definition = migration.split("CREATE OR REPLACE VIEW claris_kb.v_active_kb AS")[1]
    definition = definition.split("COMMENT ON")[0]
    assert "release_class::text = 'AUTHORITATIVE'::text" in definition
    # still fail-closed, and the guard counts within the class
    assert "count(*)" in definition
    assert definition.count("release_class::text = 'AUTHORITATIVE'::text") == 2


def test_the_prototype_view_is_disjoint_from_production(migration):
    prototype = migration.split(
        "CREATE OR REPLACE VIEW claris_kb.v_active_prototype_kb AS")[1]
    prototype = prototype.split("COMMENT ON")[0]
    assert "release_class::text = 'PROTOTYPE'::text" in prototype
    assert "count(*)" in prototype          # fail-closed too
    assert "AUTHORITATIVE" not in prototype  # no overlap, no fallback


def test_the_prototype_view_exposes_its_classification(migration):
    """A caller reading the prototype view can see what it is holding."""
    prototype = migration.split(
        "CREATE OR REPLACE VIEW claris_kb.v_active_prototype_kb AS")[1]
    prototype = prototype.split("FROM")[0]
    for column in ("release_class", "governance_basis", "validation_status"):
        assert column in prototype


def test_nothing_reads_the_prototype_view_by_default(migration):
    """It is a separate door, not a fallback: production never selects it."""
    active = migration.split("CREATE OR REPLACE VIEW claris_kb.v_active_kb AS")[1]
    active = active.split("COMMENT ON")[0]
    assert "prototype" not in active.lower()


# ---------------------------------------------------------------------------
# rerun safety -- D.4G.4 migration correction
# ---------------------------------------------------------------------------

def test_every_add_constraint_is_guarded(migration):
    """ADD CONSTRAINT has no IF NOT EXISTS form, so it needs an explicit guard.

    A live rerun failed on exactly this: the columns skipped cleanly via
    IF NOT EXISTS, then ADD CONSTRAINT aborted the transaction.
    """
    body = _body(migration)
    unguarded = re.findall(r"(?<!    )ALTER TABLE[^;]*ADD CONSTRAINT", body, re.S)
    assert unguarded == []
    assert body.count("$guard$") == 4          # two DO blocks, opened and closed
    assert body.count("FROM pg_constraint") == 2


def test_the_guard_tolerates_the_earlier_constraint_name(migration):
    """One constraint was pasted into chat under a different name before this
    file existed. The guard accepts either spelling and adds neither twice."""
    guard = migration.split("ck_kb_artifact_release_class")[0]
    guard = migration[migration.index("DO $guard$"):]
    assert "'ck_kb_artifact_release_class', 'ck_kb_artifact_class'" in guard


@pytest.mark.parametrize("statement,form", [
    ("ADD COLUMN", "IF NOT EXISTS"),
    ("CREATE UNIQUE INDEX", "IF NOT EXISTS"),
    ("CREATE OR REPLACE VIEW", "OR REPLACE"),
])
def test_every_other_statement_is_naturally_idempotent(statement, form, migration):
    body = _body(migration)
    for occurrence in re.finditer(re.escape(statement), body):
        window = body[occurrence.start():occurrence.start() + 120]
        assert form in window, window[:80]


def test_the_migration_can_be_applied_twice(migration):
    """No statement in the file can fail because a prior run succeeded."""
    body = _body(migration)
    hazards = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("ALTER TABLE") and "ADD CONSTRAINT" in body:
            continue
        if stripped.startswith("CREATE INDEX") and "IF NOT EXISTS" not in stripped:
            hazards.append(stripped)
        if stripped.startswith("CREATE VIEW"):        # must be OR REPLACE
            hazards.append(stripped)
        if stripped.startswith("CREATE TABLE") and "IF NOT EXISTS" not in stripped:
            hazards.append(stripped)
    assert hazards == []
