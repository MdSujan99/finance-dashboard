import os
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional

import pandas as pd
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import RedirectResponse, HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, func

from models import engine, Account, CreditCard, CCPayment, Lending, Loan, Income
from services import FinanceService
from utils import clean_currency, format_date

# --- Constants & Configuration ---
UPLOAD_DIR = "temp_uploads"
TEMP_FILE_PATH = os.path.join(UPLOAD_DIR, "latest_finance.xlsx")

app = FastAPI(title="Finance Dashboard")
templates = Jinja2Templates(directory="templates")

os.makedirs(UPLOAD_DIR, exist_ok=True)
service = FinanceService()

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
        service.migrate_excel_to_db(TEMP_FILE_PATH)

        return RedirectResponse(url="/dashboard", status_code=303)
    except Exception as e:
        return HTMLResponse(
            content=f"Upload & Migration failed: {str(e)}", status_code=500
        )

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Fetches dashboard data via FinanceService."""
    try:
        dashboard_data = service.get_dashboard_data()

        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "data": dashboard_data,
                "now_date": datetime.now().strftime("%Y-%m-%d"),
            },
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return HTMLResponse(
            content=f"Error fetching data: {str(e)}", status_code=500
        )

@app.get("/download_report")
async def download_report():
    """Generates and downloads a text-based financial report."""
    try:
        data = service.get_dashboard_data()
        from calculations import FinanceCalculations
        report_content = FinanceCalculations.generate_report_text(data, data)

        return PlainTextResponse(
            content=report_content,
            headers={
                "Content-Disposition": f"attachment; filename=finance_report_{datetime.now().strftime('%Y%m%d')}.txt"
            },
        )
    except Exception as e:
        return HTMLResponse(
            content=f"Error generating report: {str(e)}", status_code=500
        )

# --- Manual Data Entry Routes (Unified with SQLModel) ---

@app.post("/add_income")
async def add_income(
    source: str = Form(...), amount: float = Form(...), date: str = Form(...)
):
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
async def add_payment(
    card_id: int = Form(...), amount: float = Form(...), date: str = Form(...)
):
    with Session(engine) as session:
        # Update current due and available limit on the card automatically
        statement = select(CreditCard).where(CreditCard.id == card_id)
        card = session.exec(statement).one()
        
        session.add(
            CCPayment(
                card_id=card_id, amount=amount, date=datetime.strptime(date, "%Y-%m-%d")
            )
        )
        
        card.current_due -= amount
        card.available_limit += amount
        session.add(card)
        session.commit()
    return RedirectResponse(url="/dashboard", status_code=303)

@app.post("/add_lending")
async def add_lending(
    person: str = Form(...), amount: float = Form(...), due_date: str = Form(...)
):
    with Session(engine) as session:
        due = datetime.strptime(due_date, "%Y-%m-%d") if due_date else None
        session.add(Lending(person=person, amount=amount, due_date=due))
        session.commit()
    return RedirectResponse(url="/dashboard", status_code=303)

@app.post("/add_emi")
async def add_emi(
    provider: str = Form(...), amount: float = Form(...), remaining: str = Form(...)
):
    with Session(engine) as session:
        session.add(Loan(provider=provider, monthly_emi=amount, months_left=remaining))
        session.commit()
    return RedirectResponse(url="/dashboard", status_code=303)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
