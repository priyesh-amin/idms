CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    source_file TEXT,
    new_name TEXT,
    category TEXT,
    entity TEXT,
    confidence NUMERIC(5,4),
    storage_path TEXT,
    status TEXT,
    file_hash TEXT,
    hash_valid BOOLEAN DEFAULT FALSE,
    extracted_text TEXT,
    extracted_text_length INTEGER DEFAULT 0,
    extraction_method TEXT,
    pages_processed INTEGER DEFAULT 0,
    ocr_used BOOLEAN DEFAULT FALSE,
    ocr_dpi INTEGER DEFAULT 0,
    ocr_engine_version TEXT,
    embedding_model TEXT,
    signals_detected JSONB DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category);
CREATE INDEX IF NOT EXISTS idx_documents_entity ON documents(entity);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(file_hash);
CREATE INDEX IF NOT EXISTS idx_documents_text_trgm ON documents USING GIN (extracted_text gin_trgm_ops);

CREATE TABLE IF NOT EXISTS document_chunks (
    id BIGSERIAL PRIMARY KEY,
    doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding VECTOR(384),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (doc_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_document_chunks_doc_id ON document_chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_text_trgm ON document_chunks USING GIN (chunk_text gin_trgm_ops);

CREATE TABLE IF NOT EXISTS invoices (
    doc_id TEXT PRIMARY KEY REFERENCES documents(doc_id) ON DELETE CASCADE,
    invoice_number TEXT,
    invoice_date DATE,
    due_date DATE,
    currency TEXT,
    vendor TEXT,
    customer TEXT,
    net_amount NUMERIC(14,2),
    vat_amount NUMERIC(14,2),
    total_amount NUMERIC(14,2),
    vat_reclaimable NUMERIC(14,2),
    is_ar BOOLEAN DEFAULT FALSE,
    payment_status TEXT DEFAULT 'unpaid',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_invoices_invoice_date ON invoices(invoice_date);
CREATE INDEX IF NOT EXISTS idx_invoices_due_date ON invoices(due_date);
CREATE INDEX IF NOT EXISTS idx_invoices_total_amount ON invoices(total_amount);
CREATE INDEX IF NOT EXISTS idx_invoices_vat_reclaimable ON invoices(vat_reclaimable);
CREATE INDEX IF NOT EXISTS idx_invoices_is_ar ON invoices(is_ar);
CREATE INDEX IF NOT EXISTS idx_invoices_payment_status ON invoices(payment_status);

CREATE TABLE IF NOT EXISTS ar_items (
    id BIGSERIAL PRIMARY KEY,
    doc_id TEXT REFERENCES documents(doc_id) ON DELETE SET NULL,
    counterparty TEXT,
    due_date DATE,
    total_amount NUMERIC(14,2),
    amount_paid NUMERIC(14,2) DEFAULT 0,
    amount_outstanding NUMERIC(14,2),
    status TEXT DEFAULT 'open',
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ar_items_due_date ON ar_items(due_date);
CREATE INDEX IF NOT EXISTS idx_ar_items_status ON ar_items(status);
CREATE INDEX IF NOT EXISTS idx_ar_items_outstanding ON ar_items(amount_outstanding);

CREATE TABLE IF NOT EXISTS audit_events (
    id BIGSERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    doc_id TEXT,
    execution_id TEXT,
    severity TEXT DEFAULT 'info',
    details JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_events_doc_id ON audit_events(doc_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_execution_id ON audit_events(execution_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_type ON audit_events(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_events_created_at ON audit_events(created_at);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_documents_updated_at ON documents;
CREATE TRIGGER trg_documents_updated_at
BEFORE UPDATE ON documents
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_invoices_updated_at ON invoices;
CREATE TRIGGER trg_invoices_updated_at
BEFORE UPDATE ON invoices
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_ar_items_updated_at ON ar_items;
CREATE TRIGGER trg_ar_items_updated_at
BEFORE UPDATE ON ar_items
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
