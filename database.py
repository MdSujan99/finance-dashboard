import sqlite3
import pandas as pd
from datetime import datetime

DB_NAME = "finance.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create expenses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            account TEXT NOT NULL
        )
    ''')
    
    # Create credit_card_payments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS credit_card_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            card_name TEXT NOT NULL,
            amount REAL NOT NULL
        )
    ''')
    
    # Create lending table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lending (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            borrower TEXT NOT NULL,
            amount REAL NOT NULL,
            due_date TEXT,
            status TEXT NOT NULL
        )
    ''')
    
    # Create income table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS income (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            source TEXT NOT NULL,
            amount REAL NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

def add_expense(date, category, amount, account):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO expenses (date, category, amount, account)
        VALUES (?, ?, ?, ?)
    ''', (date, category, amount, account))
    conn.commit()
    conn.close()

def add_cc_payment(date, card_name, amount):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO credit_card_payments (date, card_name, amount)
        VALUES (?, ?, ?, ?)
    ''', (date, card_name, amount))
    conn.commit()
    conn.close()

def add_lending(date, borrower, amount, due_date, status):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO lending (date, borrower, amount, due_date, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (date, borrower, amount, due_date, status))
    conn.commit()
    conn.close()

def add_income(date, source, amount):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO income (date, source, amount)
        VALUES (?, ?, ?)
    ''', (date, source, amount))
    conn.commit()
    conn.close()

def load_table(table_name):
    conn = get_connection()
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    conn.close()
    return df
