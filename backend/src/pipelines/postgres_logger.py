import os
import re
import sys
import json
from datetime import datetime

import psycopg2
from psycopg2.extras import Json


def get_dsn():
    dsn = os.environ.get("IDMS_PG_DSN")
    if dsn:
        return dsn
    host = os.environ.get("IDMS_PG_HOST", "127.0.0.1")
    port = os.environ.get("IDMS_PG_PORT", "5432")
    db = os.environ.get("IDMS_PG_DB", "idms")
    user = os.environ.get("IDMS_PG_USER", "idms")
    password = os.environ.get("IDMS_PG_PASSWORD", "idms")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()

    text = str(value).strip()
    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%d %b %Y",
        "%d %B %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def to_float(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", "")
    text = text.replace("GBP", "").replace("USD", "").replace("EUR", "")
    text = text.replace("$", "").replace("?", "").replace("?", "")
    try:
        return float(text)
    except ValueError:
        return None


def first_match(patterns, text):
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def parse_money_from_text(text, keywords):
    lines = text.splitlines()
    for line in lines:
        lower = line.lower()
        if any(k in lower for k in keywords):
            match = re.search(r"([?$?]?\s?[0-9][0-9,]*(?:\.[0-9]{2})?)", line)
            if match:
                return to_float(match.group(1))
    return None


def detect_currency(text):
    if re.search(r"\bGBP\b|?", text, re.IGNORECASE):
        return "GBP"
    if re.search(r"\bUSD\b|\$", text, re.IGNORECASE):
        return "USD"
    if re.search(r"\bEUR\b|?", text, re.IGNORECASE):
        return "EUR"
    return None


def infer_invoice_fields(metadata, content):
    text = content or ""
    doc_type = str(metadata.get("doc_type", "") or "")
    is_invoice_like = doc_type.lower() == "invoice" or ("invoice" in text.lower())

    invoice_number = first_match(
        [
            r"invoice\s*(?:number|no\.?|#)\s*[:\-]?\s*([A-Za-z0-9\-_/]+)",
            r"inv\s*(?:number|no\.?|#)\s*[:\-]?\s*([A-Za-z0-9\-_/]+)",
        ],
        text,
    )

    invoice_date_raw = first_match(
        [
            r"invoice\s*date\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
            r"date\s*[:\-]?\s*([0-9]{4}\-[0-9]{2}\-[0-9]{2})",
        ],
        text,
    )
    due_date_raw = first_match(
        [
            r"due\s*date\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
            r"payment\s*due\s*[:\-]?\s*([0-9]{1,2}[\/\-][0-9]{1,2}[\/\-][0-9]{2,4})",
        ],
        text,
    )

    total_amount = parse_money_from_text(text, ["total", "amount due", "balance due"])
    vat_amount = parse_money_from_text(text, ["vat", "tax"])
    net_amount = parse_money_from_text(text, ["subtotal", "net"])

    if vat_amount is not None and total_amount is not None and net_amount is None:
        net_amount = max(total_amount - vat_amount, 0)

    currency = detect_currency(text) or metadata.get("currency")
    vendor = metadata.get("entity")
    customer = metadata.get("customer")

    # Basic AR detection: if explicitly marked or text references receivables/customer due
    is_ar = bool(metadata.get("is_ar"))
    if not is_ar and re.search(r"accounts receivable|overdue|balance due", text, re.IGNORECASE):
        is_ar = True

    vat_reclaimable = vat_amount if vat_amount is not None and not is_ar else 0.0

    return {
        "is_invoice_like": is_invoice_like,
        "invoice_number": invoice_number,
        "invoice_date": parse_date(invoice_date_raw),
        "due_date": parse_date(due_date_raw),
        "currency": currency,
        "vendor": vendor,
        "customer": customer,
        "net_amount": net_amount,
        "vat_amount": vat_amount,
        "total_amount": total_amount,
        "vat_reclaimable": vat_reclaimable,
        "is_ar": is_ar,
    }


def upsert_document(cur, metadata, content):
    doc_id = metadata.get("doc_id")
    if not doc_id:
        raise ValueError("metadata.doc_id is required")

    cur.execute(
        """
        INSERT INTO documents (
            doc_id, source_file, new_name, category, entity, confidence,
            storage_path, status, file_hash, hash_valid, extracted_text,
            extracted_text_length, extraction_method, pages_processed,
            ocr_used, ocr_dpi, ocr_engine_version, embedding_model,
            signals_detected, metadata
        )
        VALUES (
            %(doc_id)s, %(source_file)s, %(new_name)s, %(category)s, %(entity)s, %(confidence)s,
            %(storage_path)s, %(status)s, %(file_hash)s, %(hash_valid)s, %(extracted_text)s,
            %(extracted_text_length)s, %(extraction_method)s, %(pages_processed)s,
            %(ocr_used)s, %(ocr_dpi)s, %(ocr_engine_version)s, %(embedding_model)s,
            %(signals_detected)s, %(metadata)s
        )
        ON CONFLICT (doc_id) DO UPDATE SET
            source_file = EXCLUDED.source_file,
            new_name = EXCLUDED.new_name,
            category = EXCLUDED.category,
            entity = EXCLUDED.entity,
            confidence = EXCLUDED.confidence,
            storage_path = EXCLUDED.storage_path,
            status = EXCLUDED.status,
            file_hash = EXCLUDED.file_hash,
            hash_valid = EXCLUDED.hash_valid,
            extracted_text = EXCLUDED.extracted_text,
            extracted_text_length = EXCLUDED.extracted_text_length,
            extraction_method = EXCLUDED.extraction_method,
            pages_processed = EXCLUDED.pages_processed,
            ocr_used = EXCLUDED.ocr_used,
            ocr_dpi = EXCLUDED.ocr_dpi,
            ocr_engine_version = EXCLUDED.ocr_engine_version,
            embedding_model = EXCLUDED.embedding_model,
            signals_detected = EXCLUDED.signals_detected,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
        """,
        {
            "doc_id": doc_id,
            "source_file": metadata.get("orig_name"),
            "new_name": metadata.get("new_name"),
            "category": metadata.get("category"),
            "entity": metadata.get("entity"),
            "confidence": to_float(metadata.get("confidence")),
            "storage_path": metadata.get("path"),
            "status": metadata.get("status"),
            "file_hash": metadata.get("hash"),
            "hash_valid": bool(metadata.get("hash_valid")),
            "extracted_text": content,
            "extracted_text_length": int(metadata.get("extracted_text_length", len(content or ""))),
            "extraction_method": metadata.get("extraction_method"),
            "pages_processed": int(metadata.get("pages_processed", 0)),
            "ocr_used": bool(metadata.get("ocr_used", False)),
            "ocr_dpi": int(metadata.get("ocr_dpi", 0)),
            "ocr_engine_version": metadata.get("ocr_engine_version"),
            "embedding_model": metadata.get("embedding_model"),
            "signals_detected": Json(metadata.get("signals_detected", [])),
            "metadata": Json(metadata),
        },
    )


