import pandas as pd
from datetime import datetime

# Centralized Configurations
EXCLUDED_OWNERS = ["Pyaru Mama"]

class FinanceCalculations:
    @staticmethod
    def get_summary_metrics(data):
        # 1. Credit Card Metrics (Snapshot)
        cc = data['credit_cards']
        total_cc_used = cc['Current Balance'].sum() if not cc.empty else 0
        total_cc_limit = cc['Max Limit'].sum() if not cc.empty else 0
        util_pct = (total_cc_used / total_cc_limit * 100) if total_cc_limit > 0 else 0

        # 2. Baseline Income & Burn (from Budget Sheet)
        budget_df = data.get('budget', pd.DataFrame())
        budget_income = 0
        budget_burn = 0
        
        # Keywords that signify an investment/savings allocation rather than a "burn" expense
        INVESTMENT_KEYWORDS = ['INVESTMENT', 'INVESTMENTS', 'SAVINGS', 'MF', 'SIP', 'GOLD', 'EQUITY', 'STOCK']

        if not budget_df.empty:
            # 2a. Calculate Income Baseline
            budget_income = budget_df[budget_df['Category'].str.upper() == 'INCOME']['Amount'].sum()
            
            # 2b. Calculate Burn Baseline (Exclude Income AND any Investment-like items)
            # We check both the top-level Category and the Subcategory column
            def is_investment(row):
                cat = str(row.get('Category', '')).upper()
                sub = str(row.get('Subcategory', '')).upper()
                if cat == 'INCOME':
                    return True # Income is not burn
                return any(kw in cat for kw in INVESTMENT_KEYWORDS) or \
                       any(kw in sub for kw in INVESTMENT_KEYWORDS)

            investment_mask = budget_df.apply(is_investment, axis=1)
            budget_burn = budget_df[~investment_mask]['Amount'].sum()

        # 3. Monthly Baseline established
        incomes = data['incomes']
        if budget_income > 0:
            monthly_income = budget_income
        elif not incomes.empty:
            monthly_income = incomes.iloc[-1]['Amount']
        else:
            monthly_income = 0

        # 4. Actual Monthly Expenses & Recurring Obligations
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

        current_actual_variable_expense = 0
        current_actual_investment = 0
        sqlite_expenses_df = data.get('expenses', pd.DataFrame())
        if not sqlite_expenses_df.empty and 'amount' in sqlite_expenses_df.columns:
            now = datetime.now()
            if not pd.api.types.is_datetime64_any_dtype(sqlite_expenses_df['date']):
                sqlite_expenses_df['date'] = pd.to_datetime(sqlite_expenses_df['date'], dayfirst=True)
            
            mask = (sqlite_expenses_df['date'].dt.month == now.month) & \
                   (sqlite_expenses_df['date'].dt.year == now.year)
            
            current_month_df = sqlite_expenses_df[mask]
            
            # CRITICAL FIX 2: Transaction Type Classification
            # Split variable spending into actual Expenses vs Investments
            if 'transaction_type' in current_month_df.columns:
                current_actual_variable_expense = current_month_df[current_month_df['transaction_type'] == 'Expense']['amount'].sum()
                current_actual_investment = current_month_df[current_month_df['transaction_type'] == 'Investment']['amount'].sum()
            else:
                # Fallback if column missing
                current_actual_variable_expense = current_month_df['amount'].sum()

        # Final Monthly Burn Calculation (Strictly non-investment outflows)
        if budget_burn > 0:
            monthly_expenses = budget_burn
        else:
            monthly_expenses = emi_total + fixed_exp_total + current_actual_variable_expense

        # 5. Asset & Net Worth Snapshot
        lendings = data['lendings']
        if not lendings.empty:
            active_lend = lendings[lendings['isCleared'] != 'Yes'] if 'isCleared' in lendings.columns else lendings
            l_col = 'Amount Due' if 'Amount Due' in active_lend.columns else ('Amount Lent' if 'Amount Lent' in active_lend.columns else 'Amount Outstanding')
            total_lent = active_lend[l_col].sum() if l_col in active_lend.columns else 0
        else:
            total_lent = data['lendings_nw']['Amount Lent'].sum() if not data['lendings_nw'].empty else 0

        loans = data['loans']
        total_loan_owed = 0
        if not loans.empty:
            active_loans = loans[(loans['Cleared'] == 'No') & (loans['own'] == 'Yes')]
            total_loan_owed = active_loans['Amount Due'].sum()

        pf_value = data.get('pf_value', 0)
        nw = data['net_worth']
        total_cash = nw[nw['Category'] == 'Cash']['Balance'].sum() if not nw.empty else 0
        total_savings = nw[nw['Category'] == 'Savings']['Balance'].sum() if not nw.empty else 0
        
        total_assets = total_cash + total_savings + total_lent + pf_value
        net_worth = total_assets - total_cc_used - total_loan_owed

        # 6. Final Metric Derivations
        monthly_savings = monthly_income - monthly_expenses
        
        # CRITICAL FIX 3: Define wealth_velocity = savings + investments
        # This reflects total value generated/retained, whether in cash or assets
        wealth_velocity = monthly_savings + current_actual_investment
        
        savings_rate = (monthly_savings / monthly_income * 100) if monthly_income > 0 else 0
        
        # Financial Runway: How many months liquidity covers current burn
        liquid_assets = total_cash + total_savings
        runway = (liquid_assets / monthly_expenses) if monthly_expenses > 0 else 0

        # Financial Independence Ratio: Assets / Yearly Expenses
        yearly_expenses = monthly_expenses * 12
        fi_ratio = (total_assets / yearly_expenses) if yearly_expenses > 0 else 0

        total_credit_available = total_cc_limit - total_cc_used
        total_available_funds = liquid_assets + total_credit_available

        return {
            "net_worth": net_worth,
            "total_cash": total_cash,
            "total_savings": total_savings,
            "total_cc_used": total_cc_used,
            "total_cc_limit": total_cc_limit,
            "total_credit_available": total_credit_available,
            "total_available_funds": total_available_funds,
            "util_pct": round(util_pct, 1),
            "total_lent": total_lent,
            "total_loan_owed": total_loan_owed,
            "monthly_income": monthly_income,
            "savings_rate": round(savings_rate, 1),
            "runway": round(runway, 1),
            "monthly_expenses": monthly_expenses,
            "total_expenses": current_actual_variable_expense,
            "total_investments": current_actual_investment,
            "pf_value": pf_value,
            "wealth_velocity": wealth_velocity,
            "fi_ratio": round(fi_ratio, 2),
            "total_assets": total_assets
        }

    @staticmethod
    def run_sanity_checks(metrics, data):
        """Runs critical sanity checks and returns a list of warnings for the dashboard."""
        warnings = []
        
        # 1. Income Duplication Check
        total_income = metrics.get('monthly_income', 0)
        budget_df = data.get('budget', pd.DataFrame())
        expected_income = 0
        if not budget_df.empty:
            expected_income = budget_df[budget_df['Category'] == 'Income']['Amount'].sum()
        
        if expected_income > 0 and total_income > 1.5 * expected_income:
            warnings.append(f"⚠️ Possible Duplicate Income: Current income (₹{total_income:,.0f}) is > 150% of budgeted income (₹{expected_income:,.0f}).")

        # 2. Lending Integrity Check
        lendings_df = data.get('lendings', pd.DataFrame())
        reported_lent = metrics.get('total_lent', 0)
        actual_sum = 0
        if not lendings_df.empty:
            l_col = 'Amount Due' if 'Amount Due' in lendings_df.columns else ('Amount Lent' if 'Amount Lent' in lendings_df.columns else 'Amount Outstanding')
            if l_col in lendings_df.columns:
                active_lend = lendings_df[lendings_df['isCleared'] != 'Yes'] if 'isCleared' in lendings_df.columns else lendings_df
                actual_sum = active_lend[l_col].sum()
        
        if abs(reported_lent - actual_sum) > 10:
            warnings.append(f"⚠️ Lending Mismatch: Summary reports ₹{reported_lent:,.0f} but sum of active entries is ₹{actual_sum:,.0f}.")
            
        return warnings

    @staticmethod
    def get_metric_explanations(metrics):
        """Returns detailed strings explaining how each metric was calculated."""
        liquidity = metrics.get('total_cash', 0) + metrics.get('total_savings', 0)
        liabilities = metrics.get('total_cc_used', 0) + metrics.get('total_loan_owed', 0)
        
        return {
            "Net Worth": f"Net Worth = Total Assets - Total Liabilities\n"
                         f"₹{metrics.get('total_assets', 0):,.0f} (Cash + Savings + Lent + PF) - "
                         f"₹{liabilities:,.0f} (Credit Owed + Loans) = "
                         f"₹{metrics.get('net_worth', 0):,.0f}",
            
            "Wealth Velocity": f"Wealth Velocity = Monthly Savings + Monthly Investments\n"
                               f"₹{(metrics.get('monthly_income', 0) - metrics.get('monthly_expenses', 0)):,.0f} (Savings) + "
                               f"₹{metrics.get('total_investments', 0):,.0f} (Investments) = "
                               f"₹{metrics.get('wealth_velocity', 0):,.0f} per month",
            
            "FI Ratio": f"FI Ratio = Total Assets / Annual Expenses\n"
                        f"₹{metrics.get('total_assets', 0):,.0f} / (₹{metrics.get('monthly_expenses', 0):,.0f} × 12) = "
                        f"{metrics.get('fi_ratio', 0)} years",
            
            "Runway": f"Runway = Liquidity / Monthly Burn\n"
                      f"₹{liquidity:,.0f} / ₹{metrics.get('monthly_expenses', 0):,.0f} = "
                      f"{metrics.get('runway', 0)} months",
            
            "Savings Rate": f"Savings Rate = (Monthly Savings / Monthly Income) × 100\n"
                            f"(₹{(metrics.get('monthly_income', 0) - metrics.get('monthly_expenses', 0)):,.0f} / ₹{metrics.get('monthly_income', 0):,.0f}) × 100 = "
                            f"{metrics.get('savings_rate', 0)}%",
            
            "Monthly Income": f"Monthly Income = Budgeted Income (or latest recorded entry)\n"
                              f"Baseline: ₹{metrics.get('monthly_income', 0):,.0f}",
            
            "Monthly Burn": f"Monthly Burn = Outflows strictly excluding Investments\n"
                            f"Total Burn: ₹{metrics.get('monthly_expenses', 0):,.0f}",
            
            "Credit Used": f"Total amount owed across all cards: ₹{metrics.get('total_cc_used', 0):,.0f}",
            
            "Utilisation": f"Utilisation = (Total Owed / Total Limit) × 100\n"
                           f"(₹{metrics.get('total_cc_used', 0):,.0f} / ₹{metrics.get('total_cc_limit', 0):,.0f}) × 100 = "
                           f"{metrics.get('util_pct', 0)}%",
            
            "Liquidity": f"Liquidity = Total Cash + Total Savings\n"
                         f"₹{metrics.get('total_cash', 0):,.0f} + ₹{metrics.get('total_savings', 0):,.0f} = "
                         f"₹{liquidity:,.0f}",
            
            "Total Available": f"Total Available = Liquidity + Credit Available\n"
                               f"₹{liquidity:,.0f} + (₹{metrics.get('total_cc_limit', 0):,.0f} - ₹{metrics.get('total_cc_used', 0):,.0f}) = "
                               f"₹{metrics.get('total_available_funds', 0):,.0f}"
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

    @staticmethod
    def get_net_worth_history(data, current_nw):
        history_df = data.get('nw_history', pd.DataFrame())
        if history_df.empty:
            return pd.DataFrame()
        
        if 'Date' in history_df.columns and 'Net Worth' in history_df.columns:
            df = history_df.copy()
            df['Date'] = pd.to_datetime(df['Date'], dayfirst=True)
            current_row = pd.DataFrame([{'Date': datetime.now(), 'Net Worth': current_nw}])
            df = pd.concat([df, current_row], ignore_index=True)
            return df.sort_values('Date')
        return pd.DataFrame()
