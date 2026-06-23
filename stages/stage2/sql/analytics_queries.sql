SELECT
    count(*) AS canonical_purchases,
    count(amount_rub) AS with_amount,
    round(100.0 * count(amount_rub) / nullif(count(*), 0), 2) AS amount_coverage_pct,
    min(publication_date) AS first_publication_date,
    max(publication_date) AS last_publication_date,
    count(*) FILTER (WHERE source_count > 1) AS multi_source_purchases
FROM sber_procurement.purchases;


SELECT
    year,
    count(*) AS purchase_count,
    count(amount_rub) AS purchases_with_amount,
    sum(amount_rub) AS total_amount_rub,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY amount_rub)
        FILTER (WHERE amount_rub IS NOT NULL) AS median_amount_rub
FROM sber_procurement.purchases
GROUP BY year
ORDER BY year;

SELECT * FROM sber_procurement.v_monthly_dynamics ORDER BY month;

SELECT *
FROM sber_procurement.v_customer_summary
ORDER BY purchase_count DESC, total_amount_rub DESC NULLS LAST
LIMIT 20;

SELECT
    platform_section,
    procedure_type,
    count(*) AS purchase_count,
    sum(amount_rub) AS total_amount_rub
FROM sber_procurement.purchases
GROUP BY platform_section, procedure_type
ORDER BY purchase_count DESC;

SELECT
    purchase_number,
    customer_name,
    publication_date,
    amount_rub,
    procedure_type,
    left(title, 250) AS title_short,
    primary_url
FROM sber_procurement.purchases
WHERE amount_rub IS NOT NULL
ORDER BY amount_rub DESC
LIMIT 20;

SELECT
    duplicate_type,
    match_method,
    count(*) AS duplicate_source_rows,
    avg(match_confidence) AS average_confidence
FROM sber_procurement.duplicate_audit
GROUP BY duplicate_type, match_method;

SELECT
    canonical_purchase_id,
    count(*) AS source_rows,
    count(DISTINCT publication_date) AS distinct_publication_dates,
    count(DISTINCT amount_rub) FILTER (WHERE amount_rub IS NOT NULL) AS distinct_amounts,
    string_agg(source_system || ':' || source_record_id, ' | ' ORDER BY source_system) AS lineage
FROM sber_procurement.purchase_sources
GROUP BY canonical_purchase_id
HAVING count(*) > 1
ORDER BY canonical_purchase_id;

SELECT
    source_system,
    purchase_number,
    customer_name,
    publication_date,
    amount_rub,
    left(title, 250) AS title_short,
    source_url
FROM sber_procurement.purchase_candidates
WHERE review_status = 'pending'
ORDER BY amount_rub DESC NULLS LAST
LIMIT 50;

SELECT
    processing_priority,
    metadata_status,
    extraction_status,
    count(*) AS queue_size
FROM sber_procurement.documents
GROUP BY processing_priority, metadata_status, extraction_status
ORDER BY processing_priority, metadata_status, extraction_status;

SELECT
    purchase_number,
    publication_date,
    amount_rub,
    status,
    left(title, 250) AS title_short,
    primary_url
FROM sber_procurement.purchases
WHERE lower(coalesce(title, '') || ' ' || coalesce(status, '') || ' ' || coalesce(procedure_type, ''))
      LIKE '%единственн%'
ORDER BY amount_rub DESC NULLS LAST;

SELECT
    customer_inn,
    publication_date,
    amount_rub,
    left(upper(regexp_replace(title, '[^[:alnum:]]+', ' ', 'g')), 120) AS title_key,
    count(*) AS similar_procedures,
    array_agg(purchase_number ORDER BY purchase_number) AS purchase_numbers
FROM sber_procurement.purchases
WHERE title IS NOT NULL
GROUP BY customer_inn, publication_date, amount_rub,
         left(upper(regexp_replace(title, '[^[:alnum:]]+', ' ', 'g')), 120)
HAVING count(*) > 1
ORDER BY similar_procedures DESC, publication_date DESC;
