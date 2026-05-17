import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime

from services import FinanceService
from models import (
    engine,
    Account,
    CreditCard,
    CCPayment,
    Lending,
    Loan,
    Income,
    create_db_and_tables,
)
from sqlmodel import Session, select
from calculations import FinanceCalculations, EXCLUDED_OWNERS
from utils import format_date

# --- Config & Style ---
st.set_page_config(page_title="Financial Intelligence Dashboard", layout="wide")

# Initialize DB (Unified SQLModel)
create_db_and_tables()

# Custom UI Styling
st.markdown(
    """
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

    /* Modern Premium Styles */
    .premium-container {
        max-width: 1200px;
        margin: 0 auto;
        padding: 20px 0;
    }
    
    .premium-card {
        padding: 24px;
        border-radius: 20px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.08);
        border: 1px solid rgba(0,0,0,0.05);
        transition: all 0.3s ease;
        margin-bottom: 16px;
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
        font-size: 14px;
        font-weight: 600;
        color: #555;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        margin-bottom: 8px;
    }
    .card-value {
        font-size: 32px;
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
        background: white;
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
    """,
    unsafe_allow_html=True,
)


def render_metric_card(label, value, theme_class, col, small=False):
    font_size = "2rem" if not small else "1.5rem"
    padding = "24px" if not small else "16px"
    with col:
        st.markdown(
            f"""
            <div class="premium-card {theme_class}" style="padding: {padding};">
                <div class="card-label" style="font-size: {'14px' if not small else '12px'};">{label}</div>
                <div class="card-value" style="font-size: {font_size};">{value}</div>
            </div>
        """,
            unsafe_allow_html=True,
        )


