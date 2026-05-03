import os
import shutil
import logging
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

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        logger.error(f"Upload & Migration failed: {str(e)}", exc_info=True)
        return HTMLResponse(
            content="An internal error occurred during file upload and migration. Please check the server logs.", 
            status_code=500
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
        logger.error(f"Dashboard data fetch failed: {str(e)}", exc_info=True)
        return HTMLResponse(
            content="Error loading dashboard data. Please ensure the database is initialized and the Excel file is valid.", 
            status_code=500
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
        logger.error(f"Report generation failed: {str(e)}", exc_info=True)
        return HTMLResponse(
            content="Error generating the financial report. Please check the server logs.", 
            status_code=500
        )

# --- Manual Data Entry Routes (Unified with SQLModel) ---

@app.post("/add_income")
async def add_income(
    source: str = Form(...), amount: float = Form(...), date: str = Form(...)
):
    try:
        service.add_manual_income(source, amount, date)
        return RedirectResponse(url="/dashboard", status_code=303)
    except Exception as e:
        logger.error(f"Add income failed: {str(e)}", exc_info=True)
        return HTMLResponse(content="Failed to add income record.", status_code=500)

@app.post("/update_account")
async def update_account(name: str = Form(...), balance: float = Form(...)):
    try:
        service.update_account_balance(name, balance)
        return RedirectResponse(url="/dashboard", status_code=303)
    except Exception as e:
        logger.error(f"Update account failed: {str(e)}", exc_info=True)
        return HTMLResponse(content="Failed to update account balance.", status_code=500)

@app.post("/add_payment")
async def add_payment(
    card_id: int = Form(...), amount: float = Form(...), date: str = Form(...)
):
    try:
        service.add_manual_payment(card_id, amount, datetime.strptime(date, "%Y-%m-%d"))
        return RedirectResponse(url="/dashboard", status_code=303)
    except Exception as e:
        logger.error(f"Add payment failed: {str(e)}", exc_info=True)
        return HTMLResponse(content="Failed to record credit card payment.", status_code=500)

@app.post("/add_lending")
async def add_lending(
    person: str = Form(...), amount: float = Form(...), due_date: str = Form(...)
):
    try:
        due = datetime.strptime(due_date, "%Y-%m-%d") if due_date else None
        service.add_manual_lending(person, amount, due)
        return RedirectResponse(url="/dashboard", status_code=303)
    except Exception as e:
        logger.error(f"Add lending failed: {str(e)}", exc_info=True)
        return HTMLResponse(content="Failed to record lending transaction.", status_code=500)

@app.post("/add_emi")
async def add_emi(
    provider: str = Form(...), amount: float = Form(...), remaining: str = Form(...)
):
    try:
        service.add_manual_emi(provider, amount, remaining)
        return RedirectResponse(url="/dashboard", status_code=303)
    except Exception as e:
        logger.error(f"Add EMI failed: {str(e)}", exc_info=True)
        return HTMLResponse(content="Failed to record EMI obligation.", status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
