import pandas as pd
import os
import sqlite3
import numpy as np
from database import DB_NAME, load_table

class DataLoader:
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
        latest_file = max(candidates, key=lambda x: x[1])[0]
        return pd.ExcelFile(latest_file)

    def _clean_currency(self, value):
        if pd.isna(value) or value == "":
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        # Handle string currency
        clean_val = str(value).replace('₹', '').replace(',', '').strip()
        try:
            return float(clean_val)
        except:
            return 0.0

    def get_sheet_data(self, excel, sheet_name):
        try:
            if excel is None or sheet_name not in excel.sheet_names:
                return pd.DataFrame()
            df = excel.parse(sheet_name)
            # Standard cleanup for most sheets
            amount_cols = ['Amount', 'Balance', 'Current Balance', 'Max Limit', 
                           'Amount Outstanding', 'EMI Amount', 'Expected Cost', 'Amt Due', 
                           'Amount Lent', 'Amount Due', 'Budget', 'Actual Cost', 
                           'Amount Paid', 'Monthly Amount', 'Net Worth']
            for col in amount_cols:
                if col in df.columns:
                    df[col] = df[col].apply(self._clean_currency)
            return df
        except:
            return pd.DataFrame()

    def _parse_net_worth_details(self, excel):
        """Specially parses the 'Net Worth' sheet due to its non-standard tabular format."""
        if excel is None:
            return {
                "credit_cards_df": pd.DataFrame(),
                "net_worth_df": pd.DataFrame(),
                "lendings_nw_df": pd.DataFrame(),
                "loans_nw_df": pd.DataFrame(),
                "pf_value": 0
            }
            
        df = excel.parse('Net Worth', header=None)
        
        cc_raw_data = {}
        cash_savings = []
        lendings_nw = []
        loans_nw = []
        pf_val = 0

        # Specific extraction for Loans from row 9 (index 8), columns H (7) and I (8)
        if len(df) > 8:
            loan_row = df.iloc[8]
            loan_label = str(loan_row.iloc[7]).strip() if len(loan_row) > 7 else ""
            loan_val = self._clean_currency(loan_row.iloc[8]) if len(loan_row) > 8 else 0
            if loan_label and loan_val > 0:
                loans_nw.append({
                    "Loan Name": loan_label,
                    "Amount Due": loan_val,
                    "Cleared": "No",
                    "own": "Yes"
                })

        # Specific extraction for PF from row 13 (index 12), columns B (1) and C (2)
        if len(df) > 12:
            pf_row = df.iloc[12]
            pf_label = str(pf_row.iloc[1]).strip() if len(pf_row) > 1 else ""
            if "PF" in pf_label.upper():
                pf_val = self._clean_currency(pf_row.iloc[2]) if len(pf_row) > 2 else 0

        mode_col4 = None
        for idx, row in df.iterrows():
            # Parse Credit Card info (Columns 4 and 5)
            label_cc = str(row.iloc[4]).strip() if len(row) > 4 else ""
            val_cc = self._clean_currency(row.iloc[5]) if len(row) > 5 else 0

            if "Credit Available" in label_cc: mode_col4 = "AVAIL"
            elif "Credit Card Max Limit" in label_cc: mode_col4 = "LIMIT"
            elif "Credit Due" in label_cc: mode_col4 = "DUE"
            elif label_cc == "" or "total" in label_cc.lower(): mode_col4 = None
            elif mode_col4:
                cc_raw_data.setdefault(label_cc, {"limit": 0, "due": 0, "available": 0})
                if mode_col4 == "AVAIL": cc_raw_data[label_cc]["available"] = val_cc
                elif mode_col4 == "LIMIT": cc_raw_data[label_cc]["limit"] = val_cc
                elif mode_col4 == "DUE": cc_raw_data[label_cc]["due"] = val_cc

            # Parse Cash/Savings (Columns 1 and 2)
            if idx == 12: continue # Skip PF row as it's handled separately
            
            label_cash = str(row.iloc[1]).strip() if len(row) > 1 else ""
            val_cash = self._clean_currency(row.iloc[2]) if len(row) > 2 else 0
            if label_cash and val_cash > 0 and label_cash.lower() != 'nan' and label_cash.lower() != 'total':
                cat = "Savings" if any(x in label_cash.upper() for x in ["SAVINGS", "FD", "HDFC", "SLICE FD"]) else "Cash"
                cash_savings.append({"Name": label_cash, "Balance": val_cash, "Category": cat})

            # Parse Lendings (Columns 7 and 8)
            if idx == 8: continue # Skip row 9 as it's for loans
            label_lend = str(row.iloc[7]).strip() if len(row) > 7 else ""
            val_lend = self._clean_currency(row.iloc[8]) if len(row) > 8 else 0
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

    def _parse_monthly_budget(self, excel):
        """Parses the 'Monthly Budget' sheet with its hierarchical structure."""
        if excel is None:
            return pd.DataFrame()
        
        if 'Monthly Budget' not in excel.sheet_names:
            return pd.DataFrame()
            
        df = excel.parse('Monthly Budget', header=None)
        data = []
        current_cat = None
        current_sub = None
        current_group = None

        for idx, row in df.iterrows():
            row_len = len(row)
            
            # Helper to get clean value
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
            amount = self._clean_currency(row.iloc[5]) if row_len > 5 else 0
            
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

    def get_all_data(self):
        sqlite_expenses = load_table("expenses") if os.path.exists(DB_NAME) else pd.DataFrame()
        sqlite_cc_payments = load_table("credit_card_payments") if os.path.exists(DB_NAME) else pd.DataFrame()
        sqlite_lending = load_table("lending") if os.path.exists(DB_NAME) else pd.DataFrame()
        sqlite_income = load_table("income") if os.path.exists(DB_NAME) else pd.DataFrame()

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
            "budget": self._parse_monthly_budget(excel)
        }
        
        return data

    def _format_income(self, sqlite_df, excel_df):
        if sqlite_df.empty:
            return excel_df
        res = sqlite_df.rename(columns={'source': 'Source', 'amount': 'Amount', 'date': 'Date Of Credit'})
        return res

    def _format_cc_payments(self, sqlite_df, excel_df):
        if sqlite_df.empty:
            return excel_df
        res = sqlite_df.rename(columns={'date': 'Payment Date', 'card_name': 'Card Name', 'amount': 'Amount Paid'})
        res['Payment Date'] = pd.to_datetime(res['Payment Date'])
        return res

    def _format_lendings(self, sqlite_df, excel_df):
        if sqlite_df.empty:
            return excel_df
        res = sqlite_df.rename(columns={
            'borrower': 'Lent to', 
            'amount': 'Amount Lent', 
            'date': 'Date',
            'due_date': 'Due Date'
        })
        res['isCleared'] = res['status'].apply(lambda x: 'Yes' if x == 'Cleared' else 'No')
        res['Amount Due'] = res['Amount Lent']
        return res