def show_dashboard(data, metrics):
    st.title("Financial Intelligence 🏦")

    explanations = metrics.get("metric_explanations", {})

    # --- Level 1: Primary Insights (Always Visible, Large) ---
    st.markdown("### Primary Insights")
    l1_cols = st.columns(4)
    render_metric_card(
        "💰 Net Worth",
        f"₹{metrics.get('net_worth', 0):,.0f}",
        "card-savings",
        l1_cols[0],
    )
    render_metric_card(
        "📈 Savings Rate",
        f"{metrics.get('savings_rate', 0)}%",
        "card-generic",
        l1_cols[1],
    )
    render_metric_card(
        "🛫 Runway", f"{metrics.get('runway', 0)} Mo", "card-non-personal", l1_cols[2]
    )
    render_metric_card(
        "🚀 Wealth Velocity",
        f"₹{metrics.get('wealth_velocity', 0):,.0f}/mo",
        "card-income",
        l1_cols[3],
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Level 2: Supporting Metrics (Visible but less dominant) ---
    st.markdown("#### Supporting Metrics")
    l2_cols = st.columns(4)
    liquidity = metrics.get("total_cash", 0) + metrics.get("total_savings", 0)
    render_metric_card(
        "💧 Liquidity", f"₹{liquidity:,.0f}", "card-generic", l2_cols[0], small=True
    )
    render_metric_card(
        "🏖️ FI Ratio",
        f"{metrics.get('fi_ratio', 0)} Yrs",
        "card-personal",
        l2_cols[1],
        small=True,
    )
    render_metric_card(
        "💳 Credit Util",
        f"{metrics.get('util_pct', 0)}%",
        "card-expenses",
        l2_cols[2],
        small=True,
    )
    render_metric_card(
        "🛡️ Total Available",
        f"₹{metrics.get('total_available_funds', 0):,.0f}",
        "card-savings",
        l2_cols[3],
        small=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Level 3: Deep Dive (Expandable Detail) ---
    with st.expander("🔍 Metric Formulas & Calculation Breakdowns", expanded=False):
        st.info(
            "Click on a metric below to see the exact formula and numbers used for its calculation."
        )

        # We'll group these in columns for better vertical space usage
        exp_cols = st.columns(2)

        metric_keys = list(explanations.keys())
        half = (len(metric_keys) + 1) // 2

        for i, key in enumerate(metric_keys):
            target_col = exp_cols[0] if i < half else exp_cols[1]
            with target_col:
                with st.expander(f"Detailed Breakdown: {key}", expanded=False):
                    content = explanations.get(key, "No details available.")
                    # Split formula from result if possible for cleaner look
                    if "\n" in content:
                        parts = content.split("\n", 1)
                        st.markdown(f"**Formula:**")
                        st.code(parts[0], language="text")
                        st.markdown(f"**Current Calculation:**")
                        st.code(parts[1], language="text")
                    else:
                        st.code(content, language="text")

    st.markdown("<br><hr>", unsafe_allow_html=True)

    # --- Cash Flow & Baseline Summary ---
    st.subheader("Monthly Baseline")
    col_a, col_b = st.columns(2)

    l3_baseline_cols = st.columns(3)
    render_metric_card(
        "💵 Income",
        f"₹{metrics.get('monthly_income', 0):,.0f}",
        "card-income",
        l3_baseline_cols[0],
        small=True
    )
    render_metric_card(
        "🔥 Burn",
        f"₹{metrics.get('monthly_expenses', 0):,.0f}",
        "card-expenses",
        l3_baseline_cols[1],
        small=True
    )
    render_metric_card(
        "🛡️ Available",
        f"₹{metrics.get('total_available_funds', 0):,.0f}",
        "card-generic",
        l3_baseline_cols[2],
        small=True
    )

    st.divider()

    # --- Trend & Allocation Section ---
    left_col, right_col = st.columns([1.2, 1])

    with left_col:
        # Net Worth History & Projection
        st.subheader("Net Worth Trend")
        nw_history = FinanceCalculations.get_net_worth_history(
            data, metrics.get("net_worth", 0)
        )

        if not nw_history.empty:
            fig_hist = px.line(nw_history, x="Date", y="Net Worth", markers=True)
            st.plotly_chart(fig_hist, width="stretch")
        else:
            months = np.arange(1, 13)
            monthly_savings = metrics.get("wealth_velocity", 0)
            projection = [
                metrics.get("net_worth", 0) + (monthly_savings * m) for m in months
            ]
            fig_proj = px.line(
                x=months,
                y=projection,
                markers=True,
                labels={"x": "Month", "y": "Net Worth"},
            )
            fig_proj.update_layout(yaxis_tickformat=",.0f")
            st.plotly_chart(fig_proj, width="stretch")

        st.subheader("Income vs Expenses")
        cash_flow_df = FinanceCalculations.get_cash_flow_data(metrics, data)
        fig_cf = px.bar(
            cash_flow_df,
            x="Category",
            y="Amount",
            color="Category",
            color_discrete_sequence=["#2ECC71", "#E74C3C", "#3498DB"],
            text_auto=".2s",
        )
        st.plotly_chart(fig_cf, width="stretch")

    with right_col:
        st.subheader("Asset Allocation")
        asset_df = FinanceCalculations.get_asset_allocation(metrics, data)
        fig_pie = px.pie(
            asset_df,
            values="Balance",
            names="Asset",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.T10,
        )
        st.plotly_chart(fig_pie, width="stretch")

        st.subheader("Credit Health")
        fig_gauge = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=metrics.get("util_pct", 0),
                gauge={
                    "axis": {"range": [None, 100]},
                    "bar": {
                        "color": (
                            "#E74C3C" if metrics.get("util_pct", 0) > 30 else "#2ECC71"
                        )
                    },
                    "steps": [
                        {"range": [0, 30], "color": "rgba(46, 204, 113, 0.2)"},
                        {"range": [30, 70], "color": "rgba(241, 196, 15, 0.2)"},
                        {"range": [70, 100], "color": "rgba(231, 76, 60, 0.2)"},
                    ],
                },
            )
        )
        st.plotly_chart(fig_gauge, width="stretch")


