# Personal Finance Intelligence Dashboard

A comprehensive, dual-interface financial management suite. This application unifies your legacy Excel-based tracking with a modern SQL database, providing deep insights, interactive visualizations, and robust data persistence.

## 🚀 Key Features

### 📊 Intelligence Dashboard (Streamlit)
*   **Advanced Metrics:** Real-time tracking of Financial Runway, Wealth Velocity, FI Ratio, and Savings Rate.
*   **Rich Visualizations:** Interactive asset allocation, cash flow, and payment trend charts using Plotly and Altair.
*   **Goal Forecasting:** Estimate time-to-completion for major financial milestones.
*   **Credit Health:** Comprehensive monitoring of credit card limits, dues, and utilization.

### 🌐 Management Web UI (FastAPI)
*   **Centralized Data:** A clean web interface to view your financial snapshot.
*   **Unified Backend:** Powered by a shared `FinanceService` and SQLite database (`finance.db`).
*   **Security:** Production-ready error handling and secure logging.

### 🛠 Robust Data Engine
*   **Non-Destructive Sync:** Migrate data from `latest_finance.xlsx` without losing manually entered UI records.
*   **Anchor-Based Parsing:** Intelligent Excel parsing that adapts to row/column shifts.
*   **Enhanced Reporting:** Download professional, metric-rich text reports generated via Jinja2 templates.

---

## 🛠 Project Architecture

| Component | Responsibility | Tech Stack |
| :--- | :--- | :--- |
| **`dashboard.py`** | Primary Visualization UI | Streamlit, Plotly |
| **`main.py`** | Web Dashboard & Data Management | FastAPI, Jinja2 |
| **`services.py`** | Centralized Service Layer | Python |
| **`calculations.py`** | Core Financial Logic | Pandas |
| **`models.py`** | Database Schema & Persistence | SQLModel, SQLite |
| **`migrate.py`** | Excel-to-DB Migration Logic | SQLModel |

---

## 🏁 Quick Start

### 1. Prerequisites
*   Python 3.10+
*   An Excel file named `latest_finance.xlsx` in the root directory.

### 2. Installation
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Initialize & Sync
Populate the database from your Excel file:
```bash
python3 migrate.py
```

### 4. Launch the Applications
*   **Intelligence Dashboard:**
    ```bash
    streamlit run dashboard.py
    ```
*   **Management Web UI:**
    ```bash
    uvicorn main.py:app --reload
    ```

---

## 🎨 Design Principles
*   **Single Source of Truth:** All data is unified in `finance.db`.
*   **Resiliency:** Use of labels instead of hardcoded indices for Excel parsing.
*   **Modularity:** UI-agnostic service layer allows for easy extension.

---

## 📝 Reporting
The system generates an enhanced **Financial Intelligence Report** (available in both UIs) containing:
*   Summary Ledger (Assets, Cash, Savings, Debts).
*   Health Metrics (Runway, Savings Rate, FI Ratio).
*   Detailed Breakdowns (Active Lendings, EMIs, Payment Trends).
