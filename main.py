import os
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional

import pandas as pd
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, func

from models import engine, Account, CreditCard, CCPayment, Lending, Loan, Income

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
    if isinstance(value, (int, float)):
        return float(value)
    
    # If string, remove currency symbols, commas, and spaces
    try:
        clean_val = str(value).replace('₹', '').replace(',', '').strip()
        # Some values might have multiple spaces or other characters
        import re
        clean_val = re.sub(r'[^\d.]', '', clean_val)
        return float(clean_val) if clean_val else 0.0
    except (ValueError, TypeError):
        return 0.0


def format_date(value: Any) -> str:
    """Formats a date value into a YYYY-MM-DD string."""
    if pd.isna(value) or value is None:
        return "N/A"
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d')
    return str(value)


# --- Core Logic: FinanceService (SQLite) ---
class FinanceService:
    """
    Service layer to fetch financial data from SQLite database.
    """
    def __init__(self, session: Session):
        self.session = session

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Fetches all data required for the dashboard."""
        data = {}

        # 1. Accounts (Cash/Savings)
        accounts = self.session.exec(select(Account)).all()
        data['total_cash'] = next((a.balance for a in accounts if "Cash" in a.name), 0.0)
        data['total_savings'] = next((a.balance for a in accounts if "Savings" in a.name), 0.0)

        # 2. Credit Cards
        cards = self.session.exec(select(CreditCard)).all()
        total_cc_due = 0.0
        total_cc_limit = 0.0
        total_actual_used = 0.0
        cc_utilization = []
        bob_due = 0.0

        for card in cards:
            total_cc_due += card.current_due
            total_cc_limit += card.max_limit
            
            # Actual used includes unbilled and EMIs
            # limit - available = total used
            # If available is 0, we fallback to current_due
            actual_used = card.max_limit - card.available_limit if card.available_limit > 0 else card.current_due
            total_actual_used += actual_used

            if "BOB" in card.name.upper():
                bob_due += card.current_due
            
            util_pct = (actual_used / card.max_limit * 100) if card.max_limit > 0 else 0
            cc_utilization.append({
                "name": card.name,
                "due": card.current_due,
                "unbilled": actual_used - card.current_due,
                "total_used": actual_used,
                "limit": card.max_limit,
                "available": card.available_limit,
                "utilization": round(util_pct, 1)
            })
        
        data['cc_utilization'] = cc_utilization
        data['card_info'] = [{"id": card.id, "name": card.name} for card in cards]
        data['total_cc_due'] = total_cc_due
        data['total_cc_limit'] = total_cc_limit
        data['total_actual_used'] = total_actual_used
        data['bob_due'] = bob_due
        data['total_cc_utilization'] = round((total_actual_used / total_cc_limit * 100), 1) if total_cc_limit > 0 else 0
        data['total_credit_available'] = total_cc_limit - total_actual_used
        data['total_available_funds'] = data['total_cash'] + data['total_savings'] + data['total_credit_available']

        # 3. Lendings
        lendings = self.session.exec(select(Lending)).all()
        active_lendings = []
        total_lent = 0.0
        now = datetime.now()

        for l in lendings:
            if not l.is_paid:
                is_overdue = False
                if l.due_date:
                    is_overdue = l.due_date < now
                
                active_lendings.append({
                    "person": l.person,
                    "amount": l.amount,
                    "due_date": format_date(l.due_date),
                    "overdue": is_overdue
                })
                total_lent += l.amount
        
        data['active_lendings'] = active_lendings
        data['total_lent'] = total_lent

        # 4. EMIs
        loans = self.session.exec(select(Loan).where(Loan.is_active == True)).all()
        data['active_emis'] = [{
            "item": loan.provider,
            "amount": loan.monthly_emi,
            "remaining": loan.months_left
        } for loan in loans]

        # 5. Incomes
        incomes = self.session.exec(select(Income)).all()
        data['incomes'] = [{
            "month": inc.date,
            "amount": inc.amount,
            "source": inc.source
        } for inc in incomes]

        # 6. Payments History
        payments = self.session.exec(
            select(CCPayment, CreditCard.name)
            .join(CreditCard)
            .order_by(CCPayment.date)
        ).all()
        
        data['payments_history'] = [{
            "date": p[0].date.strftime('%Y-%m-%d'),
            "amount": p[0].amount,
            "card": p[1]
        } for p in payments]

        # 7. Net Worth
        data['net_worth'] = data['total_cash'] + data['total_savings'] + data['total_lent'] - data['total_actual_used']

        # 8. Explanations
        from calculations import FinanceCalculations
        data['metric_explanations'] = FinanceCalculations.get_metric_explanations(data)

        # 9. Budget (from Excel fallback as it's not yet in SQLite)
        from data_loader import DataLoader
        loader = DataLoader("latest_finance.xlsx")
        excel = loader.load_excel()
        budget_df = loader._parse_monthly_budget(excel)
        if not budget_df.empty:
            data['budget'] = budget_df.to_dict('records')
        else:
            data['budget'] = []

        return data


# --- Original Core Logic: FinanceParser (Kept for Migration/Upload fallback) ---
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
        kpis = self._parse_net_worth_kpis(data['total_lent'], data['total_actual_used'])
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
                    cc_raw_data.setdefault(label, {"limit": 0, "due": 0, "available": 0})["limit"] = val
                elif mode == "DUE":
                    cc_raw_data.setdefault(label, {"limit": 0, "due": 0, "available": 0})["due"] = val
                    if "BOB" in label.upper():
                        bob_due += val
                elif mode == "AVAIL":
                    cc_raw_data.setdefault(label, {"limit": 0, "due": 0, "available": 0})["available"] = val

        total_cc_due = 0.0
        total_cc_limit = 0.0
        total_actual_used = 0.0
        cc_utilization = []

        for name, vals in cc_raw_data.items():
            limit = vals["limit"]
            due = vals["due"]
            available = vals["available"]
            total_cc_due += due
            total_cc_limit += limit
            
            actual_used = limit - available if available > 0 else due
            total_actual_used += actual_used
            
            util_pct = (actual_used / limit * 100) if limit > 0 else 0
            
            cc_utilization.append({
                "name": name,
                "due": due,
                "unbilled": actual_used - due,
                "total_used": actual_used,
                "limit": limit,
                "available": available,
                "utilization": round(util_pct, 1)
            })

        total_util_pct = (total_actual_used / total_cc_limit * 100) if total_cc_limit > 0 else 0

        return {
            'cc_utilization': cc_utilization,
            'bob_due': bob_due,
            'total_cc_due': total_cc_due,
            'total_cc_limit': total_cc_limit,
            'total_actual_used': total_actual_used,
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
            # Convert Payment Date to datetime
            df['Payment Date'] = pd.to_datetime(df['Payment Date'], errors='coerce')
            df = df.dropna(subset=['Payment Date'])
            
            # Clean and convert Amount Paid to numeric
            df['Amount Paid'] = df['Amount Paid'].apply(clean_currency)
            
            # Sort by date
            df = df.sort_values('Payment Date')
            
            for _, row in df.iterrows():
                payments.append({
                    "date": row['Payment Date'].strftime('%Y-%m-%d'),
                    "amount": row['Amount Paid'],
                    "card": str(row['Card Name']).strip()
                })
        return payments

    def _parse_net_worth_kpis(self, total_lent: float, total_actual_used: float) -> Dict[str, Any]:
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

        net_worth = total_cash + total_savings + total_lent - total_actual_used

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
    """Handles Excel file upload and triggers a fresh migration."""
    try:
        with open(TEMP_FILE_PATH, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Trigger migration from Excel to DB
        from migrate import migrate_excel_to_sqlite
        migrate_excel_to_sqlite(TEMP_FILE_PATH)
        
        return RedirectResponse(url="/dashboard", status_code=303)
    except Exception as e:
        return HTMLResponse(content=f"Upload & Migration failed: {str(e)}", status_code=500)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Fetches dashboard data from SQLite."""
    try:
        with Session(engine) as session:
            service = FinanceService(session)
            dashboard_data = service.get_dashboard_data()
            
        return templates.TemplateResponse("dashboard.html", {
            "request": request, 
            "data": dashboard_data,
            "now_date": datetime.now().strftime('%Y-%m-%d')
        })
    except Exception as e:
        return HTMLResponse(content=f"Error fetching data from database: {str(e)}", status_code=500)


