# Retail OS

Retail OS is a governed product and decision platform prototype for Claris retail/product lifecycle modernization.

## Architecture

The runtime flow follows this pipeline:

```
S3 source corpus
    ↓
Lambda ingestion
    ↓
PostgreSQL raw.raw_event
    ↓
Raw → Evidence (PostgreSQL procedure)
    ↓
runtime.evidence
    ↓
Evidence → Assertions (PostgreSQL procedure)
    ↓
runtime.assertion
    ↓
Fold (PostgreSQL procedure)
    ↓
state.fold_state_snapshot
    ↓
Canonical Product/Configuration State
    ↓
Governed Deterministic Decisions
    ↓
Actions / Legacy Projection
    ↓
Common Decision Workbench
    ↓
AI-assisted orchestration & explanation
```

## Current Phase

**Raw Ingestion**: AWS S3 → Lambda → PostgreSQL raw ingestion

## Next Phase

PostgreSQL transformations: Raw → Evidence → Assertions → Fold

## Key Principles

1. **AI agents are NOT decision authority** — They orchestrate, retrieve context, and explain decisions.
2. **Governed deterministic services are authoritative** — Business logic remains deterministic and auditable.
3. **Auditability is independent** — Works without AI involvement.
4. **PostgreSQL is the transformation engine** — No external orchestrators (Airflow, Databricks) initially.

## Directory Structure

- `database/` — PostgreSQL schema, ingestion, and transformation procedures
- `transforms/` — Reserved for reusable Python mappings (future)
- `canonical/` — Canonical product/configuration model (future)
- `decisions/` — Deterministic governed decision services (future)
- `agents/` — AI orchestration and explanation (future)
- `audit/` — Decision logging, replay, lineage (future)
- `tests/` — Test suites mirroring runtime layers
- `ui/` — React frontend (future)
- `docs/` — Architecture, ontology, use cases, decisions

## Next Steps

1. Implement PostgreSQL raw ingestion schema (database/ddl/)
2. Implement raw → evidence transformation (database/procedures/)
3. Add evidence → assertion transformation
4. Add fold operation
5. Build canonical configuration model
6. Implement governed decision services
7. Add AI agents for orchestration
