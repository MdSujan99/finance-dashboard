# Personal Finance Dashboard

A comprehensive financial management suite featuring a robust PostgreSQL backend and a modern Streamlit intelligence dashboard.

## 📊 Streamlit Intelligence Dashboard (New)
A high-performance visualization tool built with Streamlit and Plotly for deep financial insights.

### Features
- **Smart Data Loading**: Automatically detects and loads the most recent version of your data from either the root or uploads folder.
- **Dynamic Summaries**: Real-time calculation of Net Worth, Asset Allocation, and Debt-to-Income metrics.
- **Interactive Filtering**: Toggle between "Active Only" and "Full History" for Lendings, EMIs, and Loans.
- **Credit Health Gauge**: Visual tracking of your total credit utilization across all cards.
- **Goal Tracking**: Progress monitoring for financial goals (e.g., Emergency Fund) with estimated time to completion.
- **Theme Support**: Fully responsive design with optimized visibility for both Light and Dark modes.

### Setup & Run
```bash
pip install streamlit plotly
streamlit run dashboard.py
```

---

## 💻 Core Application (v2.0 - PostgreSQL)
The underlying system built with FastAPI and SQLModel for data persistence and manual entries.

### Features
- **PostgreSQL Persistence**: Robust data storage for long-term tracking.
- **Manual Data Entry**: Update balances, record payments, and log income directly.
- **Excel Migration**: One-click "Sync" to populate the database from your master file.
- **Modern UI**: Clean, high-contrast Beige, Black, Green, and Red palette.

---

## 🚀 Installation & Setup

### 1. Prerequisites
- Python 3.10+
- **PostgreSQL** installed and running locally.
- A database named `finance`.

### 2. Environment Configuration
Create a `.env` file in the project root:
```env
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=finance
```

### 3. Installation
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install sqlmodel psycopg2-binary python-dotenv streamlit plotly
```

### 4. Database Sync
To populate the database from your Excel file:
```bash
python3 migrate.py
```

### 5. Running the Suite
- **Intelligence Dashboard**: `streamlit run dashboard.py`
- **Data Entry App**: `python3 main.py`

---

## 🛠 Project Structure
- `dashboard.py`: Streamlit UI and visualizations.
- `calculations.py`: Centralized business logic and metric formulas.
- `data_loader.py`: Smart Excel parsing and cleaning logic.
- `main.py`: FastAPI backend for manual data management.
- `models.py`: SQLModel database schemas.

---

## 🎨 Design Language
- **Background**: Light Beige / Theme-Aware Secondary
- **Success**: Green (`#2ECC71`)
- **Danger**: Red (`#E74C3C`)
- **Action**: Black (`#000000`)
