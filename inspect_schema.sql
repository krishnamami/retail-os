-- Find all schemas
SELECT 'SCHEMAS' AS section, schema_name 
FROM information_schema.schemata 
WHERE schema_name NOT LIKE 'pg_%' AND schema_name != 'information_schema'
ORDER BY schema_name;

-- Find all tables by schema
SELECT 'TABLES' AS section, table_schema, table_name
FROM information_schema.tables
WHERE table_schema NOT LIKE 'pg_%' AND table_schema != 'information_schema'
ORDER BY table_schema, table_name;

-- Check if knowledge_base schema exists
SELECT 'KB_SCHEMA_CHECK' AS section,
  schema_name,
  CASE WHEN schema_name = 'knowledge_base' THEN 'EXISTS' ELSE 'NOT_FOUND' END as status
FROM information_schema.schemata
WHERE schema_name = 'knowledge_base';

-- Check state schema tables
SELECT 'STATE_SCHEMA_TABLES' AS section, table_name
FROM information_schema.tables
WHERE table_schema = 'state'
ORDER BY table_name;

-- Check runtime schema tables
SELECT 'RUNTIME_SCHEMA_TABLES' AS section, table_name
FROM information_schema.tables
WHERE table_schema = 'runtime'
ORDER BY table_name;
