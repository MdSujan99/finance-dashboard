import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime

from data_loader import DataLoader
from calculations import FinanceCalculations, EXCLUDED_OWNERS
from database import init_db, add_expense, add_cc_payment, add_lending, add_income

# --- Config & Style ---
st.set_page_config(page_title="Financial Intelligence Dashboard", layout="wide")

# Initialize DB
init_db()

# Custom UI Styling
st.markdown("""
    <style>
    /* Global Layout */
    .main .block-container {
        padding-top: 1.5rem;
    }
    
    /* Small Button Styling */
    div[data-testid="stPopover"] > button {
        border: 1px solid #eee !important;
        background: #f8f9fa !important;
        padding: 0px 8px !important;
        height: 22px !important;
        width: 22px !important;
        min-height: unset !important;
        border-radius: 4px !important;
        font-size: 12px !important;
        font-family: serif !important;
        font-style: italic !important;
    }

    /* Metric Value Styling */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
    }

    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 5px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 70px;
        white-space: pre-wrap;
        background-color: var(--secondary-background-color);
        border-radius: 5px 5px 0px 0px;
        padding: 5px;
        text-align: center;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        font-size: 14px;
        line-height: 1.2;
    }
    </style>
    """, unsafe_allow_html=True)

def show_dashboard(data, metrics):
    st.title("Financial Intelligence 🏦")
    
    explanations = FinanceCalculations.get_metric_explanations(metrics)

    def render_card(label, value, col):
        with col:
            with st.container(border=True):
                # Using columns inside container to place button top-right
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.metric(label, value)
                with c2:
                    with st.popover("ƒ", help="Calculation Details"):
                        st.markdown(f"### {label}")
                        st.code(explanations.get(label.split(" ", 1)[-1], "No details"), language="text")

    # --- Top Row Metrics ---
    cols1 = st.columns(5)
    render_card("💰 Net Worth", f"₹{metrics.get('net_worth', 0):,.0f}", cols1[0])
    render_card("🚀 Wealth Velocity", f"₹{metrics.get('wealth_velocity', 0):,.0f}/mo", cols1[1])
    render_card("🏖️ FI Ratio", f"{metrics.get('fi_ratio', 0)} Yrs", cols1[2])
    render_card("🛫 Runway", f"{metrics.get('runway', 0)} Mo", cols1[3])
    render_card("📈 Savings Rate", f"{metrics.get('savings_rate', 0)}%", cols1[4])

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Bottom Row Metrics ---
    cols2 = st.columns(6)
    render_card("💵 Monthly Income", f"₹{metrics.get('monthly_income', 0):,.0f}", cols2[0])
    render_card("🔥 Monthly Burn", f"₹{metrics.get('monthly_expenses', 0):,.0f}", cols2[1])
    render_card("💳 Credit Used", f"₹{metrics.get('total_cc_used', 0):,.0f}", cols2[2])
    render_card("📊 Utilisation", f"{metrics.get('util_pct', 0)}%", cols2[3])
    render_card("💧 Liquidity", f"₹{metrics.get('total_cash', 0) + metrics.get('total_savings', 0):,.0f}", cols2[4])
    render_card("🏦 Total Available", f"₹{metrics.get('total_available_funds', 0):,.0f}", cols2[5])

    st.divider()

    # --- Trend & Allocation Section ---
    left_col, right_col = st.columns([1.2, 1])

    with left_col:
        # Net Worth History & Projection
        st.subheader("Net Worth Trend")
        nw_history = FinanceCalculations.get_net_worth_history(data, metrics.get('net_worth', 0))
        
        if not nw_history.empty:
            fig_hist = px.line(nw_history, x='Date', y='Net Worth', markers=True)
            st.plotly_chart(fig_hist, width="stretch")
        else:
            months = np.arange(1, 13)
            monthly_savings = metrics.get('wealth_velocity', 0)
            projection = [metrics.get('net_worth', 0) + (monthly_savings * m) for m in months]
            fig_proj = px.line(x=months, y=projection, markers=True, labels={'x':'Month', 'y':'Net Worth'})
            fig_proj.update_layout(yaxis_tickformat=",.0f")
            st.plotly_chart(fig_proj, width="stretch")

        st.subheader("Income vs Expenses")
        cash_flow_df = FinanceCalculations.get_cash_flow_data(metrics, data)
        fig_cf = px.bar(cash_flow_df, x='Category', y='Amount', color='Category', 
                         color_discrete_sequence=['#2ECC71', '#E74C3C', '#3498DB'], text_auto='.2s')
        st.plotly_chart(fig_cf, width="stretch")

    with right_col:
        st.subheader("Asset Allocation")
        asset_df = FinanceCalculations.get_asset_allocation(metrics, data)
        fig_pie = px.pie(asset_df, values='Balance', names='Asset', hole=.4, color_discrete_sequence=px.colors.qualitative.T10)
        st.plotly_chart(fig_pie, width="stretch")

        st.subheader("Credit Health")
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = metrics.get('util_pct', 0),
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': "#E74C3C" if metrics.get('util_pct', 0) > 30 else "#2ECC71"},
                'steps' : [{'range': [0, 30], 'color': "rgba(46, 204, 113, 0.2)"}, {'range': [30, 70], 'color': "rgba(241, 196, 15, 0.2)"}, {'range': [70, 100], 'color': "rgba(231, 76, 60, 0.2)"}]
            }
        ))
        st.plotly_chart(fig_gauge, width="stretch")

