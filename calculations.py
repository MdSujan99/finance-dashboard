import pandas as pd
from datetime import datetime

# Centralized Configurations
EXCLUDED_OWNERS = ["Pyaru Mama"]
PF_VALUE = 420000 

class FinanceCalculations:
    @staticmethod
    def get_summary_metrics(data):
        cc = data['credit_cards']
        total_cc_used = cc['Current Balance'].sum() if not cc.empty else 0
        total_cc_limit = cc['Max Limit'].sum() if not cc.empty else 0
        util_pct = (total_cc_used / total_cc_limit * 100) if total_cc_limit > 0 else 0

        incomes = data['incomes']
        total_income = incomes['Amount'].sum() if not incomes.empty else 0

        lendings = data['lendings']
        if not lendings.empty:
            if 'isCleared' in lendings.columns:
                active_lend = lendings[lendings['isCleared'] != 'Yes']
            else:
                active_lend = lendings
            l_col = 'Amount Due' if 'Amount Due' in active_lend.columns else ('Amount Lent' if 'Amount Lent' in active_lend.columns else 'Amount Outstanding')
            total_lent = active_lend[l_col].sum() if l_col in active_lend.columns else 0
        else:
            total_lent = data['lendings_nw']['Amount Lent'].sum() if not data['lendings_nw'].empty else 0

        loans = data['loans']
        total_loan_owed = 0
        if not loans.empty:
            active_loans = loans[(loans['Cleared'] == 'No') & (loans['own'] == 'Yes')]
            total_loan_owed = active_loans['Amount Due'].sum()

        nw = data['net_worth']
        total_cash = nw[nw['Category'] == 'Cash']['Balance'].sum() if not nw.empty else 0
        total_savings = nw[nw['Category'] == 'Savings']['Balance'].sum() if not nw.empty else 0
        total_assets = total_cash + total_savings + total_lent + PF_VALUE
        net_worth = total_assets - total_cc_used - total_loan_owed

        emi_total = 0
        emis = data['emis']
        if not emis.empty:
            active_emis = emis[emis['IsClosed'] == 'No'] if 'IsClosed' in emis.columns else emis
            if 'Actual Owner' in active_emis.columns:
                active_emis = active_emis[~active_emis['Actual Owner'].isin(EXCLUDED_OWNERS)]
            emi_col = 'Amt Due' if 'Amt Due' in active_emis.columns else 'EMI Amount'
            if emi_col in active_emis.columns:
                emi_total = active_emis[emi_col].sum()

        fixed_exp_total = 0
        fixed_df = data.get('fixed_expenses', pd.DataFrame())
        if not fixed_df.empty and 'Monthly Amount' in fixed_df.columns:
            fixed_exp_total = fixed_df['Monthly Amount'].sum()

        monthly_expenses = emi_total + fixed_exp_total + (total_cc_used / 2)
        savings_val = total_income - monthly_expenses
        savings_rate = (savings_val / total_income * 100) if total_income > 0 else 0
        
        liquid_assets = total_cash + total_savings
        runway = (liquid_assets / monthly_expenses) if monthly_expenses > 0 else 0

        return {
            "net_worth": net_worth,
            "total_cash": total_cash,
            "total_savings": total_savings,
            "total_cc_used": total_cc_used,
            "total_cc_limit": total_cc_limit,
            "util_pct": round(util_pct, 1),
            "total_lent": total_lent,
            "total_loan_owed": total_loan_owed,
            "monthly_income": total_income,
            "savings_rate": round(savings_rate, 1),
            "runway": round(runway, 1),
            "monthly_expenses": monthly_expenses,
            "pf_value": PF_VALUE
        }

    @staticmethod
    def get_cash_flow_data(summary, data):
        expenses = summary['monthly_expenses']
        income = summary['monthly_income']
        savings = income - expenses
        return pd.DataFrame({
            "Category": ["Income", "Expenses", "Savings"],
            "Amount": [income, expenses, max(0, savings)]
        })

    @staticmethod
    def get_asset_allocation(summary, data):
        return pd.DataFrame({
            "Asset": ["Cash", "Savings", "Lent Money", "PF"],
            "Balance": [summary['total_cash'], summary['total_savings'], summary['total_lent'], summary['pf_value']]
        })

    @staticmethod
    def get_payment_trends(data):
        # 1. Get Credit Card Payments
        payments = data['payments'].copy() if not data['payments'].empty else pd.DataFrame()
        if not payments.empty:
            payments = payments[['Payment Date', 'Card Name', 'Amount Paid']]
            payments.columns = ['Date', 'Category', 'Amount']
            payments['Type'] = 'Credit Card'
        
        # 2. Get Fixed Expenses
        fixed = data['fixed_expenses'].copy() if not data['fixed_expenses'].empty else pd.DataFrame()
        fixed_rows = []
        if not fixed.empty:
            # We assume current month for fixed expenses since they are recurring
            # For trend, we can duplicate them across months found in payments
            unique_months = payments['Date'].dt.to_period('M').unique() if not payments.empty else [pd.Period(datetime.now(), freq='M')]
            for month in unique_months:
                for _, row in fixed.iterrows():
                    fixed_rows.append({
                        'Date': month.to_timestamp(),
                        'Category': row.get('Expense Name', 'Fixed Expense'),
                        'Amount': row.get('Monthly Amount', 0),
                        'Type': 'Fixed Bill'
                    })
        fixed_df = pd.DataFrame(fixed_rows)
        
        # Combine
        combined = pd.concat([payments, fixed_df], ignore_index=True)
        if combined.empty: return pd.DataFrame()
        
        # Add Sort/Label Keys
        combined['MonthSort'] = combined['Date'].dt.to_period('M')
        combined['MonthLabel'] = combined['Date'].dt.strftime('%b %Y')
        combined['ExactDate'] = combined['Date'].dt.strftime('%d %b %Y')
        
        return combined.sort_values('Date')

    @staticmethod
    def get_goal_forecast(summary, target_amount):
        current_saved = summary['total_savings']
        monthly_savings = summary['monthly_income'] - summary['monthly_expenses']
        remaining = target_amount - current_saved
        if remaining <= 0: return "Goal Achieved! 🎉"
        if monthly_savings <= 0: return "Indefinite (No monthly savings)"
        months_left = remaining / monthly_savings
        today = datetime.now()
        target_month = (today.month + int(months_left) - 1) % 12 + 1
        target_year = today.year + (today.month + int(months_left) - 1) // 12
        return f"{months_left:.1f} months (Est. {datetime(target_year, target_month, 1).strftime('%b %Y')})"
