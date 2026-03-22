import pandas as pd

# List of Actual Owners to ignore from personal EMI obligations
EXCLUDED_OWNERS = ["Pyaru Mama"]

class FinanceCalculations:
    @staticmethod
    def get_summary_metrics(data):
        # Credit Cards
        cc = data['credit_cards']
        total_cc_used = cc['Current Balance'].sum() if not cc.empty else 0
        total_cc_limit = cc['Max Limit'].sum() if not cc.empty else 0
        util_pct = (total_cc_used / total_cc_limit * 100) if total_cc_limit > 0 else 0

        # Incomes
        incomes = data['incomes']
        total_income = incomes['Amount'].sum() if not incomes.empty else 0

        # Lendings (Prefer Lendings sheet, fallback to Net Worth parsed values)
        lendings = data['lendings']
        if not lendings.empty:
            if 'isCleared' in lendings.columns:
                active_lend = lendings[lendings['isCleared'] != 'Yes']
            else:
                active_lend = lendings
            
            l_col = 'Amount Lent' if 'Amount Lent' in active_lend.columns else ('Amount Outstanding' if 'Amount Outstanding' in active_lend.columns else None)
            total_lent = active_lend[l_col].sum() if l_col else 0
        else:
            total_lent = data['lendings_nw']['Amount Lent'].sum() if not data['lendings_nw'].empty else 0

        # Loans (Owed)
        loans = data['loans']
        total_loan_owed = 0
        if not loans.empty:
            active_loans = loans[(loans['Cleared'] == 'No') & (loans['own'] == 'Yes')]
            total_loan_owed = active_loans['Amount Due'].sum()

        # Net Worth & Assets
        nw = data['net_worth']
        total_cash = nw[nw['Category'] == 'Cash']['Balance'].sum() if not nw.empty else 0
        total_savings = nw[nw['Category'] == 'Savings']['Balance'].sum() if not nw.empty else 0
        
        total_assets = total_cash + total_savings + total_lent
        net_worth = total_assets - total_cc_used - total_loan_owed

        return {
            "net_worth": net_worth,
            "total_cash": total_cash,
            "total_savings": total_savings,
            "total_cc_used": total_cc_used,
            "total_cc_limit": total_cc_limit,
            "util_pct": round(util_pct, 1),
            "total_lent": total_lent,
            "total_loan_owed": total_loan_owed,
            "monthly_income": total_income
        }

    @staticmethod
    def get_cash_flow_data(summary, data):
        # EMIs (Active only for cash flow, excluding non-owned ones)
        emis = data['emis']
        if not emis.empty:
            active_emis = emis.copy()
            if 'IsClosed' in active_emis.columns:
                active_emis = active_emis[active_emis['IsClosed'] != 'Yes']
            
            if 'Amt Due' in active_emis.columns:
                active_emis = active_emis[active_emis['Amt Due'] > 0]
            
            # Exclude specific owners from cash flow calc based on central list
            if 'Actual Owner' in active_emis.columns:
                active_emis = active_emis[~active_emis['Actual Owner'].isin(EXCLUDED_OWNERS)]
            
            emi_col = 'Amt Due' if 'Amt Due' in active_emis.columns else ('EMI Amount' if 'EMI Amount' in active_emis.columns else None)
            emi_total = active_emis[emi_col].sum() if emi_col else 0
        else:
            emi_total = 0
        
        expenses = emi_total + summary['total_cc_used']
        savings = summary['monthly_income'] - expenses
        
        return pd.DataFrame({
            "Category": ["Income", "Expenses", "Savings"],
            "Amount": [summary['monthly_income'], expenses, max(0, savings)]
        })
