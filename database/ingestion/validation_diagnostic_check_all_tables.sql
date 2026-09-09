-- Check configuration_assertion columns
SELECT 'configuration_assertion' as table_name;
SELECT column_name, data_type FROM information_schema.columns
WHERE table_schema = 'claris' AND table_name = 'configuration_assertion'
ORDER BY ordinal_position;

SELECT '' as blank;

-- Check configuration_state columns
SELECT 'configuration_state' as table_name;
SELECT column_name, data_type FROM information_schema.columns
WHERE table_schema = 'claris' AND table_name = 'configuration_state'
ORDER BY ordinal_position;

SELECT '' as blank;

-- Check decision table columns
SELECT 'decision' as table_name;
SELECT column_name, data_type FROM information_schema.columns
WHERE table_schema = 'claris' AND table_name = 'decision'
ORDER BY ordinal_position;
