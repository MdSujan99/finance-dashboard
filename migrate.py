import os
import re
import logging
import hashlib
import pandas as pd
from datetime import datetime
from sqlmodel import Session, select, delete
from models import create_db_and_tables, engine, Account, CreditCard, CCPayment, Lending, Loan, Income, Expense, Investment
from data_loader import DataLoader
from utils import clean_currency

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_hash(*args):
    """Generates a SHA256 hash for a set of values to ensure idempotency."""
    combined = "|".join(str(arg) for arg in args).encode('utf-8')
    return hashlib.sha256(combined).hexdigest()

def migrate_excel_to_sqlite(excel_path: str):
    if not os.path.exists(excel_path):
        logger.error(f"Excel file not found at {excel_path}")
        return

    # 1. Ensure Tables Exist
    logger.info("Ensuring database tables exist...")
    create_db_and_tables()

    # 2. Fetch RAW data from Excel (Avoiding the unified data loader merge loop)
    logger.info("Parsing Excel file (Raw)...")
    loader = DataLoader(excel_path)
    excel = loader.load_excel()
    if not excel:
        logger.error("Failed to load Excel object.")
        return

    nw_details = loader._parse_net_worth_details(excel)
    excel_incomes = loader.get_sheet_data(excel, 'Incomes')
    excel_payments = loader.get_sheet_data(excel, 'Credit Card Payments')
    excel_lendings = loader.get_sheet_data(excel, 'Lendings')
    excel_emis = loader.get_sheet_data(excel, 'EMIs')

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
        session.commit()

        # 4. Migrate Accounts (Cash/Savings)
        logger.info("Migrating Accounts...")
        nw_df = nw_details.get('net_worth_df', pd.DataFrame())
        total_cash = 0
        total_savings = 0
        if not nw_df.empty:
            total_cash = nw_df[nw_df['Category'] == 'Cash']['Balance'].sum()
            total_savings = nw_df[nw_df['Category'] == 'Savings']['Balance'].sum()

        session.add(Account(name="Total Cash", balance=total_cash, is_manual=False))
        session.add(Account(name="Total Savings", balance=total_savings, is_manual=False))

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

        session.commit()
    logger.info("Migration completed successfully!")

if __name__ == "__main__":
    EXCEL_FILE = "latest_finance.xlsx"
    if not os.path.exists(EXCEL_FILE):
        EXCEL_FILE = "temp_uploads/latest_finance.xlsx"
    migrate_excel_to_sqlite(EXCEL_FILE)
