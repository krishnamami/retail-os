# Ontology and Knowledge Base Assets

This directory contains the Retail OS ontology definition, knowledge base setup, and related compilation artifacts.

## Structure

### source/
Original ontology source files and definitions:
- **claris_ontology.sql**: Main Claris ontology definition with entities, relationships, and semantic rules
- **postgres_ontology_retail_schema.sql**: PostgreSQL implementation of the retail ontology schema
- **ontology_implementation_guide.sql**: Guide for implementing the ontology in PostgreSQL
- **lakehouse_postgres_ontology_retail_schema_reference.sql**: Reference implementation from lakehouse-os project

### compiled/
Compiled and generated ontology artifacts ready for deployment:
- **kb_1_0_1_postgresql_load.sql**: Knowledge base v1.0.1 load script for PostgreSQL

### migrations/
Schema migration scripts for ontology evolution (TODO):
- Placeholder for future ontology version migrations

### validation/
Ontology validation and verification scripts (TODO):
- Placeholder for ontology consistency checks

## Important Notes

✓ **Ontology is stable**: The current ontology (claris_ontology.sql) represents the approved business logic and semantic model.

✓ **Knowledge base is loaded**: The PostgreSQL database already has the ontology and KB loaded.

✓ **Multiple source versions exist**: Several SQL files provide alternative schema implementations (source and reference). The primary version is `claris_ontology.sql`.

❌ **Do NOT**:
- Modify ontology semantics without approval
- Change entity relationships or business rules
- Reapply ontology DDL to live database (already loaded)

## Usage

1. **Reference semantic model**: Review `claris_ontology.sql` for the authoritative ontology
2. **Understand PostgreSQL mapping**: See `postgres_ontology_retail_schema.sql` for relational implementation
3. **Track versions**: Store ontology changes in `migrations/` subdirectory with version numbers
4. **Validate consistency**: Use scripts in `validation/` subdirectory to verify ontology state

## Related Directories

- See `database/ddl/` for schema DDL
- See `decisions/` for decision logic that uses this ontology
- See `agents/` for AI agents that orchestrate decisions based on ontology

---

*Imported from edms-simulator and lakehouse-os projects. This is source-control capture only.*
