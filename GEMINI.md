# Project Instructions: Finance Dashboard

## Architecture Overview
This project follows a **Service-Oriented Architecture** with a unified backend supporting dual UIs.

### 1. Streamlit Implementation (Primary Intelligence UI)
- **Entry Point:** `streamlit run dashboard.py`
- **Role:** Deep visualizations, trends, and financial goal tracking.
- **Tech:** Streamlit, Plotly, Altair.

### 2. FastAPI Implementation (Web / Data Entry UI)
- **Entry Point:** `uvicorn main.py:app --port 8000`
- **Role:** Web-based dashboard and forms for manual data management.
- **Tech:** FastAPI, Jinja2 (Templates).

## Core Architecture Components
- **Unified Service Layer (`services.py`):** Central entry point for all UI interactions. Encapsulates business logic, data fetching, and report generation via `FinanceService`.
- **Data Persistence (`models.py`):** Uses **SQLModel + SQLite** (`finance.db`). This shared database ensures data parity between UIs.
- **Business Logic (`calculations.py`):** Pure functional logic for financial metrics (Runway, FI Ratio, Wealth Velocity, etc.).
- **Report Engine:** Uses Jinja2 templates (`templates/report.txt`) for high-quality, metric-rich text reports.
- **Excel Parser (`data_loader.py`):** Features **anchor-based searching** to remain resilient against structural changes in `latest_finance.xlsx`.

## Data Integrity & Migration
- **Non-Destructive Migration:** `migrate.py` clears ONLY Excel-sourced data. Records with `is_manual=True` are strictly preserved.
- **Idempotency & Deduplication:** Transactions (Income, Expense, Payment) use SHA256 hashes (`entry_hash`) to prevent duplicates. Lendings use unique constraints on `(person, amount, due_date)`.
- **Source Tracking:** All models contain an `is_manual` flag to distinguish between imported Excel data and UI-added records.
- **Deduplication Logic:** `DataLoader` must ONLY fetch `is_manual=True` records from SQLite to avoid double-counting when merging with raw Excel data.

## Development & Security Standards
- **Zero Business Logic in UI:** `main.py` and `dashboard.py` should only handle request/session state and rendering. All logic MUST reside in `FinanceService` or `FinanceCalculations`.
- **Security Hardening:** FastAPI routes must use generic error messages. Detailed tracebacks are captured via internal `logging` to prevent information leakage.
- **UI Parity:** New features must be reflected in both Streamlit and FastAPI templates unless they are purely visualization-focused.
- **Anchor-Based Parsing:** When adding new Excel parsing logic, use `utils.get_value_by_label` instead of hardcoded row/column indices.

## UI State Configuration
- **Disabled Features:** The "Quick Entry" (Streamlit) and "Manage Financial Data" (FastAPI) sections are functionally complete but **hidden/disabled** in the active UI at the user's request.
