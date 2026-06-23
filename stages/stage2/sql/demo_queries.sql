\pset pager off
\x off

SELECT current_database() AS database_name, current_schema() AS current_schema;

SELECT 'organizations' AS table_name, count(*) AS rows_count FROM sber_procurement.organizations
UNION ALL SELECT 'purchases', count(*) FROM sber_procurement.purchases
UNION ALL SELECT 'purchase_sources', count(*) FROM sber_procurement.purchase_sources
UNION ALL SELECT 'purchase_candidates', count(*) FROM sber_procurement.purchase_candidates
UNION ALL SELECT 'duplicate_audit', count(*) FROM sber_procurement.duplicate_audit
UNION ALL SELECT 'documents', count(*) FROM sber_procurement.documents
ORDER BY table_name;

SELECT
    year,
    count(*) AS purchase_count,
    count(amount_rub) AS with_amount,
    sum(amount_rub) AS total_amount_rub
FROM sber_procurement.purchases
GROUP BY year
ORDER BY year;

SELECT
    canonical_purchase_id,
    purchase_number,
    source_count,
    source_systems,
    customer_name,
    amount_rub
FROM sber_procurement.purchases
WHERE source_count > 1
ORDER BY purchase_number;

SELECT
    duplicate_type,
    match_method,
    count(*) AS duplicate_rows,
    avg(match_confidence) AS average_confidence
FROM sber_procurement.duplicate_audit
GROUP BY duplicate_type, match_method;

SELECT
    metadata_status,
    extraction_status,
    count(*) AS documents_in_queue
FROM sber_procurement.documents
GROUP BY metadata_status, extraction_status;

SELECT
    purchase_number,
    publication_date,
    amount_rub,
    customer_name,
    left(title, 100) AS title
FROM sber_procurement.purchases
ORDER BY amount_rub DESC NULLS LAST
LIMIT 5;