def show_trends(data):
    st.title("Bill & Payment Trends 📈")
    
    trend_df = FinanceCalculations.get_payment_trends(data)
    if not trend_df.empty:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            types = ['ALL'] + sorted(trend_df['Type'].unique().tolist())
            selected_type = st.selectbox("Filter by Bill Type", types)
        with col_f2:
            categories = sorted(trend_df['Category'].unique().tolist())
            selected_cats = st.multiselect("Filter by Account(s)", categories, default=[])
        
        plot_df = trend_df.copy()
        if selected_type != 'ALL': plot_df = plot_df[plot_df['Type'] == selected_type]
        if selected_cats: plot_df = plot_df[plot_df['Category'].isin(selected_cats)]
        
        chart = alt.Chart(plot_df).mark_bar(stroke='white', strokeWidth=0.5).encode(
            x=alt.X('yearmonth(Date):T', title='Month', axis=alt.Axis(format='%b %Y', labelAngle=-45)),
            y=alt.Y('Amount:Q', title='Amount (₹)'),
            color=alt.Color('Category:N', title='Bill/Card'),
            detail='ExactDate:N',
            tooltip=['ExactDate', 'Category', 'Amount', 'Type']
        ).properties(height=450).interactive()
        
        st.altair_chart(chart, width="stretch")
        
        st.subheader("Recent Activity")
        st.dataframe(plot_df.sort_values('Date', ascending=False)[['ExactDate', 'Category', 'Amount', 'Type']], width="stretch")
    else:
        st.info("No payment history found to display trends.")

def show_quick_entry():
    st.title("Quick Entry 📝")
    st.info("Record transactions quickly.")

    with st.expander("💸 Add Expense", expanded=True):
        with st.form("expense_form", clear_on_submit=True):
            category = st.selectbox("Category", ["Food", "Transport", "Shopping", "Entertainment", "Bills", "Health", "Other"])
            amount = st.number_input("Amount", min_value=0.0, format="%.2f")
            account = st.selectbox("Account", ["Credit Card", "Cash", "Savings Account"])
            date = st.date_input("Date", datetime.now())
            submit = st.form_submit_button("Add Expense")
            if submit:
                add_expense(date.strftime('%Y-%m-%d'), category, amount, account)
                st.success(f"Expense of ₹{amount} added!")

    with st.expander("💳 Record CC Payment"):
        with st.form("cc_payment_form", clear_on_submit=True):
            card_name = st.text_input("Card Name")
            amount = st.number_input("Amount", min_value=0.0, format="%.2f")
            date = st.date_input("Date", datetime.now())
            submit = st.form_submit_button("Record Payment")
            if submit:
                add_cc_payment(date.strftime('%Y-%m-%d'), card_name, amount)
                st.success(f"Payment recorded!")

    with st.expander("🤝 Record Lending"):
        with st.form("lending_form", clear_on_submit=True):
            borrower = st.text_input("Borrower Name")
            amount = st.number_input("Amount", min_value=0.0, format="%.2f")
            due_date = st.date_input("Due Date", datetime.now())
            status = st.selectbox("Status", ["Pending", "Cleared"])
            submit = st.form_submit_button("Add Lending")
            if submit:
                add_lending(datetime.now().strftime('%Y-%m-%d'), borrower, amount, due_date.strftime('%Y-%m-%d'), status)
                st.success(f"Lending recorded!")

    with st.expander("💰 Add Income"):
        with st.form("income_form", clear_on_submit=True):
            source = st.text_input("Source")
            amount = st.number_input("Amount", min_value=0.0, format="%.2f")
            date = st.date_input("Date", datetime.now())
            submit = st.form_submit_button("Add Income")
            if submit:
                add_income(date.strftime('%Y-%m-%d'), source, amount)
                st.success(f"Income added!")

