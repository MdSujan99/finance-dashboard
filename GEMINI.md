# Project Instructions: Finance Dashboard

## Architecture Overview
This project contains two distinct implementations of the Financial Dashboard. Always clarify which one the user is currently interacting with.

### 1. Streamlit Implementation (Primary UI)
- **Main File:** `dashboard.py`
- **Title:** "Financial Intelligence Dashboard"
- **Entry Point:** `streamlit run dashboard.py`
- **Features:** Richer visualizations (Plotly, Altair), sidebar actions, and tab-based navigation (Dashboard, Credit, Budget, Lending, Goals).

### 2. FastAPI Implementation (Secondary/Web UI)
- **Main File:** `main.py`
- **Templates:** `templates/dashboard.html`, `templates/upload.html`
- **Entry Point:** `python3 main.py` or `uvicorn main.py:app`
- **Database:** Uses SQLModel (PostgreSQL/SQLite) for data persistence.

## Common Components
- **Data Loading:** `data_loader.py` handles parsing the `latest_finance.xlsx` file.
- **Calculations:** `calculations.py` contains the core `FinanceCalculations` class. **All business logic and report generation should reside here** to ensure consistency across both implementations.
- **Models:** `models.py` defines the SQLModel schema used by the FastAPI implementation.

## Development Pitfalls
- **Dual UI Sync:** When adding UI features (like buttons or reports), ensure they are implemented in BOTH `dashboard.py` (Streamlit) and `templates/dashboard.html` (FastAPI/Jinja2) unless specified otherwise.
- **Data Source:** The project relies heavily on `latest_finance.xlsx`. Modifications to the Excel structure require updates to `data_loader.py`.
- **Database vs. Excel:** The FastAPI version migrates Excel data to a database, while Streamlit primarily reads from Excel. Be mindful of which data source is being used.

## Reports
- Text reports are generated via `FinanceCalculations.generate_report_text(data, metrics)`.
- **FastAPI Route:** `/download_report`
- **Streamlit Button:** Located in the sidebar.

## UI Customizations
- **Credit Tab:** Replaced the "Trends" tab. Now contains both detailed Credit Card metrics (Limit, Due, Available) and the Payment Trends charts.
- **Quick Entry / Manage Data:** The "Quick Entry" tab (Streamlit) and "Manage Financial Data" section (FastAPI) have been **disabled** at the user's request. 
    - The code for these features remains in `dashboard.py` (`show_quick_entry`) and `templates/dashboard.html` (inside a `display: none` div) but should not be rendered in the active UI.
