import os
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship, create_engine
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Account(SQLModel, table=True):
    """Maps to 'Net Worth' (Cash/Savings totals)"""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str  # e.g., "Cash", "Savings"
    balance: float
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class CreditCard(SQLModel, table=True):
    """Maps to 'Net Worth' (Credit Card Limits/Dues)"""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    max_limit: float
    current_due: float
    available_limit: float = Field(default=0.0)
    payments: List["CCPayment"] = Relationship(back_populates="card")

class CCPayment(SQLModel, table=True):
    """Maps to 'Credit Card Payments' sheet"""
    id: Optional[int] = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="creditcard.id")
    amount: float
    date: datetime
    card: Optional[CreditCard] = Relationship(back_populates="payments")

class Lending(SQLModel, table=True):
    """Maps to 'Net Worth' (Lendings) + 'Lendings' (Due Dates)"""
    id: Optional[int] = Field(default=None, primary_key=True)
    person: str
    amount: float
    due_date: Optional[datetime] = None
    is_paid: bool = Field(default=False)

class Loan(SQLModel, table=True):
    """Maps to 'EMIs' sheet"""
    id: Optional[int] = Field(default=None, primary_key=True)
    provider: str
    monthly_emi: float
    months_left: str # Keeping as string to match your 'N/A' or '12' logic
    is_active: bool = Field(default=True)

class Income(SQLModel, table=True):
    """Maps to 'Incomes' sheet"""
    id: Optional[int] = Field(default=None, primary_key=True)
    source: str
    amount: float
    date: str  # e.g., "June 2025"

# Database Engine Configuration (PostgreSQL)
db_user = os.getenv("DB_USER", "postgres")
db_password = os.getenv("DB_PASSWORD", "secret")
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "5432")
db_name = os.getenv("DB_NAME", "finance")

# Construct Postgres connection string
postgres_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
engine = create_engine(postgres_url, echo=False)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def drop_db_and_tables():
    SQLModel.metadata.drop_all(engine)
