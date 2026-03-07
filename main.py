import os
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional

import pandas as pd
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

# --- Constants & Configuration ---
UPLOAD_DIR = "temp_uploads"
TEMP_FILE_PATH = os.path.join(UPLOAD_DIR, "latest_finance.xlsx")

app = FastAPI(title="Finance Dashboard")
templates = Jinja2Templates(directory="templates")

os.makedirs(UPLOAD_DIR, exist_ok=True)


# --- Utility Functions ---
def clean_currency(value: Any) -> float:
    """Safely converts a value to a float for currency representation."""
    if pd.isna(value) or value == "":
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def format_date(value: Any) -> str:
    """Formats a date value into a YYYY-MM-DD string."""
    if pd.isna(value):
        return "N/A"
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d')
    return str(value)


# --- Core Logic: FinanceParser ---
class FinanceParser:
    """
    Parses a specifically formatted Excel file to extract financial data
    for the dashboard.
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.excel = pd.ExcelFile(file_path)

    def _read_sheet(self, sheet_name: str) -> pd.DataFrame:
        """Safely reads an Excel sheet into a DataFrame."""
        try:
            return self.excel.parse(sheet_name)
        except Exception:
            return pd.DataFrame()

    def parse(self) -> Dict[str, Any]:
        """Orchestrates the parsing of all sections and returns a combined dictionary."""
        data = {}

        # Parse sections
        data['incomes'] = self._parse_incomes()
        
        # Credit card logic
        cc_data = self._parse_credit_cards()
        data.update(cc_data)

        # Lendings
        lendings_data = self._parse_lendings()
        data.update(lendings_data)

        # EMIs & Payments
        data['active_emis'] = self._parse_emis()
        data['payments_history'] = self._parse_payments()

        # Net Worth KPIs
        kpis = self._parse_net_worth_kpis(data['total_lent'], data['total_cc_due'])
        data.update(kpis)

        return data

    def _parse_incomes(self) -> List[Dict[str, Any]]:
        df = self._read_sheet("Incomes")
        incomes = []
        if not df.empty:
            # Drop rows where Amount is missing
            valid_rows = df.dropna(subset=['Amount'])
            for _, row in valid_rows.iterrows():
                incomes.append({
                    "month": str(row.get('Date Of Credit', 'N/A')),
                    "amount": clean_currency(row.get('Amount', 0)),
                    "source": str(row.get('Source', 'N/A'))
                })
        return incomes

    def _parse_credit_cards(self) -> Dict[str, Any]:
        df_nw = self._read_sheet("Net Worth")
        cc_raw_data: Dict[str, Dict[str, float]] = {}
        bob_due = 0.0

        if not df_nw.empty:
            mode = None
            for _, row in df_nw.iterrows():
                # Based on original logic: col 4 is label, col 5 is value
                label = str(row.iloc[4]).strip() if len(row) > 4 else ""
                val = clean_currency(row.iloc[5]) if len(row) > 5 else 0

                if "Credit Card Max Limit" in label:
                    mode = "LIMIT"
                    continue
                elif "Credit Due" in label:
                    mode = "DUE"
                    continue
                elif "Credit Available" in label:
                    mode = "AVAIL"
                    continue
                elif label == "" or "total" in label.lower():
                    mode = None
                    continue

                if mode == "LIMIT":
                    cc_raw_data.setdefault(label, {"limit": 0, "due": 0})["limit"] = val
                elif mode == "DUE":
                    cc_raw_data.setdefault(label, {"limit": 0, "due": 0})["due"] = val
                    if "BOB" in label.upper():
                        bob_due += val

        total_cc_due = 0.0
        total_cc_limit = 0.0
        cc_utilization = []

        for name, vals in cc_raw_data.items():
            limit = vals["limit"]
            due = vals["due"]
            total_cc_due += due
            total_cc_limit += limit
            util_pct = (due / limit * 100) if limit > 0 else 0
            
            cc_utilization.append({
                "name": name,
                "due": due,
                "limit": limit,
                "available": limit - due,
                "utilization": round(util_pct, 1)
            })

        total_util_pct = (total_cc_due / total_cc_limit * 100) if total_cc_limit > 0 else 0

        return {
            'cc_utilization': cc_utilization,
            'bob_due': bob_due,
            'total_cc_due': total_cc_due,
            'total_cc_limit': total_cc_limit,
            'total_cc_utilization': round(total_util_pct, 1)
        }

    def _parse_lendings(self) -> Dict[str, Any]:
        # Map Name -> Due Date from the Lendings sheet
        due_date_map = {}
        df_lendings_sheet = self._read_sheet("Lendings")
        if not df_lendings_sheet.empty:
            for _, row in df_lendings_sheet.iterrows():
                person_name = str(row.get('Lent to', '')).strip().lower()
                due_date = row.get('Due Date')
                if person_name and not pd.isna(due_date):
                    due_date_map[person_name] = due_date

        active_lendings = []
        total_lent = 0.0
        df_nw = self._read_sheet("Net Worth")

        if not df_nw.empty:
            # Original logic: columns 7 (label) and 8 (value) for Lendings
            for r_idx, row in df_nw.iterrows():
                if r_idx == 0: continue # Skip 'Lendings' header

                label = str(row.iloc[7]).strip() if len(row) > 7 else ""
                val = clean_currency(row.iloc[8]) if len(row) > 8 else 0

                if label == "" or "total" in label.lower() or label.lower() == "nan":
                    continue
                if "loans" in label.lower():
                    break

                if val > 0:
                    raw_due_date = due_date_map.get(label.lower())
                    is_overdue = False
                    if isinstance(raw_due_date, datetime):
                        is_overdue = raw_due_date < datetime.now()

                    active_lendings.append({
                        "person": label,
                        "amount": val,
                        "due_date": format_date(raw_due_date),
                        "overdue": is_overdue
                    })
                    total_lent += val

        return {
            'active_lendings': active_lendings,
            'total_lent': total_lent
        }

    def _parse_emis(self) -> List[Dict[str, Any]]:
        df = self._read_sheet("EMIs")
        active_emis = []
        if not df.empty:
            # Filter rows: must have 'Amt Due' and not be 'IsClosed' == 'yes'
            valid_emis = df.dropna(subset=['Amt Due'])
            for _, row in valid_emis.iterrows():
                if str(row.get('IsClosed', '')).strip().lower() != 'yes':
                    active_emis.append({
                        "item": str(row.get('Provider', 'Unknown')),
                        "amount": clean_currency(row.get('Amt Due', 0)),
                        "remaining": str(row.get('EMIs Remaining', 'N/A'))
                    })
        return active_emis

    def _parse_payments(self) -> List[Dict[str, Any]]:
        df = self._read_sheet("Credit Card Payments")
        payments = []
        if not df.empty:
            df['Payment Date'] = pd.to_datetime(df['Payment Date'], errors='coerce')
            df = df.dropna(subset=['Payment Date']).sort_values('Payment Date')
            
            for _, row in df.iterrows():
                payments.append({
                    "date": row['Payment Date'].strftime('%Y-%m-%d'),
                    "amount": clean_currency(row.get('Amount Paid', 0)),
                    "card": str(row.get('Card Name', 'Unknown'))
                })
        return payments

    def _parse_net_worth_kpis(self, total_lent: float, total_cc_due: float) -> Dict[str, Any]:
        df_nw = self._read_sheet("Net Worth")
        total_cash = 0.0
        total_savings = 0.0

        if not df_nw.empty:
            # Based on original inspection: Cash/Savings totals are in col 2 when col 1 is 'total'
            totals_found = []
            for _, row in df_nw.iterrows():
                label = str(row.iloc[1]).lower() if len(row) > 1 else ""
                val = clean_currency(row.iloc[2]) if len(row) > 2 else 0
                if label == "total" and val > 0:
                    totals_found.append(val)
            
            if len(totals_found) >= 1: total_cash = totals_found[0]
            if len(totals_found) >= 2: total_savings = totals_found[1]

        net_worth = total_cash + total_savings + total_lent - total_cc_due

        return {
            "total_cash": total_cash,
            "total_savings": total_savings,
            "net_worth": net_worth
        }


# --- API Routes ---
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Handles Excel file upload and saves it locally."""
    try:
        with open(TEMP_FILE_PATH, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return RedirectResponse(url="/dashboard", status_code=303)
    except Exception as e:
        return HTMLResponse(content=f"Upload failed: {str(e)}", status_code=500)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Parses the latest uploaded file and displays the dashboard."""
    if not os.path.exists(TEMP_FILE_PATH):
        return RedirectResponse(url="/")
    
    try:
        parser = FinanceParser(TEMP_FILE_PATH)
        dashboard_data = parser.parse()
        return templates.TemplateResponse("dashboard.html", {
            "request": request, 
            "data": dashboard_data
        })
    except Exception as e:
        # For production, log the error and show a user-friendly message
        return HTMLResponse(content=f"Error parsing financial data: {str(e)}", status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
