# Personal Finance Dashboard

A local FastAPI web application to parse your personal finance Excel workbook and display a beautiful, dark-themed dashboard.

## Features
- **File Upload**: Upload your `Finance_Logs.xlsx` directly via the UI.
- **KPI Cards**: View Total Cash, Savings, BOB Credit Due, Money Lent Out, and Net Worth.
- **Active Lendings**: Track who owes you money and see overdue flags.
- **Credit Card Utilisation**: Monitor card usage with visual progress bars (BOB and others).
- **EMIs & Loans**: Summary of active monthly installments.
- **Income History**: Monthly income summary.

## Setup & Run

1. **Create and Activate a Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Server**:
   ```bash
   uvicorn main:app --reload
   ```

3. **Access the App**:
   Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

## Excel Structure Requirements
The app expects a `.xlsx` file with the following sheets:
- **Incomes**: Columns `Month`, `Amount`, `Source`.
- **Credit Cards**: Columns `Card Name`, `Due Amount`, `Limit`, `Available`.
- **Lendings**: Columns `Person`, `Amount`, `Due Date`, `isCleared`.
- **EMIs**: Columns `Item`, `Monthly EMI`, `Remaining Months`, `IsClosed`.
- **Net Worth**: Key-value pairs in the first two columns (e.g., "Cash", "Savings", "Net Worth").

*Note: The parser automatically handles currency symbols (₹), commas, and blank rows.*
