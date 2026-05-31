import os
import re
import logging
import hashlib
import pandas as pd
from datetime import datetime
from sqlmodel import Session, select, delete
from models import create_db_and_tables, drop_db_and_tables, engine, Account, CreditCard, CCPayment, Lending, Loan, Income, Expense, Investment, BudgetLineItem, NetWorthSnapshot, WishlistItem
from data_loader import DataLoader
from utils import clean_currency, get_value_by_label

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_hash(*args):
    """Generates a SHA256 hash for a set of values to ensure idempotency."""
    combined = "|".join(str(arg) for arg in args).encode('utf-8')
    return hashlib.sha256(combined).hexdigest()

# --- Legacy Excel Parsing Logic (Used only for migration) ---

def load_excel_legacy(excel_file_path):
    # Look for files in root and temp_uploads
    root_path = excel_file_path
    temp_path = os.path.join("temp_uploads", excel_file_path)
    
    candidates = []
    if os.path.exists(root_path):
        candidates.append((root_path, os.path.getmtime(root_path)))
    if os.path.exists(temp_path):
        candidates.append((temp_path, os.path.getmtime(temp_path)))
        
    if not candidates:
        return None
        
    latest_file, _ = max(candidates, key=lambda x: x[1])
    try:
        return pd.ExcelFile(latest_file)
    except Exception as e:
        logger.error(f"Error loading Excel file {latest_file}: {e}")
        return None

def get_sheet_data_legacy(excel, sheet_name):
    try:
        if excel is None or sheet_name not in excel.sheet_names:
            return pd.DataFrame()
        df = excel.parse(sheet_name)
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].fillna("Unknown")
            else:
                df[col] = df[col].fillna(0)
        
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

def parse_net_worth_details_legacy(excel):
    if excel is None: return {}
    try:
        df = excel.parse('Net Worth', header=None)
        pf_val = get_value_by_label(df, "PF Account", col_offset=1)
        if pf_val == 0: pf_val = get_value_by_label(df, "PF", col_offset=1)
        
        cc_raw_data = {}
        cash_savings = []
        mode_col4 = None
        for idx, row in df.iterrows():
            label_cc = str(row.iloc[4]).strip() if len(row) > 4 else ""
            val_cc = clean_currency(row.iloc[5]) if len(row) > 5 else 0
            if "Credit Available" in label_cc: mode_col4 = "AVAIL"
            elif "Credit Card Max Limit" in label_cc: mode_col4 = "LIMIT"
            elif "Credit Due" in label_cc: mode_col4 = "DUE"
            elif mode_col4:
                cc_raw_data.setdefault(label_cc, {"limit": 0, "due": 0, "available": 0})
                if mode_col4 == "AVAIL": cc_raw_data[label_cc]["available"] = val_cc
                elif mode_col4 == "LIMIT": cc_raw_data[label_cc]["limit"] = val_cc
                elif mode_col4 == "DUE": cc_raw_data[label_cc]["due"] = val_cc

            label_cash = str(row.iloc[1]).strip() if len(row) > 1 else ""
            val_cash = clean_currency(row.iloc[2]) if len(row) > 2 else 0
            if label_cash and val_cash > 0 and label_cash.lower() != 'nan' and label_cash.lower() != 'total':
                if "PF" not in label_cash.upper():
                    cat = "Savings" if any(x in label_cash.upper() for x in ["SAVINGS", "FD", "HDFC", "SLICE FD"]) else "Cash"
                    cash_savings.append({"Name": label_cash, "Balance": val_cash, "Category": cat})

        cc_list = []
        for name, vals in cc_raw_data.items():
            cc_list.append({"Card Provider": name, "Current Balance": vals["due"], "Max Limit": vals["limit"], "Available Credit": vals["available"]})

        return {"credit_cards_df": pd.DataFrame(cc_list), "net_worth_df": pd.DataFrame(cash_savings), "pf_value": pf_val}
    except Exception as e:
        logger.error(f"Error parsing Net Worth legacy: {e}")
        return {}

def parse_monthly_budget_legacy(excel):
    if excel is None or 'Monthly Budget' not in excel.sheet_names: return pd.DataFrame()
    try:
        df = excel.parse('Monthly Budget', header=None)
        data = []
        current_cat, current_sub, current_group = None, None, None
        for idx, row in df.iterrows():
            row_len = len(row)
            def get_val(col_idx):
                if col_idx >= row_len: return None
                v = row.iloc[col_idx]
                if pd.isna(v): return None
                s = str(v).strip()
                return None if s.lower() in ['nan', 'none', ''] else s

            cat, sub, group, item = get_val(1), get_val(2), get_val(3), get_val(4)
            amount = clean_currency(row.iloc[5]) if row_len > 5 else 0
            if cat: current_cat, current_sub, current_group = cat, None, None
            if sub: current_sub, current_group = sub, None
            if group: current_group = group
            if amount > 0:
                parts = []
                if current_group: parts.append(current_group)
                if item: parts.append(item)
                full_item = ' - '.join(parts) if parts else current_sub or current_cat
                data.append({'Category': current_cat, 'Subcategory': current_sub, 'Item': full_item, 'Amount': amount})
        return pd.DataFrame(data)
    except Exception as e:
        logger.error(f"Error parsing Budget legacy: {e}")
        return pd.DataFrame()

