# Personal Finance Dashboard (v2.0 - PostgreSQL)

A robust financial management system built with FastAPI, SQLModel, and PostgreSQL. It allows you to track net worth, credit card utilization, lendings, EMIs, and income history through both automated Excel sync and manual entry.

## Features
- **PostgreSQL Persistence**: Robust data storage for long-term tracking.
- **Manual Data Entry**: Update balances, record payments, and log income directly in the dashboard.
- **Excel Migration**: One-click "Sync" to populate the database from a formatted Excel file.
- **Interactive Visuals**: Filterable credit card payment history and utilization charts.
- **Modern UI**: Clean, high-contrast Beige, Black, Green, and Red palette.

---

## 🚀 Setup & Installation

### 1. Prerequisites
- Python 3.10+
- **PostgreSQL** installed and running locally.
- A database named `finance`.

### 2. Environment Configuration
Create a `.env` file in the project root with your Postgres credentials:
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
pip install sqlmodel psycopg2-binary python-dotenv
```

### 4. Initial Data Migration
To populate the database from your existing Excel file:
```bash
python3 migrate.py
```
*Note: This will reset the database and perform a fresh import from `temp_uploads/latest_finance.xlsx`.*

### 5. Start the Application
```bash
python3 main.py
```
Visit `http://localhost:8000` to view your dashboard.

---

## 🛠 Database Management

### Connecting via DBeaver
1. **New Connection** -> Select **PostgreSQL**.
2. **Host**: `localhost` | **Port**: `5432`.
3. **Database**: `finance`.
4. **Username/Password**: As defined in your `.env`.

### Resetting the Database
To wipe all data and start fresh from the Excel file, simply run:
```bash
python3 migrate.py
```
This script automatically drops all tables and recreates them to ensure a clean sync.

---

## 🎨 Color Palette
- **Background**: Light Beige (`#f5f5dc`)
- **Text/Primary**: Black (`#000000`)
- **Success/Good**: Green (`#008000`)
- **Danger/Bad**: Red (`#ff0000`)