# --- Manual Data Entry Routes ---

@app.post("/add_income")
async def add_income(source: str = Form(...), amount: float = Form(...), date: str = Form(...)):
    with Session(engine) as session:
        session.add(Income(source=source, amount=amount, date=date))
        session.commit()
    return RedirectResponse(url="/dashboard", status_code=303)


@app.post("/update_account")
async def update_account(name: str = Form(...), balance: float = Form(...)):
    with Session(engine) as session:
        statement = select(Account).where(Account.name == name)
        account = session.exec(statement).first()
        if account:
            account.balance = balance
            account.updated_at = datetime.utcnow()
            session.add(account)
            session.commit()
    return RedirectResponse(url="/dashboard", status_code=303)


@app.post("/add_payment")
async def add_payment(card_id: int = Form(...), amount: float = Form(...), date: str = Form(...)):
    with Session(engine) as session:
        session.add(CCPayment(
            card_id=card_id,
            amount=amount,
            date=datetime.strptime(date, '%Y-%m-%d')
        ))
        # Update current due and available limit on the card automatically
        statement = select(CreditCard).where(CreditCard.id == card_id)
        card = session.exec(statement).one()
        card.current_due -= amount
        card.available_limit += amount
        session.add(card)
        session.commit()
    return RedirectResponse(url="/dashboard", status_code=303)


@app.post("/add_lending")
async def add_lending(person: str = Form(...), amount: float = Form(...), due_date: str = Form(...)):
    with Session(engine) as session:
        due = datetime.strptime(due_date, '%Y-%m-%d') if due_date else None
        session.add(Lending(person=person, amount=amount, due_date=due))
        session.commit()
    return RedirectResponse(url="/dashboard", status_code=303)


@app.post("/add_emi")
async def add_emi(provider: str = Form(...), amount: float = Form(...), remaining: str = Form(...)):
    with Session(engine) as session:
        session.add(Loan(provider=provider, monthly_emi=amount, months_left=remaining))
        session.commit()
    return RedirectResponse(url="/dashboard", status_code=303)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