def show_lending(data):
    st.title("Lendings & Loans 🤝")
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("Repayment Tracker")
        lend_df = data['lendings']
        show_active_lend = st.checkbox("Show Active Only", value=True)
        if show_active_lend and not lend_df.empty and 'isCleared' in lend_df.columns:
            lend_display = lend_df[lend_df['isCleared'] != 'Yes'].copy()
        else: lend_display = lend_df.copy()
        l_cols = ['Lent to', 'Amount Lent', 'Amount Due', 'Due Date', 'isCleared']
        st.dataframe(lend_display[[c for c in l_cols if c in lend_display.columns]], width="stretch")
        
        st.subheader("EMI Obligations")
        # EXCLUDED_OWNERS defined at top of dashboard.py or calculations.py
        emi_df = data['emis']
        emi_display = emi_df.copy()
        if not emi_display.empty and 'IsClosed' in emi_display.columns:
            emi_display = emi_display[emi_display['IsClosed'] == 'No']
        if not emi_display.empty and 'Actual Owner' in emi_display.columns:
            emi_display = emi_display[~emi_display['Actual Owner'].isin(EXCLUDED_OWNERS)]
        st.table(emi_display)

    with col_r:
        st.subheader("Money Owed (Loans)")
        loan_df = data['loans']
        loan_display = loan_df[(loan_df['Cleared'] == 'No') & (loan_df['own'] == 'Yes')].copy() if not loan_df.empty else loan_df
        st.dataframe(loan_display, width="stretch")

def show_goals(metrics):
    st.title("Goals & Wishlist 🎯")
    target = 400000
    current = metrics.get('total_savings', 0)
    progress = min(current/target, 1.0)
    st.subheader("Emergency Fund Goal")
    st.write(f"**Target: ₹{target:,.0f}**")
    st.progress(progress)
    st.write(f"Status: {progress*100:.1f}% Complete")
    
    forecast_msg = FinanceCalculations.get_goal_forecast(metrics, target)
    st.success(f"**Estimated Completion:** {forecast_msg}")