def show_credit(data, metrics):
    st.title("Credit Summary")

    # --- Credit Summary Section ---
    cols_sum = st.columns(3)
    render_metric_card(
        "💳 Total Limit",
        f"₹{metrics.get('total_cc_limit', 0):,.0f}",
        "card-generic",
        cols_sum[0],
        small=True
    )
    render_metric_card(
        "🔥 Total Due",
        f"₹{metrics.get('total_cc_used', 0):,.0f}",
        "card-expenses",
        cols_sum[1],
        small=True
    )
    render_metric_card(
        "🛡️ Available",
        f"₹{metrics.get('total_credit_available', 0):,.0f}",
        "card-savings",
        cols_sum[2],
        small=True
    )


    st.markdown("<br>", unsafe_allow_html=True)
    st.divider()

    # --- Credit Card Details Section ---
    st.subheader("Card Details")
    cc_df = data.get("credit_cards", pd.DataFrame())

    if not cc_df.empty:
        # Create columns for cards (3 per row)
        cols = st.columns(3)
        for i, (_, row) in enumerate(cc_df.iterrows()):
            col = cols[i % 3]
            name = row.get("Card Provider", "Unknown")
            due = row.get("Current Balance", 0)
            limit = row.get("Max Limit", 0)
            avail = row.get("Available Credit", 0)
            util = (due / limit * 100) if limit > 0 else 0

            theme = (
                "card-expenses"
                if util > 70
                else ("card-non-personal" if util > 30 else "card-generic")
            )

            with col:
                st.markdown(
                    f"""
                    <div class="category-card {theme}">
                        <div class="category-header">
                            <span>{name}</span>
                            <span class="cat-total">{util:.1f}%</span>
                        </div>
                        <div class="budget-row">
                            <span class="row-label">Max Limit</span>
                            <span class="row-amount" style="color: #888;">₹{limit:,.0f}</span>
                        </div>
                        <div class="budget-row">
                            <span class="row-label">Credit Due</span>
                            <span class="row-amount">₹{due:,.0f}</span>
                        </div>
                        <div class="budget-row" style="border-bottom: none;">
                            <span class="row-label">Available</span>
                            <span class="row-amount">₹{avail:,.0f}</span>
                        </div>
                    </div>
                """,
                    unsafe_allow_html=True,
                )
    else:
        st.info("No credit card details found.")

    st.divider()

    # --- Bill & Payment Trends Section ---
    st.subheader("Bill & Payment Trends 📈")

    trend_df = FinanceCalculations.get_payment_trends(data)
    if not trend_df.empty:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            types = ["ALL"] + sorted(
                [str(x) for x in trend_df["Type"].dropna().unique()]
            )
            selected_type = st.selectbox("Filter by Bill Type", types)
        with col_f2:
            categories = sorted(
                [str(x) for x in trend_df["Category"].dropna().unique()]
            )
            selected_cats = st.multiselect(
                "Filter by Account(s)", categories, default=[]
            )

        plot_df = trend_df.copy()
        if selected_type != "ALL":
            plot_df = plot_df[plot_df["Type"] == selected_type]
        if selected_cats:
            plot_df = plot_df[plot_df["Category"].isin(selected_cats)]

        chart = (
            alt.Chart(plot_df)
            .mark_bar(stroke="white", strokeWidth=0.5)
            .encode(
                x=alt.X(
                    "yearmonth(Date):T",
                    title="Month",
                    axis=alt.Axis(format="%b %Y", labelAngle=-45),
                ),
                y=alt.Y("Amount:Q", title="Amount (₹)"),
                color=alt.Color("Category:N", title="Bill/Card"),
                detail="ExactDate:N",
                tooltip=["ExactDate", "Category", "Amount", "Type"],
            )
            .properties(height=450)
            .interactive()
        )

        st.altair_chart(chart, width="stretch")

        with st.expander("View Recent Activity Details"):
            st.dataframe(
                plot_df.sort_values("Date", ascending=False)[
                    ["ExactDate", "Category", "Amount", "Type"]
                ],
                width="stretch",
            )
    else:
        st.info("No payment history found to display trends.")


