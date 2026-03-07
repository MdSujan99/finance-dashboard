import os
import shutil
import pandas as pd
from datetime import datetime
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import List, Dict, Any

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Temporary storage for the uploaded file path
# In a real app, this would be session-based or in a DB
UPLOAD_DIR = "temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
TEMP_FILE_PATH = os.path.join(UPLOAD_DIR, "latest_finance.xlsx")

def clean_currency(value):
    """Directly convert to float, assuming no currency symbols."""
    if pd.isna(value) or value == "":
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0

def format_date(value):
    """Handle datetime objects or strings."""
    if pd.isna(value):
        return "N/A"
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d')
    return str(value)

def parse_excel(file_path: str) -> Dict[str, Any]:
    excel = pd.ExcelFile(file_path)
    data = {}

    # 1. Incomes
    df_incomes = pd_read_sheet(excel, "Incomes")
    incomes_summary = []
    if not df_incomes.empty:
        for _, row in df_incomes.dropna(subset=['Amount']).iterrows():
            incomes_summary.append({
                "month": str(row.get('Date Of Credit', 'N/A')),
                "amount": clean_currency(row.get('Amount', 0)),
                "source": str(row.get('Source', 'N/A'))
            })
    data['incomes'] = incomes_summary

    # 2. Credit Card Utilisation (Parsed from Net Worth sheet)
    df_nw = pd_read_sheet(excel, "Net Worth")
    cc_data = {}
    bob_due = 0.0
    
    if not df_nw.empty:
        mode = None
        for _, row in df_nw.iterrows():
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
                cc_data.setdefault(label, {"limit": 0, "due": 0})["limit"] = val
            elif mode == "DUE":
                cc_data.setdefault(label, {"limit": 0, "due": 0})["due"] = val
                if "BOB" in label.upper():
                    bob_due += val

    total_cc_due = 0.0
    total_cc_limit = 0.0
    cc_utilization = []
    for name, vals in cc_data.items():
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
    
    data['cc_utilization'] = cc_utilization
    data['bob_due'] = bob_due
    data['total_cc_due'] = total_cc_due
    data['total_cc_limit'] = total_cc_limit
    data['total_cc_utilization'] = round((total_cc_due / total_cc_limit * 100), 1) if total_cc_limit > 0 else 0

    # 3. Lendings (Names/Amounts from Net Worth, Dates from Lendings sheet)
    active_lendings = []
    total_lent = 0.0
    
    # First, get a mapping of Name -> Due Date from the Lendings sheet
    due_date_map = {}
    df_lendings_sheet = pd_read_sheet(excel, "Lendings")
    if not df_lendings_sheet.empty:
        for _, row in df_lendings_sheet.iterrows():
            person_name = str(row.get('Lent to', '')).strip().lower()
            due_date = row.get('Due Date')
            if person_name and not pd.isna(due_date):
                due_date_map[person_name] = due_date

    if not df_nw.empty:
        # Looking at columns Unnamed: 7 and Unnamed: 8 for Lendings
        for r_idx, row in df_nw.iterrows():
            if r_idx == 0: continue # Skip header row 'Lendings'
            
            label = str(row.iloc[7]).strip() if len(row) > 7 else ""
            val = clean_currency(row.iloc[8]) if len(row) > 8 else 0
            
            if label == "" or "total" in label.lower() or "nan" == label.lower():
                continue
            
            if "loans" in label.lower():
                break

            if val > 0:
                # Find the due date using the mapping (case-insensitive)
                raw_due_date = due_date_map.get(label.lower())
                
                active_lendings.append({
                    "person": label,
                    "amount": val,
                    "due_date": format_date(raw_due_date) if raw_due_date else "N/A",
                    "overdue": (raw_due_date < datetime.now() if isinstance(raw_due_date, datetime) else False)
                })
                total_lent += val
                
    data['active_lendings'] = active_lendings
    data['total_lent'] = total_lent

    # 4. EMIs
    df_emis = pd_read_sheet(excel, "EMIs")
    active_emis = []
    if not df_emis.empty:
        for _, row in df_emis.dropna(subset=['Amt Due']).iterrows():
            if str(row.get('IsClosed', '')).strip().lower() != 'yes':
                active_emis.append({
                    "item": str(row.get('Provider', 'Unknown')),
                    "amount": clean_currency(row.get('Amt Due', 0)),
                    "remaining": str(row.get('EMIs Remaining', 'N/A'))
                })
    data['active_emis'] = active_emis

    # 6. Credit Card Payments (History)
    df_payments = pd_read_sheet(excel, "Credit Card Payments")
    payments_history = []
    if not df_payments.empty:
        # Sort by date
        df_payments['Payment Date'] = pd.to_datetime(df_payments['Payment Date'], errors='coerce')
        df_payments = df_payments.dropna(subset=['Payment Date']).sort_values('Payment Date')
        
        for _, row in df_payments.iterrows():
            payments_history.append({
                "date": row['Payment Date'].strftime('%Y-%m-%d'),
                "amount": clean_currency(row.get('Amount Paid', 0)),
                "card": str(row.get('Card Name', 'Unknown'))
            })
    data['payments_history'] = payments_history

    # 5. Net Worth KPIs (Parsed from Net Worth sheet)
    data.update({"total_cash": 0, "total_savings": 0, "net_worth": 0})
    if not df_nw.empty:
        # Based on inspection: 
        # Cash total is in Unnamed: 2 (index 2) where Unnamed: 1 (index 1) is 'total'
        # First 'total' is Cash, second is Savings
        totals_found = []
        for r_idx, row in df_nw.iterrows():
            label = str(row.iloc[1]).lower() if len(row) > 1 else ""
            val = clean_currency(row.iloc[2]) if len(row) > 2 else 0
            if label == "total" and val > 0:
                totals_found.append(val)
        
        if len(totals_found) >= 1: data['total_cash'] = totals_found[0]
        if len(totals_found) >= 2: data['total_savings'] = totals_found[1]
        
    # Final Net Worth Calculation
    data['net_worth'] = (data['total_cash'] + data['total_savings'] + 
                         data['total_lent'] - data['total_cc_due'])

    return data

def pd_read_sheet(excel_obj, sheet_name):
    """Helper to read sheet safely."""
    try:
        return excel_obj.parse(sheet_name)
    except:
        return pd.DataFrame()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

@app.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    with open(TEMP_FILE_PATH, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return RedirectResponse(url="/dashboard", status_code=303)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not os.path.exists(TEMP_FILE_PATH):
        return RedirectResponse(url="/")
    
    try:
        dashboard_data = parse_excel(TEMP_FILE_PATH)
        return templates.TemplateResponse("dashboard.html", {
            "request": request, 
            "data": dashboard_data
        })
    except Exception as e:
        return HTMLResponse(content=f"Error parsing Excel: {str(e)}", status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
