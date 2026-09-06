# Database Assets

This directory contains PostgreSQL schema definitions, ingestion logic, and procedures for the Retail OS data platform.

## Structure

### ddl/
Core data definition language (DDL) files defining the Retail OS schema:
- **001_core_schema.sql**: Main schema definition (PHASE_1_DDL_FINAL) with raw, runtime, state, and audit schemas
- **002_fold_function.sql**: Fold operation for state management and evidence aggregation (PHASE_2)
- **003_decision_execution.sql**: Decision execution framework and approval workflows (PHASE_3)
- **004_postgres_core_tables_reference.sql**: Reference documentation for PostgreSQL core tables

**Deployment order**: Execute in numerical order (001 → 002 → 003 → 004)

### ingestion/
Lambda function and ingestion-related SQL scripts:
- **audit_ingestion_file.sql**: Audit table for tracking ingestion file operations
- **checkpoint_kb_setup.sql**: Knowledge base setup checkpoint (complete_kb_setup_fixed)
- **validation_diagnostic_all_tables.sql**: Diagnostic queries for validating all tables
- **lambda/**: Contains deployed Lambda function code
  - **lambda_function.py**: Current deployed Lambda ingestion handler
  - **lambda_ingestion_implementation_reference.py**: Enhanced reference implementation with test mode

**Note**: These files define the checkpoint/validation state for ingestion operations.

### procedures/
Database procedures and seed scripts:
- **seed_catalogue_missing_rules.sql**: Populates catalogue rules
- **seed_zone_d_translation.sql**: Zone D translation configuration
- **raw_to_evidence.sql**: TODO - Procedure to transform raw data to evidence (when implemented)
- **evidence_to_assertion.sql**: TODO - Procedure to transform evidence to assertions (when implemented)
- **fold.sql**: TODO - Procedure to fold state snapshots (when implemented)

## Important Notes

✓ **Database already contains these objects**: The PostgreSQL instance at accord database already has these schemas and tables defined. These files are imported for repository capture and version control.

✓ **No execution required on import**: These DDL files are reference and history. The database is already initialized.

✓ **Source control purpose**: These files represent the current approved schema definition and ingestion workflow.

❌ **Do NOT**:
- Attempt to re-execute DDL files on the live database (schemas already exist)
- Modify the PostgreSQL schema
- Modify S3 corpus configuration
- Change ingestion business logic without approval

## Related Directories

- See `ontology/` for knowledge base and ontology assets
- See `transforms/` for data transformation logic
- See `canonical/` for canonical data models

---

*Imported from edms-simulator and lakehouse-os projects. This is source-control capture only.*
