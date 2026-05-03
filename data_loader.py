import pandas as pd
import os
import logging
from sqlmodel import Session, select
import numpy as np
from models import engine, DB_NAME
from utils import clean_currency, get_value_by_label

# Setup logging
logger = logging.getLogger(__name__)

class DataLoader:
    _cache = {}
    _last_mtime = None
    _cached_excel_path = None

    def __init__(self, excel_file_path="latest_finance.xlsx"):
        self.excel_file_path = excel_file_path
        
    def load_excel(self):
        # Look for files in root and temp_uploads
        root_path = self.excel_file_path
        temp_path = os.path.join("temp_uploads", self.excel_file_path)
        
        candidates = []
        if os.path.exists(root_path):
            candidates.append((root_path, os.path.getmtime(root_path)))
        if os.path.exists(temp_path):
            candidates.append((temp_path, os.path.getmtime(temp_path)))
            
        if not candidates:
            return None
            
        # Pick the one with the latest modification time
        latest_file, mtime = max(candidates, key=lambda x: x[1])
        
        # Check if we can use cached data
        if DataLoader._cached_excel_path == latest_file and DataLoader._last_mtime == mtime:
            return DataLoader._cache.get('excel_obj')

        logger.info(f"Parsing Excel file: {latest_file}")
        try:
            excel_obj = pd.ExcelFile(latest_file)
            # Update cache
            DataLoader._cache = {'excel_obj': excel_obj}
            DataLoader._last_mtime = mtime
            DataLoader._cached_excel_path = latest_file
            return excel_obj
        except Exception as e:
            logger.error(f"Error loading Excel file {latest_file}: {e}")
            return None

    def get_sheet_data(self, excel, sheet_name):
        try:
            if excel is None or sheet_name not in excel.sheet_names:
                return pd.DataFrame()
            df = excel.parse(sheet_name)
            
            # Prevent raw 'nan' from appearing in output
            for col in df.columns:
                if df[col].dtype == object:
                    df[col] = df[col].fillna("Unknown")
                else:
                    df[col] = df[col].fillna(0)
                    
            # Standard cleanup for most sheets
            amount_cols = ['Amount', 'Balance', 'Current Balance', 'Max Limit', 
                           'Amount Outstanding', 'EMI Amount', 'Expected Cost', 'Amt Due', 
                           'Amount Lent', 'Amount Due', 'Budget', 'Actual Cost', 
                           'Amount Paid', 'Monthly Amount', 'Net Worth']
            for col in amount_cols:
                if col in df.columns:
                    df[col] = df[col].apply(clean_currency)
            return df
        except Exception as e:
            logger.error(f"Error parsing sheet {sheet_name}: {e}")
            return pd.DataFrame()

    def _parse_net_worth_details(self, excel):
        """Specially parses the 'Net Worth' sheet using anchor-based searching."""
        if excel is None:
            return {
                "credit_cards_df": pd.DataFrame(),
                "net_worth_df": pd.DataFrame(),
                "lendings_nw_df": pd.DataFrame(),
                "loans_nw_df": pd.DataFrame(),
                "pf_value": 0
            }
            
        try:
            df = excel.parse('Net Worth', header=None)
            
            # Robust extraction using labels (Anchor-Based)
            pf_val = get_value_by_label(df, "PF Account", col_offset=1)
            if pf_val == 0: # Fallback
                 pf_val = get_value_by_label(df, "PF", col_offset=1)

            # Loans
            loans_nw = []
            loan_val = get_value_by_label(df, "Loans", col_offset=1)
            if loan_val > 0:
                loans_nw.append({
                    "Loan Name": "Owed Loan",
                    "Amount Due": loan_val,
                    "Cleared": "No",
                    "own": "Yes"
                })

            cc_raw_data = {}
            cash_savings = []
            lendings_nw = []

            mode_col4 = None
            for idx, row in df.iterrows():
                # Parse Credit Card info
                label_cc = str(row.iloc[4]).strip() if len(row) > 4 else ""
                val_cc = clean_currency(row.iloc[5]) if len(row) > 5 else 0

                if "Credit Available" in label_cc: mode_col4 = "AVAIL"
                elif "Credit Card Max Limit" in label_cc: mode_col4 = "LIMIT"
                elif "Credit Due" in label_cc: mode_col4 = "DUE"
                elif label_cc == "" or "total" in label_cc.lower(): mode_col4 = None
                elif mode_col4:
                    cc_raw_data.setdefault(label_cc, {"limit": 0, "due": 0, "available": 0})
                    if mode_col4 == "AVAIL": cc_raw_data[label_cc]["available"] = val_cc
                    elif mode_col4 == "LIMIT": cc_raw_data[label_cc]["limit"] = val_cc
                    elif mode_col4 == "DUE": cc_raw_data[label_cc]["due"] = val_cc

                # Parse Cash/Savings
                label_cash = str(row.iloc[1]).strip() if len(row) > 1 else ""
                val_cash = clean_currency(row.iloc[2]) if len(row) > 2 else 0
                if label_cash and val_cash > 0 and label_cash.lower() != 'nan' and label_cash.lower() != 'total':
                    if "PF" not in label_cash.upper():
                        cat = "Savings" if any(x in label_cash.upper() for x in ["SAVINGS", "FD", "HDFC", "SLICE FD"]) else "Cash"
                        cash_savings.append({"Name": label_cash, "Balance": val_cash, "Category": cat})

                # Parse Lendings
                label_lend = str(row.iloc[7]).strip() if len(row) > 7 else ""
                val_lend = clean_currency(row.iloc[8]) if len(row) > 8 else 0
                if label_lend and val_lend > 0 and "total" not in label_lend.lower() and label_lend.lower() != 'nan' and "lendings" not in label_lend.lower() and "loans" not in label_lend.lower():
                    lendings_nw.append({"Lent to": label_lend, "Amount Lent": val_lend})

            # Convert CC raw data to DataFrame
            cc_list = []
            for name, vals in cc_raw_data.items():
                cc_list.append({
                    "Card Provider": name,
                    "Current Balance": vals["due"],
                    "Max Limit": vals["limit"],
                    "Available Credit": vals["available"]
                })

            return {
                "credit_cards_df": pd.DataFrame(cc_list),
                "net_worth_df": pd.DataFrame(cash_savings),
                "lendings_nw_df": pd.DataFrame(lendings_nw),
                "loans_nw_df": pd.DataFrame(loans_nw),
                "pf_value": pf_val
            }
        except Exception as e:
            logger.error(f"Error parsing Net Worth details: {e}")
            return {
                "credit_cards_df": pd.DataFrame(),
                "net_worth_df": pd.DataFrame(),
                "lendings_nw_df": pd.DataFrame(),
                "loans_nw_df": pd.DataFrame(),
                "pf_value": 0
            }

    def _parse_monthly_budget(self, excel):
        """Parses the 'Monthly Budget' sheet with its hierarchical structure."""
        if excel is None:
            return pd.DataFrame()
        
        if 'Monthly Budget' not in excel.sheet_names:
            return pd.DataFrame()
            
        try:
            df = excel.parse('Monthly Budget', header=None)
            data = []
            current_cat = None
            current_sub = None
            current_group = None

            for idx, row in df.iterrows():
                row_len = len(row)
                
                def get_val(col_idx):
                    if col_idx >= row_len: return None
                    v = row.iloc[col_idx]
                    if pd.isna(v): return None
                    s = str(v).strip()
                    if s.lower() in ['nan', 'none', '']: return None
                    return s

                cat = get_val(1)
                sub = get_val(2)
                group = get_val(3)
                item = get_val(4)
                amount = clean_currency(row.iloc[5]) if row_len > 5 else 0
                
                if cat: 
                    current_cat = cat
                    current_sub = None
                    current_group = None
                if sub: 
                    current_sub = sub
                    current_group = None
                if group: 
                    current_group = group
                
                if amount > 0:
                    parts = []
                    if current_group: parts.append(current_group)
                    if item: parts.append(item)
                    full_item = ' - '.join(parts) if parts else current_sub or current_cat
                    
                    data.append({
                        'Category': current_cat,
                        'Subcategory': current_sub,
                        'Item': full_item,
                        'Amount': amount
                    })

            return pd.DataFrame(data)
        except Exception as e:
            logger.error(f"Error parsing Monthly Budget: {e}")
            return pd.DataFrame()

    def get_all_data(self):
        """Fetches all data, prioritizing database for dynamic entries."""
        try:
            from models import Income, CCPayment, Lending, Expense, Investment
            with Session(engine) as session:
                # IMPORTANT: Only fetch manual entries from SQLite to avoid duplication with Excel
                sqlite_income = pd.DataFrame([i.dict() for i in session.exec(select(Income).where(Income.is_manual == True)).all()])
                sqlite_cc_payments = pd.DataFrame([p.dict() for p in session.exec(select(CCPayment).where(CCPayment.is_manual == True)).all()])
                sqlite_lending = pd.DataFrame([l.dict() for l in session.exec(select(Lending).where(Lending.is_manual == True)).all()])
                sqlite_expenses = pd.DataFrame([e.dict() for e in session.exec(select(Expense).where(Expense.is_manual == True)).all()])
                sqlite_investments = pd.DataFrame([inv.dict() for inv in session.exec(select(Investment).where(Investment.is_manual == True)).all()])
        except Exception as e:
            logger.error(f"Error loading from DB: {e}")
            sqlite_income = pd.DataFrame()
            sqlite_cc_payments = pd.DataFrame()
            sqlite_lending = pd.DataFrame()
            sqlite_expenses = pd.DataFrame()
            sqlite_investments = pd.DataFrame()

        excel = self.load_excel()
        nw_details = self._parse_net_worth_details(excel)
        
        excel_incomes = self.get_sheet_data(excel, 'Incomes')
        excel_payments = self.get_sheet_data(excel, 'Credit Card Payments')
        excel_lendings = self.get_sheet_data(excel, 'Lendings')
        
        data = {
            "incomes": self._format_income(sqlite_income, excel_incomes),
            "fixed_expenses": self.get_sheet_data(excel, 'Fixed Expenses'),
            "nw_history": self.get_sheet_data(excel, 'Net Worth History'),
            "credit_cards": nw_details["credit_cards_df"],
            "payments": self._format_cc_payments(sqlite_cc_payments, excel_payments),
            "lendings": self._format_lendings(sqlite_lending, excel_lendings),
            "lendings_nw": nw_details["lendings_nw_df"],
            "emis": self.get_sheet_data(excel, 'EMIs'),
            "wishlist": self.get_sheet_data(excel, 'Wishlist'),
            "net_worth": nw_details["net_worth_df"],
            "loans": nw_details["loans_nw_df"],
            "pf_value": nw_details["pf_value"],
            "expenses": sqlite_expenses,
            "investments": sqlite_investments,
            "budget": self._parse_monthly_budget(excel)
        }
        
        return data

    def _format_income(self, sqlite_df, excel_df):
        if sqlite_df.empty: return excel_df
        res = sqlite_df.rename(columns={'source': 'Source', 'amount': 'Amount', 'date': 'Date Of Credit'})
        return pd.concat([excel_df, res], ignore_index=True).fillna("Unknown")

    def _format_cc_payments(self, sqlite_df, excel_df):
        if sqlite_df.empty: return excel_df
        res = sqlite_df.rename(columns={'date': 'Payment Date', 'amount': 'Amount Paid'})
        res['Payment Date'] = pd.to_datetime(res['Payment Date'])
        return pd.concat([excel_df, res], ignore_index=True).fillna("Unknown")

    def _format_lendings(self, sqlite_df, excel_df):
        if sqlite_df.empty: return excel_df
        res = sqlite_df.rename(columns={
            'person': 'Lent to', 
            'amount': 'Amount Lent', 
            'due_date': 'Due Date'
        })
        res['isCleared'] = res.get('is_paid', False).apply(lambda x: 'Yes' if x else 'No')
        res['Amount Due'] = res['Amount Lent']
        return pd.concat([excel_df, res], ignore_index=True).fillna("Unknown")
