import os
import re
from datetime import datetime
from sqlmodel import Session, select
from models import create_db_and_tables, drop_db_and_tables, engine, Account, CreditCard, CCPayment, Lending, Loan, Income
from main import FinanceParser

def migrate_excel_to_sqlite(excel_path: str):
    if not os.path.exists(excel_path):
        print(f"Excel file not found at {excel_path}")
        return

    # 1. Reset Database (Drop all tables for fresh start)
    print("Resetting database (dropping all tables)...")
    drop_db_and_tables()

    # 2. Create Tables
    print("Creating database tables...")
    create_db_and_tables()

    # 3. Parse Excel
    print("Parsing Excel file...")
    parser = FinanceParser(excel_path)
    data = parser.parse()

    with Session(engine) as session:
        # 4. Migrate Accounts (Cash/Savings)
        print("Migrating Accounts...")
        session.add(Account(name="Total Cash", balance=data.get('total_cash', 0)))
        session.add(Account(name="Total Savings", balance=data.get('total_savings', 0)))

        # 5. Migrate Credit Cards
        print("Migrating Credit Cards and Payments...")
        cc_map = {} # To keep track of CC IDs for payments
        for cc_data in data.get('cc_utilization', []):
            cc = CreditCard(
                name=cc_data['name'],
                max_limit=cc_data['limit'],
                current_due=cc_data['due'],
                available_limit=cc_data['available']
            )
            session.add(cc)
            session.flush() # Get the ID
            cc_map[cc.name] = cc.id

        # 6. Migrate Payments
        print(f"Migrating {len(data.get('payments_history', []))} Payments...")
        migrated_payments = 0
        for pay in data.get('payments_history', []):
            pay_card_name = pay['card'].upper()
            card_id = None
            
            # Flexible matching: search for DB card name in Payment card name
            pay_card_words = [w.upper() for w in re.findall(r'\w+', pay_card_name)]
            for db_card_name, db_id in cc_map.items():
                db_name_upper = db_card_name.upper()
                db_card_words = [w.upper() for w in re.findall(r'\w+', db_name_upper)]
                
                match = False
                for db_w in db_card_words:
                    if db_w in pay_card_name:
                        match = True
                        break
                if not match:
                    for pay_w in pay_card_words:
                        if pay_w in db_name_upper:
                            match = True
                            break
                
                if match:
                    card_id = db_id
                    break
            
            if card_id:
                session.add(CCPayment(
                    card_id=card_id,
                    amount=pay['amount'],
                    date=datetime.strptime(pay['date'], '%Y-%m-%d')
                ))
                migrated_payments += 1
            else:
                print(f"FAILED to match card: '{pay['card']}' for payment on {pay['date']}")
        
        print(f"Successfully migrated {migrated_payments} payments.")

        # 7. Migrate Lendings
        print("Migrating Lendings...")
        for lend in data.get('active_lendings', []):
            due_date = None
            if lend['due_date'] != "N/A":
                try:
                    due_date = datetime.strptime(lend['due_date'], '%Y-%m-%d')
                except:
                    pass
            
            session.add(Lending(
                person=lend['person'],
                amount=lend['amount'],
                due_date=due_date
            ))

        # 8. Migrate EMIs
        print("Migrating EMIs...")
        for emi in data.get('active_emis', []):
            session.add(Loan(
                provider=emi['item'],
                monthly_emi=emi['amount'],
                months_left=str(emi['remaining'])
            ))

        # 9. Migrate Incomes
        print("Migrating Incomes...")
        for inc in data.get('incomes', []):
            session.add(Income(
                source=inc['source'],
                amount=inc['amount'],
                date=inc['month']
            ))

        session.commit()
    print("Migration completed successfully!")

if __name__ == "__main__":
    EXCEL_FILE = "temp_uploads/latest_finance.xlsx"
    migrate_excel_to_sqlite(EXCEL_FILE)