def upsert_invoice_and_ar(cur, doc_id, fields):
    if not fields.get("is_invoice_like"):
        return {"invoice_upserted": False, "ar_upserted": False}

    cur.execute(
        """
        INSERT INTO invoices (
            doc_id, invoice_number, invoice_date, due_date, currency,
            vendor, customer, net_amount, vat_amount, total_amount,
            vat_reclaimable, is_ar, payment_status
        )
        VALUES (
            %(doc_id)s, %(invoice_number)s, %(invoice_date)s, %(due_date)s, %(currency)s,
            %(vendor)s, %(customer)s, %(net_amount)s, %(vat_amount)s, %(total_amount)s,
            %(vat_reclaimable)s, %(is_ar)s, %(payment_status)s
        )
        ON CONFLICT (doc_id) DO UPDATE SET
            invoice_number = EXCLUDED.invoice_number,
            invoice_date = EXCLUDED.invoice_date,
            due_date = EXCLUDED.due_date,
            currency = EXCLUDED.currency,
            vendor = EXCLUDED.vendor,
            customer = EXCLUDED.customer,
            net_amount = EXCLUDED.net_amount,
            vat_amount = EXCLUDED.vat_amount,
            total_amount = EXCLUDED.total_amount,
            vat_reclaimable = EXCLUDED.vat_reclaimable,
            is_ar = EXCLUDED.is_ar,
            payment_status = EXCLUDED.payment_status,
            updated_at = NOW()
        """,
        {
            "doc_id": doc_id,
            "invoice_number": fields.get("invoice_number"),
            "invoice_date": fields.get("invoice_date"),
            "due_date": fields.get("due_date"),
            "currency": fields.get("currency"),
            "vendor": fields.get("vendor"),
            "customer": fields.get("customer"),
            "net_amount": fields.get("net_amount"),
            "vat_amount": fields.get("vat_amount"),
            "total_amount": fields.get("total_amount"),
            "vat_reclaimable": fields.get("vat_reclaimable"),
            "is_ar": bool(fields.get("is_ar")),
            "payment_status": "open" if fields.get("is_ar") else "unpaid",
        },
    )

    ar_upserted = False
    if fields.get("is_ar") and fields.get("total_amount") is not None:
        amount_outstanding = max(float(fields.get("total_amount") or 0) - 0.0, 0.0)
        cur.execute(
            """
            INSERT INTO ar_items (
                doc_id, counterparty, due_date, total_amount,
                amount_paid, amount_outstanding, status, metadata
            )
            VALUES (
                %(doc_id)s, %(counterparty)s, %(due_date)s, %(total_amount)s,
                0, %(amount_outstanding)s, %(status)s, %(metadata)s
            )
            """,
            {
                "doc_id": doc_id,
                "counterparty": fields.get("customer") or fields.get("vendor"),
                "due_date": fields.get("due_date"),
                "total_amount": fields.get("total_amount"),
                "amount_outstanding": amount_outstanding,
                "status": "overdue" if fields.get("due_date") and fields.get("due_date") < datetime.utcnow().date() else "open",
                "metadata": Json({"source": "postgres_logger"}),
            },
        )
        ar_upserted = True

    return {"invoice_upserted": True, "ar_upserted": ar_upserted}


def log_to_postgres(metadata, content):
    dsn = get_dsn()
    conn = psycopg2.connect(dsn)
    try:
        with conn:
            with conn.cursor() as cur:
                upsert_document(cur, metadata, content)
                fields = infer_invoice_fields(metadata, content)
                invoice_state = upsert_invoice_and_ar(cur, metadata.get("doc_id"), fields)

                cur.execute(
                    """
                    INSERT INTO audit_events (event_type, doc_id, severity, details)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        "pipeline.persisted",
                        metadata.get("doc_id"),
                        "info",
                        Json({
                            "source": "postgres_logger",
                            "invoice": invoice_state,
                            "doc_type": metadata.get("doc_type"),
                        }),
                    ),
                )

        return {
            "status": "success",
            "doc_id": metadata.get("doc_id"),
            "dsn_target": dsn.split("@")[-1],
            **invoice_state,
        }
    finally:
        conn.close()


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"status": "error", "message": "Usage: postgres_logger.py <metadata_json> [content]"}))
        sys.exit(1)

    try:
        metadata = json.loads(sys.argv[1])
        content = sys.argv[2] if len(sys.argv) >= 3 else ""
        result = log_to_postgres(metadata, content)
        print(json.dumps(result))
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
