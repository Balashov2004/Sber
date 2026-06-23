from __future__ import annotations

import re


EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"(?<!\d)(?:\+7|8)?[\s\-.(]*\d{3}[\s\-.)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}(?!\d)")
PASSPORT_RE = re.compile(
    r"(?i)\b(?:паспорт(?:\s+рф)?[\s:№#-]*)?"
    r"(?:(?:серия|сер\.?)[\s:№#-]*)?"
    r"\d{2}\s?\d{2}"
    r"[\s,;/-]*"
    r"(?:(?:номер|№|N|No)[\s:№#-]*)?"
    r"\d{6}\b"
)
SNILS_RE = re.compile(r"\b\d{3}-\d{3}-\d{3}\s?\d{2}\b")
SNILS_COMPACT_RE = re.compile(r"(?i)\b(?:снилс[\s:№#-]*)?\d{11}\b")
PERSONAL_INN_RE = re.compile(r"(?i)\b(?:инн\s*(?:физ(?:ического)?\s*лица)?[\s:№#-]*)\d{12}\b")

FIO_RE = re.compile(r"\b[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+){2}\b")
INITIALS_FIO_RE = re.compile(r"\b[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.\s?[А-ЯЁ]\.")


def anonymize_text(text: str) -> str:
    """Mask common personal data patterns in Russian procurement documents."""
    if not text:
        return text

    masked = EMAIL_RE.sub("[EMAIL]", text)
    masked = PHONE_RE.sub("[PHONE]", masked)
    masked = PASSPORT_RE.sub("[PASSPORT]", masked)
    masked = SNILS_RE.sub("[SNILS]", masked)
    masked = SNILS_COMPACT_RE.sub("[SNILS]", masked)
    masked = PERSONAL_INN_RE.sub("[PERSONAL_INN]", masked)
    masked = INITIALS_FIO_RE.sub("[FIO]", masked)
    masked = FIO_RE.sub("[FIO]", masked)
    return masked


TECHNICAL_IDENTIFIER_FIELDS = {
    "purchase_number",
    "Bid_id",
    "PurchaseId",
    "purchCode",
    "BidNo",
    "source_record_id",
    "customer_seed_inn",
    "CustomerInn",
    "OrgInn",
    "CustomerInnKpp",
    "OrgInnKpp",
    "CustomerKpp",
    "OrgKPP",
}


def anonymize_record(record: dict[str, str]) -> dict[str, str]:
    """Return a copy of a string record with personal data masked."""
    output = {}
    customer_is_legal_entity = len(record.get("CustomerInn", "")) == 10
    organizer_is_legal_entity = len(record.get("OrgInn", "")) == 10
    for key, value in record.items():
        personal_inn_field = key in {"CustomerInn", "OrgInn"} and len(str(value or "")) == 12
        preserve_legal_name = (
            key in {"CustomerFullName", "CustomerNickName"} and customer_is_legal_entity
        ) or (
            key in {"OrgFullName", "OrgName", "OrgNickName"} and organizer_is_legal_entity
        )
        preserve_registry_text = key in {
            "customer_seed_name",
            "matched_alias",
            "query",
            "query_notes",
            "search_term",
        }
        output[key] = (
            "[PERSONAL_INN]"
            if personal_inn_field
            else
            value
            if key in TECHNICAL_IDENTIFIER_FIELDS or preserve_legal_name or preserve_registry_text
            else anonymize_text(value) if isinstance(value, str) else value
        )
    return output
