-- Temporary working file: new product and configuration_request domains to be inserted
-- These will be inserted before the closing "), " of the applicable_properties CTE

        -- =================================================================
        -- Product domain
        -- =================================================================

        UNION ALL

        SELECT
            'product'::TEXT AS subject_type,
            subject_id,
            'product_name'::TEXT AS property_name
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'product'
        ) a

        UNION ALL

        SELECT
            'product',
            subject_id,
            'launch_reference'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'product'
        ) a

        -- =================================================================
        -- Configuration Request domain
        -- =================================================================

        UNION ALL

        SELECT
            'configuration_request'::TEXT AS subject_type,
            subject_id,
            'product_reference'::TEXT AS property_name
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'configuration_request'
        ) a

        UNION ALL

        SELECT
            'configuration_request',
            subject_id,
            'launch_reference'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'configuration_request'
        ) a

        UNION ALL

        SELECT
            'configuration_request',
            subject_id,
            'geography'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'configuration_request'
        ) a

        UNION ALL

        SELECT
            'configuration_request',
            subject_id,
            'term_months'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'configuration_request'
        ) a

        UNION ALL

        SELECT
            'configuration_request',
            subject_id,
            'customer_segment'
        FROM (
            SELECT DISTINCT subject_id
            FROM runtime.assertion
            WHERE subject_type = 'configuration_request'
        ) a