def show_quick_entry(service: FinanceService):
    st.title("Quick Entry 📝")
    st.info("Record transactions quickly.")

    with st.expander("💸 Add Expense", expanded=True):
        with st.form("expense_form", clear_on_submit=True):
            category = st.selectbox(
                "Category",
                [
                    "Food",
                    "Transport",
                    "Shopping",
                    "Entertainment",
                    "Bills",
                    "Health",
                    "Other",
                ],
            )
            amount = st.number_input("Amount", min_value=0.0, format="%.2f")
            account = st.selectbox(
                "Account", ["Credit Card", "Cash", "Savings Account"]
            )
            date = st.date_input("Date", datetime.now())
            submit = st.form_submit_button("Add Expense")
            if submit:
                # Direct expense entry is temporarily managed via Excel upload in the unified model.
                st.info("Direct expense entry is temporarily managed via Excel upload.")

    with st.expander("💳 Record CC Payment"):
        with Session(engine) as session:
            cards = session.exec(select(CreditCard)).all()
            card_options = {c.name: c.id for c in cards}

        with st.form("cc_payment_form", clear_on_submit=True):
            card_name = st.selectbox(
                "Select Card",
                options=list(card_options.keys()) if card_options else ["None Found"],
            )
            amount = st.number_input("Amount", min_value=0.0, format="%.2f")
            date = st.date_input("Date", datetime.now())
            submit = st.form_submit_button("Record Payment")
            if submit and card_options:
                service.add_manual_payment(
                    card_id=card_options[card_name],
                    amount=amount,
                    date=datetime.combine(date, datetime.min.time()),
                )
                st.success(f"Payment recorded for {card_name}!")

    with st.expander("🤝 Record Lending"):
        with st.form("lending_form", clear_on_submit=True):
            borrower = st.text_input("Borrower Name")
            amount = st.number_input("Amount", min_value=0.0, format="%.2f")
            due_date = st.date_input("Due Date", datetime.now())
            submit = st.form_submit_button("Add Lending")
            if submit:
                service.add_manual_lending(
                    person=borrower,
                    amount=amount,
                    due_date=datetime.combine(due_date, datetime.min.time()),
                )
                st.success(f"Lending to {borrower} recorded!")

    with st.expander("💰 Add Income"):
        with st.form("income_form", clear_on_submit=True):
            source = st.text_input("Source")
            amount = st.number_input("Amount", min_value=0.0, format="%.2f")
            date = st.date_input("Date", datetime.now())
            submit = st.form_submit_button("Add Income")
            if submit:
                service.add_manual_income(
                    source=source, amount=amount, date=date.strftime("%B %Y")
                )
                st.success(f"Income from {source} added!")


