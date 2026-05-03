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

    # --- Manual Data Entry Methods ---

    def add_manual_income(self, source: str, amount: float, date: str):
        with Session(engine) as session:
            session.add(Income(source=source, amount=amount, date=date, is_manual=True))
            session.commit()

    def update_account_balance(self, name: str, balance: float):
        with Session(engine) as session:
            statement = select(Account).where(Account.name == name)
            account = session.exec(statement).first()
            if account:
                account.balance = balance
                account.updated_at = datetime.utcnow()
                account.is_manual = True
                session.add(account)
                session.commit()

    def add_manual_payment(self, card_id: int, amount: float, date: datetime):
        with Session(engine) as session:
            statement = select(CreditCard).where(CreditCard.id == card_id)
            card = session.exec(statement).one()
            
            session.add(
                CCPayment(
                    card_id=card_id, amount=amount, date=date, is_manual=True
                )
            )
            
            card.current_due -= amount
            card.available_limit += amount
            card.is_manual = True
            session.add(card)
            session.commit()

    def add_manual_lending(self, person: str, amount: float, due_date: Optional[datetime]):
        with Session(engine) as session:
            session.add(Lending(person=person, amount=amount, due_date=due_date, is_manual=True))
            session.commit()

    def add_manual_emi(self, provider: str, amount: float, remaining: str):
        with Session(engine) as session:
            session.add(Loan(provider=provider, monthly_emi=amount, months_left=remaining, is_manual=True))
            session.commit()
