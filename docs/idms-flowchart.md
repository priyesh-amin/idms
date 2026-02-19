# IDMS Document Management Flowchart (v12)

This diagram illustrates the end-to-end lifecycle of a document within the Intelligent Document Management System, including the **Real OCR Fallback** and **Natural Language Review** paths.

```mermaid
graph TD
    %% Entry Point
    A[PDF Drop-off: Inbox] --> B[Pipeline Trigger]

    %% Extraction Layer
    B --> C{Text Extraction}
    C -->|Success| D[Standard PDF Extraction]
    C -->|Failed/Empty| E[OCR Fallback: Tesseract]
    D --> F[Content & SHA-256 Hash Generated]
    E --> F

    %% Categorization Layer
    F --> G[Categorizer: Entity & Type Detection]
    G --> H{Confidence >= 0.85?}

    %% Automated Path
    H -->|Yes| I[Automated Processing]
    I --> J[Renamer: Generate YYYY-MM-DD Name]
    J --> K[Side Effects Layer]
    K --> L[Archive to Domain Folder]
    K --> M[Log to Google Sheets Audit]
    K --> N[Vectorize to FAISS Index]
    L --> O[Final: Long-Term Memory]

    %% Review Path (v12)
    H -->|No| P[Staged: Inbox/review/]
    P --> Q[Directive: 'Review pending documents']
    Q --> R[Persistent Review Session]
    R --> S[Display Review Card: Identity Lock]
    S --> T{Conversational Audit}
    
    %% Audit Interactions
    T -->|Edit| U[Recalculate Metadata]
    U --> S
    T -->|Skip| V[Leave in review]
    T -->|Approve| W[Approve: Hash Verified]
    
    %% Post-Approval Ingestion
    W --> J
```

## Key Architectural Components
1. **Extraction Layer**: Dual-mode extraction (Native + OCR) with deterministic SHA-256 hashing.
2. **Confidence Gating**: 0.85 safety threshold to prevent misclassification.
3. **Conversational Review**: Persistent session management with binary hash integrity locks.
4. **Permanent Storage**: Domain-driven archival in G-Drive (`06-long-term-memory`).