def show_budget(data):
    st.title("Monthly Budget 📊")
    budget_df = data.get('budget')
    
    if isinstance(budget_df, list):
        budget_df = pd.DataFrame(budget_df)
    
    if budget_df is None or budget_df.empty:
        st.warning("No budget data found in the 'Monthly Budget' sheet.")
        return

    income = budget_df[budget_df['Category'] == 'Income']['Amount'].sum()
    expenses = budget_df[budget_df['Category'] != 'Income']['Amount'].sum()
    savings_plan = income - expenses

    st.markdown("""
        <style>
        /* Modern Premium Budget Styles */
        .budget-container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px 0;
        }
        
        .budget-summary-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 32px;
            margin-bottom: 40px;
        }
        
        .budget-card {
            padding: 32px;
            border-radius: 20px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.08);
            border: 1px solid rgba(0,0,0,0.05);
            transition: all 0.3s ease;
        }
        
        .card-income { 
            background: linear-gradient(135deg, #f0f7ff 0%, #e6f2ff 100%);
            border-left: 8px solid #007bff; 
        }
        .card-expenses { 
            background: linear-gradient(135deg, #fff5f5 0%, #fff0f0 100%);
            border-left: 8px solid #ff4d4f; 
        }
        .card-savings { 
            background: linear-gradient(135deg, #f6ffed 0%, #f0f9eb 100%);
            border-left: 8px solid #52c41a; 
        }
        .card-personal {
            background: linear-gradient(135deg, #f9f0ff 0%, #f3e6ff 100%);
            border-left: 8px solid #722ed1;
        }
        .card-non-personal {
            background: linear-gradient(135deg, #fffbe6 0%, #fff7e6 100%);
            border-left: 8px solid #faad14;
        }
        .card-generic {
            background: linear-gradient(135deg, #f0fffb 0%, #e6fffb 100%);
            border-left: 8px solid #13c2c2;
        }
        
        .card-label {
            font-size: 15px;
            font-weight: 600;
            color: #555;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            margin-bottom: 12px;
        }
        .card-value {
            font-size: 40px;
            font-weight: 800;
            color: #111;
            line-height: 1;
        }
        
        .category-card {
            padding: 32px;
            border-radius: 20px;
            border: 1px solid rgba(0,0,0,0.05);
            box-shadow: 0 8px 24px rgba(0,0,0,0.06);
            margin-bottom: 32px;
            transition: transform 0.2s ease;
        }
        .category-header {
            font-size: 20px;
            font-weight: 800;
            color: #111;
            margin-bottom: 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid rgba(0,0,0,0.05);
            padding-bottom: 16px;
        }
        .cat-total {
            font-size: 22px;
            font-weight: 700;
            color: #000;
        }
        
        .budget-row {
            display: flex;
            justify-content: space-between;
            padding: 14px 0;
            border-bottom: 1px solid #fcfcfc;
            align-items: center;
        }
        .row-label { 
            font-size: 16px; 
            font-weight: 500;
            color: #444; 
        }
        .row-amount { 
            font-size: 18px; 
            font-weight: 700; 
            color: #000; 
        }
        
        .subcategory-header {
            font-weight: 800;
            font-size: 13px;
            color: #999;
            margin-top: 24px;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        </style>
    """, unsafe_allow_html=True)

    # Wrap content in a focused container
    st.markdown('<div class="budget-container">', unsafe_allow_html=True)

    # Summary Cards
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="budget-card card-income"><div class="card-label">Expected Income</div><div class="card-value">₹{income:,.0f}</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="budget-card card-expenses"><div class="card-label">Budgeted Burn</div><div class="card-value">₹{expenses:,.0f}</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="budget-card card-savings"><div class="card-label">Projected Savings</div><div class="card-value">₹{savings_plan:,.0f}</div></div>', unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 48px;'></div>", unsafe_allow_html=True)

    # Detailed Category View
    all_cats = budget_df['Category'].unique()
    left_col, right_col = st.columns(2)
    
    for i, cat in enumerate(all_cats):
        target_col = left_col if i % 2 == 0 else right_col
        cat_data = budget_df[budget_df['Category'] == cat]
        cat_total = cat_data['Amount'].sum()
        
        # Determine theme class
        card_class = "card-generic"
        if "PERSONAL" in cat.upper(): card_class = "card-personal"
        if "INCOME" in cat.upper(): card_class = "card-income"
        if "NON PERSONAL" in cat.upper(): card_class = "card-non-personal"
        if "UTILIT" in cat.upper() or "FIXED" in cat.upper(): card_class = "card-generic"

        with target_col:
            items_html = ""
            subcats = cat_data['Subcategory'].unique()
            for sub in subcats:
                if sub:
                    items_html += f'<div class="subcategory-header">{sub}</div>'
                
                sub_items = cat_data[cat_data['Subcategory'] == sub] if sub else cat_data[cat_data['Subcategory'].isna()]
                for _, row in sub_items.iterrows():
                    items_html += f'<div class="budget-row"><span class="row-label">{row["Item"]}</span><span class="row-amount">₹{row["Amount"]:,.0f}</span></div>'
            
            st.markdown(f"""
                <div class="category-card {card_class}">
                    <div class="category-header">
                        <span>{cat}</span>
                        <span class="cat-total">₹{cat_total:,.0f}</span>
                    </div>
                    {items_html}
                </div>
            """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def main():
    # Init loader
    loader = DataLoader("latest_finance.xlsx")
    data = loader.get_all_data()

    if data is None:
        st.error("`latest_finance.xlsx` not found.")
        uploaded = st.sidebar.file_uploader("Upload Finance Excel", type=["xlsx"])
        if uploaded:
            with open("latest_finance.xlsx", "wb") as f:
                f.write(uploaded.getbuffer())
            st.rerun()
        return

    metrics = FinanceCalculations.get_summary_metrics(data)

    # Sidebar Actions
    st.sidebar.title("Actions")
    report_text = FinanceCalculations.generate_report_text(data, metrics)
    st.sidebar.download_button(
        label="📥 Download Report",
        data=report_text,
        file_name=f"finance_report_{datetime.now().strftime('%Y%m%d')}.txt",
        mime="text/plain"
    )
    
    if st.sidebar.button("🔄 Refresh Data"):
        st.rerun()

    # Top Navigation with split titles
    tabs = st.tabs(["📊\nDashboard", "📈\nTrends", "📅\nBudget", "🤝\nLending", "🎯\nGoals"])
    
    with tabs[0]:
        show_dashboard(data, metrics)
    with tabs[1]:
        show_trends(data)
    with tabs[2]:
        show_budget(data)
    with tabs[3]:
        show_lending(data)
    with tabs[4]:
        show_goals(metrics)

if __name__ == "__main__":
    main()
