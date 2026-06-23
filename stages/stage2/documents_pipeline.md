# Processing Attached Procurement Documents

The current Stage 2 output contains a card-discovery queue rather than claiming
that every card URL is an attachment. The queue is stored in
`purchase_documents_plan.csv` and PostgreSQL table `documents`.

## Recommended Pipeline

1. Open the source card and enumerate attachment metadata.
2. Store source URL, file name, MIME type, size, publication date and SHA-256.
3. Download only new hashes; keep immutable raw files separately.
4. Extract text:
   - PDF with a text layer: `pypdf`/`pdfplumber`;
   - scanned PDF/images: OCR;
   - DOCX: `python-docx`;
   - XLSX: `openpyxl`;
   - archives: unpack with file-count and size limits.
5. Run the same personal-data anonymizer before analytical storage.
6. Extract structured facts:
   - procurement subject and detailed requirements;
   - lots and OKPD2;
   - application deadlines and delivery terms;
   - participants, admitted bids and winner;
   - initial and final contract price;
   - cancellation reason;
   - single-supplier and low-competition signals.
7. Use an LLM only after deterministic extraction. Require JSON output,
   confidence, evidence snippets and `null` for unavailable facts.

## Security and Quality Controls

- allow-list file types and reject executable content;
- enforce archive depth, file-count and uncompressed-size limits;
- hash every file and avoid duplicate processing;
- preserve raw, extracted and anonymized layers separately;
- log parser/OCR/LLM version;
- manually review low-confidence fields and high-value procedures.

## Current Queue

The current queue has 1,461 source cards:

- 1,458 Sberbank-AST cards;
- 3 linked EIS cards;
- status `card_queued`;
- actual attachment count remains unknown until the card crawler runs.
