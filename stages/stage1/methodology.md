# Stage 1 Methodology

## Sources

- EIS is the canonical official procurement source.
- FNS EGRUL enriches legal entities with INN, KPP, and OGRN.
- Sberbank-AST is the key specialized platform for Sber procedures.
- ZakazRF, Roseltorg, Lot-Online, TEK-Torg, RTS-Tender, and ETP GPB are probed as additional sources.

## Source Selection

EIS was selected as the primary source because it is the official publication system for 44-FZ and 223-FZ procurement. FNS was selected for reliable legal-entity identifiers. Sberbank-AST was selected because it contains a dedicated Sber procurement section.

## Data Layers

- `raw`: unchanged source responses for reproducibility.
- `interim`: parsed candidates and source logs.
- `processed/anonymized`: personal data masked before analytics.
- `processed/stage1`: canonical multi-source links and EGRUL-enriched records.

Name-based searches can produce false positives. Candidate records are therefore kept separately from strict matches where Sber is confirmed as customer or organizer.

## Anonymization

The pipeline masks names, initials, phones, email addresses, passport identifiers, SNILS, and explicitly marked personal INN values. The anonymized exports and run report are written to `data/processed/anonymized/`.

After masking, `audit_anonymization.py` scans every anonymized CSV for residual
high-risk patterns. The current audit covers 18,891 rows and reports zero
high-risk findings.

## Record Linkage

Cross-source linkage uses a conservative hierarchy:

1. exact official purchase number;
2. no automatic merge when only title/date/amount are similar;
3. fuzzy candidates may be reviewed separately but never silently merged.

Organization enrichment is joined by verified 10-digit legal-entity INN from
FNS EGRUL.
