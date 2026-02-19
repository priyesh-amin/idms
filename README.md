# Intelligent Document Management System (IDMS)

IDMS is an automated system for ingesting, categorizing, and auditing documents using a combination of OCR, vector search, and agentic review.

## Repository Structure

*   **backend/**: Node.js API (Express) and Python processing pipelines.
    *   `src/api`: Express server and endpoints.
    *   `src/pipelines`: Python scripts for extraction, categorization, and vectorization.
*   **frontend/**: React + TypeScript + Vite dashboard for document review and management.
*   **docs/**: System directives, architecture manifests, and flowcharts.

## Getting Started

### Backend
1.  Navigate to `backend/`.
2.  Install Node dependencies: `npm install`.
3.  Install Python dependencies: `pip install -r requirements.txt`.
4.  Start the server: `npm start`.

### Frontend
1.  Navigate to `frontend/`.
2.  Install dependencies: `npm install`.
3.  Start the development server: `npm run dev`.

## Documentation
See the `docs/` directory for detailed architecture and governance directives.
