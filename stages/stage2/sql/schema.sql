CREATE SCHEMA IF NOT EXISTS sber_procurement;

CREATE TABLE IF NOT EXISTS sber_procurement.organizations (
    organization_id bigserial PRIMARY KEY,
    inn text NOT NULL,
    kpp text,
    ogrn text,
    legal_name text NOT NULL,
    short_name text,
    aliases text,
    relation_to_sber text,
    priority integer,
    verification_source text,
    notes text,
    UNIQUE (inn, kpp)
);

CREATE TABLE IF NOT EXISTS sber_procurement.purchases (
    purchase_id bigserial PRIMARY KEY,
    canonical_purchase_id text NOT NULL UNIQUE,
    purchase_number text NOT NULL,
    title text,
    customer_name text,
    customer_inn text,
    customer_kpp text,
    customer_ogrn text,
    relation_to_sber text,
    publication_date date,
    end_date date,
    amount_rub numeric(20, 2),
    currency text,
    status text,
    procedure_type text,
    law_or_section text,
    platform_section text,
    region text,
    primary_source text,
    source_count integer NOT NULL DEFAULT 1 CHECK (source_count >= 1),
    source_systems text,
    primary_url text,
    sberbank_ast_url text,
    eis_url text,
    link_quality text,
    year integer,
    month text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_purchases_date
    ON sber_procurement.purchases (publication_date);
CREATE INDEX IF NOT EXISTS idx_purchases_customer
    ON sber_procurement.purchases (customer_inn);
CREATE INDEX IF NOT EXISTS idx_purchases_amount
    ON sber_procurement.purchases (amount_rub);
CREATE INDEX IF NOT EXISTS idx_purchases_year_month
    ON sber_procurement.purchases (year, month);

CREATE TABLE IF NOT EXISTS sber_procurement.purchase_sources (
    purchase_source_id bigserial PRIMARY KEY,
    canonical_purchase_id text NOT NULL
        REFERENCES sber_procurement.purchases (canonical_purchase_id) ON DELETE CASCADE,
    source_system text NOT NULL,
    source_record_id text NOT NULL,
    purchase_number text,
    source_url text,
    source_section text,
    source_status text,
    publication_date date,
    amount_rub numeric(20, 2),
    match_quality text,
    UNIQUE (source_system, source_record_id)
);

CREATE TABLE IF NOT EXISTS sber_procurement.purchase_candidates (
    candidate_id bigserial PRIMARY KEY,
    source_system text NOT NULL,
    source_record_id text,
    purchase_number text,
    title text,
    customer_name text,
    customer_inn text,
    publication_date date,
    amount_rub numeric(20, 2),
    source_url text,
    match_quality text,
    review_status text NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS sber_procurement.duplicate_audit (
    duplicate_id bigserial PRIMARY KEY,
    canonical_purchase_id text NOT NULL
        REFERENCES sber_procurement.purchases (canonical_purchase_id) ON DELETE CASCADE,
    duplicate_source text NOT NULL,
    duplicate_record_id text NOT NULL,
    kept_source text NOT NULL,
    kept_record_id text NOT NULL,
    duplicate_type text NOT NULL,
    match_method text NOT NULL,
    match_confidence numeric(5, 4),
    purchase_number text,
    publication_date date,
    amount_rub numeric(20, 2),
    source_url text
);

CREATE TABLE IF NOT EXISTS sber_procurement.documents (
    document_id bigserial PRIMARY KEY,
    canonical_purchase_id text NOT NULL
        REFERENCES sber_procurement.purchases (canonical_purchase_id) ON DELETE CASCADE,
    purchase_number text,
    source_system text NOT NULL,
    card_url text NOT NULL,
    document_url text,
    document_type text,
    metadata_status text NOT NULL,
    download_status text NOT NULL,
    extraction_status text NOT NULL,
    anonymization_status text NOT NULL,
    processing_priority text,
    processing_idea text,
    file_name text,
    file_sha256 text,
    mime_type text,
    downloaded_at timestamptz,
    extracted_at timestamptz,
    anonymized_at timestamptz,
    extracted_text text,
    llm_summary jsonb
);

CREATE INDEX IF NOT EXISTS idx_documents_status
    ON sber_procurement.documents (metadata_status, extraction_status);

CREATE OR REPLACE VIEW sber_procurement.v_monthly_dynamics AS
SELECT
    date_trunc('month', publication_date)::date AS month,
    count(*) AS purchase_count,
    count(amount_rub) AS purchases_with_amount,
    sum(amount_rub) AS total_amount_rub,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY amount_rub)
        FILTER (WHERE amount_rub IS NOT NULL) AS median_amount_rub
FROM sber_procurement.purchases
GROUP BY 1;

CREATE OR REPLACE VIEW sber_procurement.v_customer_summary AS
SELECT
    customer_inn,
    customer_name,
    count(*) AS purchase_count,
    count(amount_rub) AS purchases_with_amount,
    sum(amount_rub) AS total_amount_rub
FROM sber_procurement.purchases
GROUP BY customer_inn, customer_name;
