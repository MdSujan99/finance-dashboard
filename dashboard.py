import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import altair as alt
from data_loader import DataLoader
from calculations import FinanceCalculations, EXCLUDED_OWNERS

# --- Config & Style ---
st.set_page_config(page_title="Financial Intelligence Dashboard", layout="wide")

# Custom UI Styling (Theme Aware)
st.markdown("""
    <style>
    [data-testid="stMetric"] {
        background-color: var(--secondary-background-color);
        border: 1px solid var(--border-color);
        padding: 15px;
        border-radius: 10px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.1);
    }
    [data-testid="stSidebar"] {
        background-color: var(--secondary-background-color);
    }
    [data-testid="stMetricValue"] > div {
        color: var(--text-color);
    }
    [data-testid="stMetricLabel"] > div {
        color: var(--text-color);
        opacity: 0.8;
    }
    </style>
    """, unsafe_allow_html=True)

def main():
    st.title("Financial Intelligence Dashboard 🏦")
    
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

    # --- Header Metrics ---
    st.subheader("Key Performance Indicators")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Net Worth", f"₹{metrics.get('net_worth', 0):,.0f}", 
                help="Total Assets (Cash + Savings + Lent + PF) minus Total Liabilities (Credit Debt + Loans Owed)")
    col2.metric("Savings Rate", f"{metrics.get('savings_rate', 0)}%", 
                help="(Monthly Income - Monthly Expenses) / Monthly Income.")
    col3.metric("Runway", f"{metrics.get('runway', 0)} Months", 
                help="Liquid Assets (Cash + Savings) / Monthly Expenses.")
    col4.metric("Lent (Active)", f"₹{metrics.get('total_lent', 0):,.0f}", 
                help="Total money currently out with others.")
    col5.metric("Loans Owed", f"₹{metrics.get('total_loan_owed', 0):,.0f}", delta_color="inverse", 
                help="Total debt owed where 'own' is Yes and 'Cleared' is No.")

    m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
    m_col1.metric("Monthly Income", f"₹{metrics.get('monthly_income', 0):,.0f}")
    m_col2.metric("Monthly Burn Rate", f"₹{metrics.get('monthly_expenses', 0):,.0f}", 
                help="Total Monthly EMIs + Fixed Expenses + Approx Monthly Credit Spend.")
    m_col3.metric("Credit Used", f"₹{metrics.get('total_cc_used', 0):,.0f}")
    m_col4.metric("Credit Utilisation", f"{metrics.get('util_pct', 0)}%")
    m_col5.metric("Cash + Savings", f"₹{metrics.get('total_cash', 0) + metrics.get('total_savings', 0):,.0f}")

    st.divider()

    # --- Trend & Allocation Section ---
    left_col, right_col = st.columns([1.2, 1])

    with left_col:
        st.subheader("Net Worth Projection (12 Months)")
        months = np.arange(1, 13)
        monthly_savings = metrics.get('monthly_income', 0) - metrics.get('monthly_expenses', 0)
        projection = [metrics.get('net_worth', 0) + (monthly_savings * m) for m in months]
        fig_proj = px.line(x=months, y=projection, markers=True, labels={'x':'Month', 'y':'Net Worth'}, title="Wealth Growth Simulation")
        fig_proj.update_layout(yaxis_tickformat=",.0f")
        st.plotly_chart(fig_proj, width="stretch")

        st.subheader("Income vs Expenses vs Savings")
        cash_flow_df = FinanceCalculations.get_cash_flow_data(metrics, data)
        fig_cf = px.bar(cash_flow_df, x='Category', y='Amount', color='Category', 
                         color_discrete_sequence=['#2ECC71', '#E74C3C', '#3498DB'], text_auto='.2s')
        st.plotly_chart(fig_cf, width="stretch")

    with right_col:
        st.subheader("Asset Allocation (True Mix)")
        asset_df = FinanceCalculations.get_asset_allocation(metrics, data)
        fig_pie = px.pie(asset_df, values='Balance', names='Asset', hole=.4, color_discrete_sequence=px.colors.qualitative.T10)
        st.plotly_chart(fig_pie, width="stretch")

        st.subheader("Global Credit Health")
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

    st.divider()

    # --- Details Section ---
    tab1, tab2, tab3 = st.tabs(["📊 Bills and Trends", "🤝 Lendings & Loans", "🎯 Goals & Wishlist"])

    with tab1:
        st.subheader("Recurring Fixed Expenses")
        fixed_df = data.get('fixed_expenses', pd.DataFrame())
        if not fixed_df.empty: st.table(fixed_df)
        else: st.info("No fixed expenses tracked yet.")

        st.subheader("Total Bill & Payment Trends 📉")
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
            if selected_type != 'ALL': 
                plot_df = plot_df[plot_df['Type'] == selected_type]
            if selected_cats:
                plot_df = plot_df[plot_df['Category'].isin(selected_cats)]
            
            # --- THE CHRONOLOGICAL FIX ---
            # Use 'Date:T' (Temporal) with timeUnit 'yearmonth' to force calendar sorting
            chart = alt.Chart(plot_df).mark_bar(stroke='white', strokeWidth=0.5).encode(
                x=alt.X('yearmonth(Date):T', title='Month', axis=alt.Axis(format='%b %Y', labelAngle=-45)),
                y=alt.Y('Amount:Q', title='Amount (₹)'),
                color=alt.Color('Category:N', title='Bill/Card'),
                detail='ExactDate:N', # Keeps daily precision as slices
                tooltip=['ExactDate', 'Category', 'Amount', 'Type']
            ).properties(height=450).interactive()
            
            st.altair_chart(chart, use_container_width=True)
            st.info("💡 Each segment in the bar represents a specific transaction on a specific day.")
        else:
            st.info("No payment history found.")

    with tab2:
        col_l, col_r = st.columns(2)
        with col_l:
            st.subheader("Repayment Tracker (Lendings)")
            lend_df = data['lendings']
            show_active_lend = st.checkbox("Show Active Lendings Only", value=True)
            if show_active_lend and not lend_df.empty and 'isCleared' in lend_df.columns:
                lend_display = lend_df[lend_df['isCleared'] != 'Yes'].copy()
            else: lend_display = lend_df.copy()
            l_cols = ['Lent to', 'Amount Lent', 'Amount Due', 'Due Date', 'isCleared']
            st.dataframe(lend_display[[c for c in l_cols if c in lend_display.columns]], width="stretch")
            
            st.subheader("EMI Obligations")
            emi_df = data['emis']
            show_active_emi = st.checkbox("Show Active EMIs Only (IsClosed: No)", value=True)
            emi_display = emi_df.copy()
            if show_active_emi and not emi_display.empty and 'IsClosed' in emi_display.columns:
                emi_display = emi_display[emi_display['IsClosed'] == 'No']
            if not emi_display.empty and 'Actual Owner' in emi_display.columns:
                emi_display = emi_display[~emi_display['Actual Owner'].isin(EXCLUDED_OWNERS)]
            st.table(emi_display)

        with col_r:
            st.subheader("Money Owed (Loans)")
            loan_df = data['loans']
            loan_display = loan_df[(loan_df['Cleared'] == 'No') & (loan_df['own'] == 'Yes')].copy() if not loan_df.empty else loan_df
            st.dataframe(loan_display, width="stretch")

    with tab3:
        col_wl, col_forecast = st.columns([1.5, 1])
        with col_wl:
            st.subheader("Personal Wishlist")
            w_df = data['wishlist']
            show_unachieved = st.checkbox("Show Unachieved Only", value=True)
            w_display = w_df.copy()
            if show_unachieved and not w_display.empty:
                p_col = 'Purchased (Yes/No)' if 'Purchased (Yes/No)' in w_df.columns else 'Status'
                if p_col in w_display.columns: w_display = w_display[w_display[p_col].astype(str).str.lower() != 'yes']
            st.dataframe(w_display, width="stretch")

        with col_forecast:
            st.subheader("Financial Goal: Forecast")
            target = 400000
            current = metrics.get('total_savings', 0)
            progress = min(current/target, 1.0)
            st.write(f"**Goal: Emergency Fund (₹{target:,.0f})**")
            st.progress(progress)
            st.write(f"Status: {progress*100:.1f}% Complete")
            st.success(f"**Time to Goal:** {FinanceCalculations.get_goal_forecast(metrics, target)}")

if __name__ == "__main__":
    main()
