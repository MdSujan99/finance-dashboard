import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from data_loader import DataLoader
from calculations import FinanceCalculations, EXCLUDED_OWNERS

# --- Config & Style ---
st.set_page_config(page_title="Personal Finance Dashboard", layout="wide")

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
    st.subheader("High-Level Summary")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Net Worth", f"₹{metrics['net_worth']:,.0f}")
    col2.metric("Monthly Income", f"₹{metrics['monthly_income']:,.0f}")
    col3.metric("Lent (Active)", f"₹{metrics['total_lent']:,.0f}")
    col4.metric("Loans Owed", f"₹{metrics['total_loan_owed']:,.0f}", delta_color="inverse")
    col5.metric("Savings", f"₹{metrics['total_savings']:,.0f}")

    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("Credit Used", f"₹{metrics['total_cc_used']:,.0f}", delta_color="inverse")
    m_col2.metric("Credit Limit", f"₹{metrics['total_cc_limit']:,.0f}")
    m_col3.metric("Utilization %", f"{metrics['util_pct']}%", delta_color="inverse")
    m_col4.metric("Cash Balance", f"₹{metrics['total_cash']:,.0f}")

    st.divider()

    # --- Charts Section ---
    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.subheader("Income vs Expenses vs Savings")
        cash_flow_df = FinanceCalculations.get_cash_flow_data(metrics, data)
        fig_cf = px.bar(cash_flow_df, x='Category', y='Amount', color='Category', 
                         color_discrete_sequence=['#2ECC71', '#E74C3C', '#3498DB'], text_auto='.2s')
        st.plotly_chart(fig_cf, width="stretch")

        st.subheader("Asset Allocation")
        nw_df = data['net_worth']
        if not nw_df.empty:
            fig_pie = px.pie(nw_df, values='Balance', names='Category', hole=.4,
                             color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_pie, width="stretch")

    with right_col:
        st.subheader("Global Credit Health")
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = metrics['util_pct'],
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': "#EF553B" if metrics['util_pct'] > 50 else "#00CC96"},
                'steps' : [
                    {'range': [0, 30], 'color': "rgba(46, 204, 113, 0.2)"},
                    {'range': [30, 70], 'color': "rgba(241, 196, 15, 0.2)"},
                    {'range': [70, 100], 'color': "rgba(231, 76, 60, 0.2)"}]
            }
        ))
        st.plotly_chart(fig_gauge, width="stretch")

        st.subheader("Credit Card Breakdown")
        cc_df = data['credit_cards']
        if not cc_df.empty:
            cc_df['Util %'] = (cc_df['Current Balance'] / cc_df['Max Limit'] * 100).round(1)
            display_cols = ['Card Provider', 'Current Balance', 'Max Limit', 'Util %']
            available_cols = [c for c in display_cols if c in cc_df.columns]
            st.dataframe(cc_df[available_cols], width="stretch")

    st.divider()

    # --- Detail Tables Section ---
    col_l, col_r = st.columns(2)
    
    with col_l:
        st.subheader("Repayment Tracker (Lendings)")
        lend_df = data['lendings']
        show_active_lend = st.checkbox("Show Active Lendings Only", value=True, key="lend_filter")
        if show_active_lend and not lend_df.empty and 'isCleared' in lend_df.columns:
            lend_display = lend_df[lend_df['isCleared'] != 'Yes'].copy()
        else:
            lend_display = lend_df.copy()
        l_cols = ['Lent to', 'Amount Lent', 'Due Date', 'isCleared']
        l_avail = [c for c in l_cols if c in lend_display.columns]
        st.dataframe(lend_display[l_avail], width="stretch")
        
        st.subheader("EMI Obligations")
        emi_df = data['emis']
        col_emi_f1, col_emi_f2 = st.columns(2)
        with col_emi_f1:
            show_active_emi = st.checkbox("Show Active EMIs Only", value=True, key="emi_filter")
        with col_emi_f2:
            exclude_others = st.checkbox("Exclude Non-Owned EMIs", value=True, key="emi_owner_filter")
        
        emi_display = emi_df.copy()
        if show_active_emi and not emi_display.empty:
            if 'IsClosed' in emi_display.columns:
                emi_display = emi_display[emi_display['IsClosed'] != 'Yes']
            if 'Amt Due' in emi_display.columns:
                emi_display = emi_display[emi_display['Amt Due'] > 0]
        
        if exclude_others and not emi_display.empty and 'Actual Owner' in emi_display.columns:
            # Use the code-defined list of owners to exclude
            emi_display = emi_display[~emi_display['Actual Owner'].isin(EXCLUDED_OWNERS)]

        e_cols = ['Provider', 'Amt Due', 'EMIs Remaining', 'Actual Owner', 'IsClosed']
        e_avail = [c for c in e_cols if c in emi_display.columns]
        st.table(emi_display[e_avail])

        st.subheader("Money Owed (Loans)")
        loan_df = data['loans']
        show_active_loan = st.checkbox("Show Active Loans Owed Only", value=True, key="loan_filter")
        if show_active_loan and not loan_df.empty:
            loan_display = loan_df[(loan_df['Cleared'] == 'No') & (loan_df['own'] == 'Yes')].copy()
        else:
            loan_display = loan_df.copy()
        loan_cols = ['Loaned From', 'Amount Due', 'Due Date', 'Cleared', 'own']
        loan_avail = [c for c in loan_cols if c in loan_display.columns]
        st.dataframe(loan_display[loan_avail], width="stretch")

    with col_r:
        st.subheader("Personal Wishlist (Goals)")
        w_df = data['wishlist']
        show_active_wish = st.checkbox("Show Unachieved Goals Only", value=True, key="wish_filter")
        if not w_df.empty:
            if show_active_wish:
                p_col = 'Purchased (Yes/No)' if 'Purchased (Yes/No)' in w_df.columns else ('Status' if 'Status' in w_df.columns else None)
                if p_col:
                    w_display = w_df[w_df[p_col].astype(str).str.lower() != 'yes'].copy()
                else:
                    w_display = w_df.copy()
            else:
                w_display = w_df.copy()
            if 'Priority' in w_display.columns:
                w_display.loc[:, 'Priority'] = w_display['Priority'].astype(str)
            w_cols = ['Item Name', 'Priority', 'Budget', 'Purchased (Yes/No)']
            w_avail = [c for c in w_cols if c in w_display.columns]
            st.dataframe(w_display[w_avail], width="stretch")
        else:
            st.info("Wishlist is empty.")

        st.subheader("Financial Goals: Progress")
        target = 400000
        current = metrics['total_savings']
        progress = min(current/target, 1.0)
        st.write(f"**Goal: Emergency Fund (₹{target:,.0f})**")
        st.progress(progress)
        st.write(f"Status: {progress*100:.1f}% Complete")

if __name__ == "__main__":
    main()