def show_lending(data):
    st.title("Lendings & Loans 🤝")

    # Filter outside cards to avoid layout breaking
    show_active_lend = st.sidebar.checkbox("Show Active Only (Lendings)", value=True)

    col_l, col_r = st.columns(2)

    with col_l:
        # 1. Repayment Tracker (Lendings)
        lend_df = data["lendings"]
        if show_active_lend and not lend_df.empty and "isCleared" in lend_df.columns:
            lend_display = lend_df[lend_df["isCleared"] != "Yes"].copy()
        else:
            lend_display = lend_df.copy()

        lend_items_html = ""
        total_due = 0
        if not lend_display.empty:
            for _, row in lend_display.iterrows():
                person = row.get("Lent to", "Unknown")
                amount = row.get("Amount Due", row.get("Amount Lent", 0))
                total_due += amount
                due = row.get("Due Date", "N/A")
                lend_items_html += f'<div class="budget-row"><span class="row-label">{person} <small style="color:#888">({due})</small></span><span class="row-amount">₹{amount:,.0f}</span></div>'
        else:
            lend_items_html = '<div class="budget-row"><span class="row-label" style="color:#888; font-style:italic;">No active records</span></div>'

        st.markdown(
            f"""
            <div class="category-card card-savings">
                <div class="category-header">
                    <span>Repayment Tracker</span>
                    <span class="cat-total">₹{total_due:,.0f}</span>
                </div>
                {lend_items_html}
            </div>
        """,
            unsafe_allow_html=True,
        )

        # 2. EMI Obligations
        emi_df = data["emis"]
        emi_display = emi_df.copy()
        if not emi_display.empty and "IsClosed" in emi_display.columns:
            emi_display = emi_display[emi_display["IsClosed"] == "No"]
        if not emi_display.empty and "Actual Owner" in emi_display.columns:
            emi_display = emi_display[
                ~emi_display["Actual Owner"].isin(EXCLUDED_OWNERS)
            ]

        emi_items_html = ""
        total_emi = 0
        if not emi_display.empty:
            for _, row in emi_display.iterrows():
                provider = row.get("Provider", "Unknown")
                amount = row.get("Amt Due", row.get("EMI Amount", 0))
                total_emi += amount
                rem = row.get("EMIs Remaining", row.get("Months Left", "N/A"))
                emi_items_html += f'<div class="budget-row"><span class="row-label">{provider} <small style="color:#888">({rem} left)</small></span><span class="row-amount">₹{amount:,.0f}</span></div>'
        else:
            emi_items_html = '<div class="budget-row"><span class="row-label" style="color:#888; font-style:italic;">No active EMIs</span></div>'

        st.markdown(
            f"""
            <div class="category-card card-expenses">
                <div class="category-header">
                    <span>EMI Obligations</span>
                    <span class="cat-total">₹{total_emi:,.0f}</span>
                </div>
                {emi_items_html}
            </div>
        """,
            unsafe_allow_html=True,
        )

    with col_r:
        # 3. Money Owed (Loans)
        loan_df = data["loans"]
        loan_display = (
            loan_df[(loan_df["Cleared"] == "No") & (loan_df["own"] == "Yes")].copy()
            if not loan_df.empty
            else loan_df
        )

        loan_items_html = ""
        total_loan = 0
        if not loan_display.empty:
            for _, row in loan_display.iterrows():
                label = row.get("Loan Name", "Loan")
                amount = row.get("Amount Due", 0)
                total_loan += amount
                loan_items_html += f'<div class="budget-row"><span class="row-label">{label}</span><span class="row-amount">₹{amount:,.0f}</span></div>'
        else:
            loan_items_html = '<div class="budget-row"><span class="row-label" style="color:#888; font-style:italic;">No loans owed</span></div>'

        st.markdown(
            f"""
            <div class="category-card card-expenses">
                <div class="category-header">
                    <span>Money Owed (Loans)</span>
                    <span class="cat-total">₹{total_loan:,.0f}</span>
                </div>
                {loan_items_html}
            </div>
        """,
            unsafe_allow_html=True,
        )


def show_goals(metrics):
    st.title("Goals & Wishlist 🎯")

    target = 400000
    current = metrics.get("total_savings", 0)
    progress_pct = min(current / target * 100, 100.0)
    forecast_msg = FinanceCalculations.get_goal_forecast(metrics, target)

    st.markdown(
        f"""
        <div class="premium-container">
            <div class="category-card card-savings">
                <div class="category-header">
                    <span>Emergency Fund Goal</span>
                    <span class="cat-total">{progress_pct:.1f}%</span>
                </div>
                <div style="margin-top: 24px; margin-bottom: 24px;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
                        <span class="row-label">Target: ₹{target:,.0f}</span>
                        <span class="row-amount">Status: ₹{current:,.0f}</span>
                    </div>
                    <div style="background-color: rgba(0,0,0,0.05); height: 16px; border-radius: 8px; overflow: hidden; border: 1px solid rgba(0,0,0,0.03);">
                        <div style="background: linear-gradient(90deg, #52c41a 0%, #73d13d 100%); width: {progress_pct}%; height: 100%; border-radius: 8px; transition: width 1s ease-in-out;"></div>
                    </div>
                </div>
                <div style="background: rgba(82, 196, 26, 0.05); padding: 16px; border-radius: 12px; border: 1px solid rgba(82, 196, 26, 0.1);">
                    <span style="font-size: 14px; color: #389e0d; font-weight: 600;">✨ Estimated Completion:</span>
                    <span style="font-size: 14px; color: #111; margin-left: 8px;">{forecast_msg}</span>
                </div>
            </div>
        </div>
    """,
        unsafe_allow_html=True,
    )


