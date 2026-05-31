import pandas as pd
import logging
from sqlmodel import Session, select
from models import (
    engine, Income, CCPayment, Lending, Loan, Expense, 
    Investment, Account, CreditCard, BudgetLineItem, 
    NetWorthSnapshot, WishlistItem
)

# Setup logging
logger = logging.getLogger(__name__)

class DataLoader:
    """
    Refactored DataLoader that fetches everything from the SQL database.
    Excel dependency is now deprecated.
    """
    def __init__(self, excel_file_path=None):
        # excel_file_path is kept for backward compatibility but ignored
        pass
        
    def get_all_data(self):
        """Fetches all data from the database and formats it for the dashboard."""
        try:
            with Session(engine) as session:
                # 1. Accounts (Cash/Savings/PF)
                accounts = session.exec(select(Account)).all()
                nw_list = []
                pf_value = 0
                for acc in accounts:
                    if acc.type == "PF":
                        pf_value = acc.balance
                    else:
                        nw_list.append({"Name": acc.source, "Balance": acc.balance, "Category": acc.type})
                
                # 2. Credit Cards
                cards = session.exec(select(CreditCard)).all()
                cc_list = []
                for c in cards:
                    cc_list.append({
                        "Card Provider": c.name,
                        "Current Balance": c.current_due,
                        "Max Limit": c.max_limit,
                        "Available Credit": c.available_limit
                    })

                # 3. Incomes (Combined Excel + Manual)
                incomes = session.exec(select(Income)).all()
                income_list = []
                for i in incomes:
                    income_list.append({
                        "Source": i.source,
                        "Amount": i.amount,
                        "Date Of Credit": i.date
                    })

                # 4. Payments
                payment_query = select(CCPayment, CreditCard).join(CreditCard)
                payments_with_cards = session.exec(payment_query).all()
                payment_list = []
                for p, card in payments_with_cards:
                    payment_list.append({
                        "Payment Date": p.date,
                        "Amount Paid": p.amount,
                        "Card Name": card.name
                    })

                # 5. Lendings
                lendings = session.exec(select(Lending)).all()
                lending_list = []
                lendings_nw = []
                for l in lendings:
                    lending_list.append({
                        "Lent to": l.person,
                        "Amount Lent": l.amount,
                        "Due Date": l.due_date,
                        "isCleared": "Yes" if l.is_paid else "No",
                        "Amount Due": l.amount # Simple assumption for consolidated view
                    })
                    if not l.is_paid:
                        lendings_nw.append({"Lent to": l.person, "Amount Lent": l.amount})

                # 6. Loans / EMIs
                loans = session.exec(select(Loan)).all()
                emi_list = []
                loans_nw = []
                for ln in loans:
                    emi_list.append({
                        "Provider": ln.provider,
                        "Amt Due": ln.monthly_emi,
                        "EMIs Remaining": ln.months_left,
                        "IsClosed": "No" if ln.is_active else "Yes"
                    })
                    if ln.is_active:
                        loans_nw.append({
                            "Loan Name": ln.provider,
                            "Amount Due": ln.monthly_emi * (int(ln.months_left) if ln.months_left.isdigit() else 1),
                            "Cleared": "No",
                            "own": "Yes"
                        })

                # 7. Budget
                budget_items = session.exec(select(BudgetLineItem)).all()
                budget_list = []
                fixed_list = []
                for b in budget_items:
                    item_dict = {
                        "Category": b.category,
                        "Subcategory": b.subcategory,
                        "Item": b.item,
                        "Amount": b.amount
                    }
                    budget_list.append(item_dict)
                    
                    # For backward compatibility with 'fixed_expenses' DataFrame
                    if b.subcategory and b.subcategory.upper() == "FIXED":
                        fixed_list.append({
                            "Expense Name": b.item,
                            "Monthly Amount": b.amount
                        })

                # 8. Net Worth History
                history = session.exec(select(NetWorthSnapshot).order_by(NetWorthSnapshot.date)).all()
                history_list = []
                for h in history:
                    history_list.append({
                        "Date": h.date,
                        "Net Worth": h.amount
                    })

                # 9. Wishlist
                wishlist = session.exec(select(WishlistItem)).all()
                wish_list = []
                for w in wishlist:
                    wish_list.append({
                        "Item": w.item,
                        "Expected Cost": w.amount,
                        "Priority": w.priority
                    })

                # 10. Expenses & Investments (Manual)
                expenses = session.exec(select(Expense)).all()
                investments = session.exec(select(Investment)).all()

            # Convert all to DataFrames
            data = {
                "incomes": pd.DataFrame(income_list) if income_list else pd.DataFrame(columns=["Source", "Amount", "Date Of Credit"]),
                "fixed_expenses": pd.DataFrame(fixed_list) if fixed_list else pd.DataFrame(columns=["Expense Name", "Monthly Amount"]),
                "nw_history": pd.DataFrame(history_list) if history_list else pd.DataFrame(columns=["Date", "Net Worth"]),
                "credit_cards": pd.DataFrame(cc_list),
                "payments": pd.DataFrame(payment_list) if payment_list else pd.DataFrame(columns=["Payment Date", "Amount Paid"]),
                "lendings": pd.DataFrame(lending_list) if lending_list else pd.DataFrame(columns=["Lent to", "Amount Lent", "Due Date", "isCleared", "Amount Due"]),
                "lendings_nw": pd.DataFrame(lendings_nw),
                "emis": pd.DataFrame(emi_list) if emi_list else pd.DataFrame(columns=["Provider", "Amt Due", "EMIs Remaining", "IsClosed"]),
                "wishlist": pd.DataFrame(wish_list) if wish_list else pd.DataFrame(columns=["Item", "Expected Cost", "Priority"]),
                "net_worth": pd.DataFrame(nw_list),
                "loans": pd.DataFrame(loans_nw),
                "pf_value": pf_value,
                "expenses": pd.DataFrame([e.dict() for e in expenses]) if expenses else pd.DataFrame(),
                "investments": pd.DataFrame([inv.dict() for inv in investments]) if investments else pd.DataFrame(),
                "budget": pd.DataFrame(budget_list) if budget_list else pd.DataFrame(columns=["Category", "Subcategory", "Item", "Amount"])
            }
            return data

        except Exception as e:
            logger.error(f"Error loading data from DB: {e}")
            return {}
