from typing import Dict, Any, List
from datetime import datetime
import pandas as pd
from sqlmodel import Session, select
from models import Account, CreditCard, CCPayment, Lending, Loan, Income, engine
from utils import format_date, clean_currency
from calculations import FinanceCalculations
from data_loader import DataLoader

class FinanceService:
    """
    Unified service layer for fetching and processing financial data.
    """
    def __init__(self):
        self.loader = DataLoader("latest_finance.xlsx")

    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Orchestrates data fetching and calculation for the dashboard.
        """
        # 1. Fetch raw data (Unified from Excel + DB)
        data = self.loader.get_all_data()
        
        # 2. Use FinanceCalculations for metrics
        metrics = FinanceCalculations.get_summary_metrics(data)
        
        # 3. Augment with explanations and extra UI data
        metrics["metric_explanations"] = FinanceCalculations.get_metric_explanations(metrics)
        
        # 4. Format for UI compatibility (e.g., specific lists for FastAPI)
        # We merge everything into a single dictionary
        result = {**data, **metrics}
        
        # Add some FastAPI specific formatting if needed
        result["active_emis"] = [
            {
                "item": row.get("Provider", "Unknown"),
                "amount": row.get("Amt Due", row.get("EMI Amount", 0)),
                "remaining": row.get("EMIs Remaining", row.get("Months Left", "N/A")),
            }
            for _, row in data["emis"].iterrows() if row.get("IsClosed") != "Yes"
        ]
        
        result["active_lendings"] = []
        if not data["lendings"].empty:
            for _, l in data["lendings"].iterrows():
                if l.get("isCleared") != "Yes":
                    due_date = l.get("Due Date")
                    is_overdue = False
                    if due_date and due_date != "N/A":
                        try:
                            is_overdue = pd.to_timestamp(due_date) < datetime.now()
                        except: pass
                    
                    result["active_lendings"].append({
                        "person": l.get("Lent to"),
                        "amount": l.get("Amount Due", l.get("Amount Lent", 0)),
                        "due_date": format_date(due_date),
                        "overdue": is_overdue
                    })

        return result

    def migrate_excel_to_db(self, excel_path: str):
        """Migrates data from Excel to the unified SQLite database."""
        from migrate import migrate_excel_to_sqlite
        migrate_excel_to_sqlite(excel_path)