def show_budget(data):
    st.title("Monthly Budget 📊")
    budget_df = data.get("budget")

    if isinstance(budget_df, list):
        budget_df = pd.DataFrame(budget_df)

    if budget_df is None or budget_df.empty:
        st.warning("No budget data found in the 'Monthly Budget' sheet.")
        return

    income = budget_df[budget_df["Category"] == "Income"]["Amount"].sum()
    expenses = budget_df[budget_df["Category"] != "Income"]["Amount"].sum()
    savings_plan = income - expenses

    # Wrap content in a focused container
    st.markdown('<div class="premium-container">', unsafe_allow_html=True)

    # Summary Cards
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            f'<div class="premium-card card-income"><div class="card-label">Expected Income</div><div class="card-value">₹{income:,.0f}</div></div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f'<div class="premium-card card-expenses"><div class="card-label">Budgeted Burn</div><div class="card-value">₹{expenses:,.0f}</div></div>',
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f'<div class="premium-card card-savings"><div class="card-label">Projected Savings</div><div class="card-value">₹{savings_plan:,.0f}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-bottom: 48px;'></div>", unsafe_allow_html=True)

    # Detailed Category View
    all_cats = budget_df["Category"].unique()
    left_col, right_col = st.columns(2)

    for i, cat in enumerate(all_cats):
        target_col = left_col if i % 2 == 0 else right_col
        cat_data = budget_df[budget_df["Category"] == cat]
        cat_total = cat_data["Amount"].sum()

        # Determine theme class
        card_class = "card-generic"
        if "PERSONAL" in cat.upper():
            card_class = "card-personal"
        if "INCOME" in cat.upper():
            card_class = "card-income"
        if "NON PERSONAL" in cat.upper():
            card_class = "card-non-personal"
        if "UTILIT" in cat.upper() or "FIXED" in cat.upper():
            card_class = "card-generic"

        with target_col:
            items_html = ""
            subcats = cat_data["Subcategory"].unique()
            for sub in subcats:
                if sub:
                    items_html += f'<div class="subcategory-header">{sub}</div>'

                sub_items = (
                    cat_data[cat_data["Subcategory"] == sub]
                    if sub
                    else cat_data[cat_data["Subcategory"].isna()]
                )
                for _, row in sub_items.iterrows():
                    items_html += f'<div class="budget-row"><span class="row-label">{row["Item"]}</span><span class="row-amount">₹{row["Amount"]:,.0f}</span></div>'

            st.markdown(
                f"""
                <div class="category-card {card_class}">
                    <div class="category-header">
                        <span>{cat}</span>
                        <span class="cat-total">₹{cat_total:,.0f}</span>
                    </div>
                    {items_html}
                </div>
            """,
                unsafe_allow_html=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)


def main():
    # Init service
    service = FinanceService()
    data = service.get_dashboard_data()

    if not data or (isinstance(data, dict) and len(data) == 0):
        st.error("Financial data not found.")
        uploaded = st.sidebar.file_uploader("Upload Finance Excel", type=["xlsx"])
        if uploaded:
            with open("latest_finance.xlsx", "wb") as f:
                f.write(uploaded.getbuffer())
            service.migrate_excel_to_db("latest_finance.xlsx")
            st.rerun()
        return

    metrics = data  # FinanceService returns metrics merged with data

    # Show Sanity Warnings if any
    if "sanity_warnings" in data and data["sanity_warnings"]:
        for warning in data["sanity_warnings"]:
            st.warning(warning)

    # Sidebar Actions
    st.sidebar.title("Actions")
    report_text = service.generate_report(data)
    st.sidebar.download_button(
        label="📥 Download Intelligence Report",
        data=report_text,
        file_name=f"financial_intelligence_report_{datetime.now().strftime('%Y%m%d')}.html",
        mime="text/html",
    )

    if st.sidebar.button("🔄 Refresh Data"):
        st.rerun()

    # Top Navigation with split titles
    tabs = st.tabs(
        ["📊\nDashboard", "💳\nCredit", "📅\nBudget", "🤝\nLending", "🎯\nGoals"]
    )

    with tabs[0]:
        show_dashboard(data, metrics)
    with tabs[1]:
        show_credit(data, metrics)
    with tabs[2]:
        show_budget(data)
    with tabs[3]:
        show_lending(data)
    with tabs[4]:
        show_goals(metrics)


if __name__ == "__main__":
    main()
