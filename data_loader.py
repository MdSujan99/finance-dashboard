import pandas as pd
import os

class DataLoader:
    def __init__(self, file_path="latest_finance.xlsx"):
        self.file_path = file_path
        
    def load_excel(self):
        # Look for files in root and temp_uploads
        root_path = self.file_path
        temp_path = os.path.join("temp_uploads", self.file_path)
        
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
        clean_val = str(value).replace('₹', '').replace(',', '').strip()
        try:
            return float(clean_val)
        except:
            return 0.0

    def get_sheet_data(self, excel, sheet_name):
        try:
            df = excel.parse(sheet_name)
            amount_cols = ['Amount', 'Balance', 'Current Balance', 'Max Limit', 
                           'Amount Outstanding', 'EMI Amount', 'Expected Cost', 'Amt Due', 'Amount Lent', 'Budget', 'Actual Cost']
            for col in amount_cols:
                if col in df.columns:
                    df[col] = df[col].apply(self._clean_currency)
            return df
        except:
            return pd.DataFrame()

    def _parse_net_worth_details(self, excel):
        df = excel.parse('Net Worth')
        cc_raw_data = {}
        cash_savings = []
        lendings_nw = []
        mode_col4 = None
        for _, row in df.iterrows():
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
            label_cash = str(row.iloc[1]).strip() if len(row) > 1 else ""
            val_cash = self._clean_currency(row.iloc[2]) if len(row) > 2 else 0
            if label_cash and val_cash > 0 and label_cash.lower() != 'nan' and label_cash.lower() != 'total':
                cat = "Savings" if any(x in label_cash.upper() for x in ["SAVINGS", "FD", "HDFC", "SLICE FD"]) else "Cash"
                cash_savings.append({"Name": label_cash, "Balance": val_cash, "Category": cat})
            label_lend = str(row.iloc[7]).strip() if len(row) > 7 else ""
            val_lend = self._clean_currency(row.iloc[8]) if len(row) > 8 else 0
            if label_lend and val_lend > 0 and "total" not in label_lend.lower() and label_lend.lower() != 'nan' and "lendings" not in label_lend.lower() and "loans" not in label_lend.lower():
                lendings_nw.append({"Lent to": label_lend, "Amount Lent": val_lend})
        cc_list = []
        for name, vals in cc_raw_data.items():
            cc_list.append({"Card Provider": name, "Current Balance": vals["due"], "Max Limit": vals["limit"], "Available Credit": vals["available"]})
        return {"credit_cards_df": pd.DataFrame(cc_list), "net_worth_df": pd.DataFrame(cash_savings), "lendings_nw_df": pd.DataFrame(lendings_nw)}

    def get_all_data(self):
        excel = self.load_excel()
        if excel is None: return None
        nw_details = self._parse_net_worth_details(excel)
        return {
            "incomes": self.get_sheet_data(excel, 'Incomes'),
            "credit_cards": nw_details["credit_cards_df"],
            "payments": self.get_sheet_data(excel, 'Credit Card Payments'),
            "lendings": self.get_sheet_data(excel, 'Lendings'),
            "lendings_nw": nw_details["lendings_nw_df"],
            "emis": self.get_sheet_data(excel, 'EMIs'),
            "wishlist": self.get_sheet_data(excel, 'Wishlist'),
            "net_worth": nw_details["net_worth_df"],
            "loans": self.get_sheet_data(excel, 'Loans')
        }
