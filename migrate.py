import os
import re
import logging
import pandas as pd
from datetime import datetime
from sqlmodel import Session, select, delete
from models import create_db_and_tables, engine, Account, CreditCard, CCPayment, Lending, Loan, Income
from data_loader import DataLoader
from utils import clean_currency

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_excel_to_sqlite(excel_path: str):
    if not os.path.exists(excel_path):
        logger.error(f"Excel file not found at {excel_path}")
        return

    # 1. Ensure Tables Exist
    logger.info("Ensuring database tables exist...")
    create_db_and_tables()

    # 2. Fetch data via unified DataLoader
    logger.info("Parsing Excel file...")
    loader = DataLoader(excel_path)
    data = loader.get_all_data()

    with Session(engine) as session:
        # 3. Non-Destructive Clear: Only delete Excel-sourced data
        # Note: We use is_manual=False to identify Excel-sourced records
        logger.info("Clearing existing Excel-sourced data...")
        session.exec(delete(Account).where(Account.is_manual == False))
        session.exec(delete(CCPayment).where(CCPayment.is_manual == False))
        session.exec(delete(CreditCard).where(CreditCard.is_manual == False))
        session.exec(delete(Lending).where(Lending.is_manual == False))
        session.exec(delete(Loan).where(Loan.is_manual == False))
        session.exec(delete(Income).where(Income.is_manual == False))
        session.commit()

        # 4. Migrate Accounts (Cash/Savings)
        logger.info("Migrating Accounts...")
        session.add(Account(name="Total Cash", balance=data.get('total_cash', 0), is_manual=False))
        session.add(Account(name="Total Savings", balance=data.get('total_savings', 0), is_manual=False))

        # 5. Migrate Credit Cards
        logger.info("Migrating Credit Cards...")
        cc_map = {}
        cc_df = data.get('credit_cards', pd.DataFrame())
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

        # 6. Migrate Payments
        payments_df = data.get('payments', pd.DataFrame())
        logger.info(f"Migrating {len(payments_df)} Payments...")
        migrated_payments = 0
        if not payments_df.empty:
            for _, pay in payments_df.iterrows():
                pay_card_name = str(pay.get('Card Name', '')).upper()
                card_id = None
                for db_card_name, db_id in cc_map.items():
                    if db_card_name.upper() in pay_card_name or pay_card_name in db_card_name.upper():
                        card_id = db_id
                        break
                if card_id:
                    session.add(CCPayment(
                        card_id=card_id,
                        amount=pay['Amount Paid'],
                        date=pd.to_datetime(pay['Payment Date']),
                        is_manual=False
                    ))
                    migrated_payments += 1
        
        logger.info(f"Successfully migrated {migrated_payments} payments.")

        # 7. Migrate Lendings
        logger.info("Migrating Lendings...")
        lend_df = data.get('lendings', pd.DataFrame())
        if not lend_df.empty:
            for _, lend in lend_df.iterrows():
                due_date = lend.get('Due Date')
                parsed_due = None
                if due_date and due_date != "N/A":
                    try: parsed_due = pd.to_datetime(due_date)
                    except: pass
                session.add(Lending(
                    person=lend['Lent to'],
                    amount=lend.get('Amount Due', lend.get('Amount Lent', 0)),
                    due_date=parsed_due,
                    is_paid=lend.get('isCleared') == 'Yes',
                    is_manual=False
                ))

        # 8. Migrate EMIs
        logger.info("Migrating EMIs...")
        emi_df = data.get('emis', pd.DataFrame())
        if not emi_df.empty:
            for _, emi in emi_df.iterrows():
                session.add(Loan(
                    provider=emi.get('Provider', 'Unknown'),
                    monthly_emi=emi.get('Amt Due', emi.get('EMI Amount', 0)),
                    months_left=str(emi.get('EMIs Remaining', emi.get('Months Left', 'N/A'))),
                    is_active=emi.get('IsClosed') != 'Yes',
                    is_manual=False
                ))

        # 9. Migrate Incomes
        logger.info("Migrating Incomes...")
        inc_df = data.get('incomes', pd.DataFrame())
        if not inc_df.empty:
            for _, inc in inc_df.iterrows():
                session.add(Income(
                    source=inc.get('Source', 'Unknown'),
                    amount=inc.get('Amount', 0),
                    date=str(inc.get('Date Of Credit', 'N/A')),
                    is_manual=False
                ))

        session.commit()
    logger.info("Migration completed successfully!")

if __name__ == "__main__":
    EXCEL_FILE = "latest_finance.xlsx"
    if not os.path.exists(EXCEL_FILE):
        EXCEL_FILE = "temp_uploads/latest_finance.xlsx"
    migrate_excel_to_sqlite(EXCEL_FILE)
