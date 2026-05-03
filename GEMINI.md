# Project Instructions: Finance Dashboard

## Architecture Overview
This project contains two distinct UI implementations sharing a **unified backend architecture**.

### 1. Streamlit Implementation (Primary UI)
- **Main File:** `dashboard.py`
- **Title:** "Financial Intelligence Dashboard"
- **Entry Point:** `streamlit run dashboard.py`
- **Features:** Interactive visualizations (Plotly, Altair), sidebar actions, and tab-based navigation.

### 2. FastAPI Implementation (Secondary/Web UI)
- **Main File:** `main.py`
- **Templates:** `templates/dashboard.html`, `templates/upload.html`
- **Entry Point:** `python3 main.py` or `uvicorn main.py:app`
- **Database:** Uses SQLModel with SQLite for unified data persistence across both applications.

## Core Architecture Components
- **Unified Service Layer:** `services.py` houses the `FinanceService` class. **Both UIs must use this service** to fetch data and trigger migrations.
- **Data Loading:** `data_loader.py` handles parsing `latest_finance.xlsx` using **anchor-based searching** (robust against row/column shifts).
- **Calculations:** `calculations.py` contains the core `FinanceCalculations` class for all business logic and financial metrics.
- **Models:** `models.py` defines the SQLModel schema and unified database connection (`finance.db`).
- **Utilities:** `utils.py` contains shared logic for currency cleaning and date formatting.

## Development Guidelines
- **Logic Centralization:** Never implement business logic in `main.py` or `dashboard.py`. Always use `calculations.py` or `services.py`.
- **Database Consistency:** Both applications share `finance.db`. Any data added via one UI will be visible in the other.
- **Excel Robustness:** `data_loader.py` avoids hardcoded indices. When parsing new sections, use `utils.get_value_by_label`.
- **Dual UI Sync:** When adding UI features, ensure they are implemented in BOTH `dashboard.py` and `templates/dashboard.html` to maintain parity.

## Data Migration
- **Script:** `migrate.py` performs a clean migration from Excel to the SQLite database.
- **Trigger:** Handled automatically upon file upload in FastAPI or via the sidebar in Streamlit if data is missing.

## UI Customizations
- **Credit Tab:** Unified view containing both Credit Card metrics and Payment Trends.
- **Disabled Features:** "Quick Entry" (Streamlit) and "Manage Financial Data" (FastAPI) are currently disabled at the user's request. The code remains for reference but is hidden/non-functional in the primary UI.