# --- Migration Main ---

def migrate_excel_to_sqlite(excel_path: str):
    if not os.path.exists(excel_path):
        logger.error(f"Excel file not found at {excel_path}")
        return

    # 1. Ensure Tables Exist (Refresh Schema)
    logger.info("Refreshing database tables...")
    try:
        drop_db_and_tables()
    except Exception as e:
        logger.warning(f"Could not drop tables (might be locked): {e}")
    
    create_db_and_tables()

    # 2. Fetch RAW data from Excel
    logger.info("Parsing Excel file (Raw)...")
    excel = load_excel_legacy(excel_path)
    if not excel:
        logger.error("Failed to load Excel object.")
        return
    
    logger.info(f"Available Excel Sheets: {excel.sheet_names}")

    nw_details = parse_net_worth_details_legacy(excel)
    excel_incomes = get_sheet_data_legacy(excel, 'Incomes')
    excel_payments = get_sheet_data_legacy(excel, 'Credit Card Payments')
    excel_lendings = get_sheet_data_legacy(excel, 'Lendings')
    excel_emis = get_sheet_data_legacy(excel, 'EMIs')
    excel_nw_history = get_sheet_data_legacy(excel, 'Net Worth History')
    excel_wishlist = get_sheet_data_legacy(excel, 'Wishlist')
    excel_budget = parse_monthly_budget_legacy(excel)

    with Session(engine) as session:
        # 3. Non-Destructive Clear: Only delete Excel-sourced data
        logger.info("Clearing existing Excel-sourced data...")
        session.exec(delete(Account).where(Account.is_manual == False))
        session.exec(delete(CCPayment).where(CCPayment.is_manual == False))
        session.exec(delete(CreditCard).where(CreditCard.is_manual == False))
        session.exec(delete(Lending).where(Lending.is_manual == False))
        session.exec(delete(Loan).where(Loan.is_manual == False))
        session.exec(delete(Income).where(Income.is_manual == False))
        session.exec(delete(Expense).where(Expense.is_manual == False))
        session.exec(delete(Investment).where(Investment.is_manual == False))
        session.exec(delete(BudgetLineItem).where(BudgetLineItem.is_manual == False))
        session.exec(delete(NetWorthSnapshot).where(NetWorthSnapshot.is_manual == False))
        session.exec(delete(WishlistItem).where(WishlistItem.is_manual == False))
        session.commit()

        # 4. Migrate Accounts (Cash/Savings)
        logger.info("Migrating Accounts...")
        nw_df = nw_details.get('net_worth_df', pd.DataFrame())
        total_cash = 0
        total_savings = 0
        if not nw_df.empty:
            total_cash = nw_df[nw_df['Category'] == 'Cash']['Balance'].sum()
            total_savings = nw_df[nw_df['Category'] == 'Savings']['Balance'].sum()

        session.add(Account(source="Total Cash", type="Cash", balance=total_cash, is_manual=False))
        session.add(Account(source="Total Savings", type="Savings", balance=total_savings, is_manual=False))
        
        # Add PF if found
        pf_val = nw_details.get('pf_value', 0)
        if pf_val > 0:
            session.add(Account(source="PF Account", type="PF", balance=pf_val, is_manual=False))

        # 5. Migrate Credit Cards
        logger.info("Migrating Credit Cards...")
        cc_map = {}
        cc_df = nw_details.get('credit_cards_df', pd.DataFrame())
        if not cc_df.empty:
            for _, cc_row in cc_df.iterrows():
                cc = CreditCard(
                    name=cc_row['Card Provider'],
                    max_limit=cc_row['Max Limit'],
                    current_due=cc_row['Current Balance'],
                    available_limit=cc_row['Available Credit'],
                    is_manual=False
                )
                session.add(cc)
                session.flush()
                cc_map[cc.name] = cc.id

        # 6. Migrate Payments with Deduplication Hash
        logger.info(f"Migrating {len(excel_payments)} Payments...")
        migrated_payments = 0
        if not excel_payments.empty:
            for _, pay in excel_payments.iterrows():
                pay_card_name = str(pay.get('Card Name', '')).upper()
                card_id = None
                for db_card_name, db_id in cc_map.items():
                    if db_card_name.upper() in pay_card_name or pay_card_name in db_card_name.upper():
                        card_id = db_id
                        break
                
                if card_id:
                    amount = pay['Amount Paid']
                    date = pd.to_datetime(pay['Payment Date'], dayfirst=True)
                    entry_hash = generate_hash(card_id, amount, date.strftime("%Y-%m-%d"))
                    
                    # Check if hash already exists (Idempotency)
                    existing = session.exec(select(CCPayment).where(CCPayment.entry_hash == entry_hash)).first()
                    if not existing:
                        session.add(CCPayment(
                            card_id=card_id,
                            amount=amount,
                            date=date,
                            entry_hash=entry_hash,
                            transaction_type="Transfer",
                            is_manual=False
                        ))
                        migrated_payments += 1
        
        logger.info(f"Successfully migrated {migrated_payments} payments.")

        # 7. Migrate Lendings with Unique Constraint Check
        logger.info("Migrating Lendings...")
        if not excel_lendings.empty:
            for _, lend in excel_lendings.iterrows():
                person = lend['Lent to']
                amount = lend.get('Amount Due', lend.get('Amount Lent', 0))
                due_date = lend.get('Due Date')
                parsed_due = None
                if due_date and due_date != "N/A":
                    try: parsed_due = pd.to_datetime(due_date, dayfirst=True)
                    except: pass
                
                # Check for existing lending (person, amount, due_date)
                statement = select(Lending).where(
                    Lending.person == person,
                    Lending.amount == amount,
                    Lending.due_date == parsed_due
                )
                if not session.exec(statement).first():
                    session.add(Lending(
                        person=person,
                        amount=amount,
                        due_date=parsed_due,
                        is_paid=lend.get('isCleared') == 'Yes',
                        is_manual=False
                    ))

        # 8. Migrate EMIs
        logger.info("Migrating EMIs...")
        if not excel_emis.empty:
            for _, emi in excel_emis.iterrows():
                provider = emi.get('Provider', 'Unknown')
                amount = emi.get('Amt Due', emi.get('EMI Amount', 0))
                months_left = str(emi.get('EMIs Remaining', emi.get('Months Left', 'N/A')))
                
                statement = select(Loan).where(
                    Loan.provider == provider,
                    Loan.monthly_emi == amount,
                    Loan.months_left == months_left
                )
                if not session.exec(statement).first():
                    session.add(Loan(
                        provider=provider,
                        monthly_emi=amount,
                        months_left=months_left,
                        is_active=emi.get('IsClosed') != 'Yes',
                        is_manual=False
                    ))

        # 9. Migrate Incomes with Deduplication Hash
        logger.info("Migrating Incomes...")
        if not excel_incomes.empty:
            for _, inc in excel_incomes.iterrows():
                source = inc.get('Source', 'Unknown')
                amount = inc.get('Amount', 0)
                date_str = str(inc.get('Date Of Credit', 'N/A'))
                entry_hash = generate_hash(source, amount, date_str)
                
                existing = session.exec(select(Income).where(Income.entry_hash == entry_hash)).first()
                if not existing:
                    session.add(Income(
                        source=source,
                        amount=amount,
                        date=date_str,
                        entry_hash=entry_hash,
                        transaction_type="Income",
                        is_manual=False
                    ))

        # 10. Migrate Budget Line Items
        logger.info("Migrating Budget...")
        budget_count = 0
        if not excel_budget.empty:
            for _, row in excel_budget.iterrows():
                session.add(BudgetLineItem(
                    category=row['Category'],
                    subcategory=row['Subcategory'],
                    item=row['Item'],
                    amount=row['Amount'],
                    is_manual=False
                ))
                budget_count += 1
        logger.info(f"Migrated {budget_count} budget items.")

        # 11. Migrate Net Worth History
        logger.info("Migrating Net Worth History...")
        nw_count = 0
        if not excel_nw_history.empty:
            for _, row in excel_nw_history.iterrows():
                date_val = row.get('Date')
                amount_val = row.get('Net Worth', 0)
                if date_val and not pd.isna(date_val):
                    session.add(NetWorthSnapshot(
                        date=pd.to_datetime(date_val, dayfirst=True),
                        amount=amount_val,
                        is_manual=False
                    ))
                    nw_count += 1
        logger.info(f"Migrated {nw_count} net worth snapshots.")

        # 12. Migrate Wishlist
        logger.info("Migrating Wishlist...")
        wish_count = 0
        if not excel_wishlist.empty:
            for _, row in excel_wishlist.iterrows():
                session.add(WishlistItem(
                    item=row.get('Item', row.get('Name', 'Unknown')),
                    amount=row.get('Expected Cost', row.get('Amount', 0)),
                    priority=row.get('Priority', 'Normal'),
                    is_manual=False
                ))
                wish_count += 1
        logger.info(f"Migrated {wish_count} wishlist items.")

        session.commit()
    logger.info("Migration completed successfully!")

if __name__ == "__main__":
    EXCEL_FILE = "latest_finance.xlsx"
    if not os.path.exists(EXCEL_FILE):
        EXCEL_FILE = "temp_uploads/latest_finance.xlsx"
    migrate_excel_to_sqlite(EXCEL_FILE)
