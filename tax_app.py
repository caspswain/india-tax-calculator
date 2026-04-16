import streamlit as st
import pandas as pd

# ==========================================
# PROFESSIONAL TAX CONFIGURATION (FY 2026-27 Projected)
# ==========================================
TAX_CONFIG = {
    "NEW_REGIME": {
        "standard_deduction": 75000,
        "rebate_limit": 700000,
        "slabs": [
            (300000, 0.00), (600000, 0.05), (900000, 0.10), 
            (1200000, 0.15), (1500000, 0.20), (float('inf'), 0.30)
        ]
    },
    "OLD_REGIME": {
        "standard_deduction": 50000,
        "rebate_limit": 500000,
        "slabs": [
            (250000, 0.00), (500000, 0.05), (1000000, 0.20), (float('inf'), 0.30)
        ]
    },
    "CESS_RATE": 0.04 
}

def calculate_tax_amount(taxable_income, config_key):
    config = TAX_CONFIG[config_key]
    if taxable_income <= config["rebate_limit"]:
        return 0.0
    tax = 0
    prev_limit = 0
    for limit, rate in config["slabs"]:
        if taxable_income > prev_limit:
            taxable_in_slab = min(taxable_income, limit) - prev_limit
            tax += taxable_in_slab * rate
            prev_limit = limit
        else: break
    return tax

# ==========================================
# UI DESIGN
# ==========================================
st.set_page_config(page_title="Pro India Tax Calc 26-27", layout="wide", page_icon="🏛️")

st.title("🏛️ Professional Income Tax Calculator")
st.markdown("### Financial Year 2026-27 (Assessment Year 2027-28)")
st.info("This calculator covers all 5 heads of income and detailed deductions for a comprehensive comparison.")

# Create Tabs for the 5 Heads of Income
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📋 Salary", "🏠 House Property", "💼 Business/Prof", "📈 Capital Gains", "💰 Other Sources", "📉 Deductions"
])

# --- TAB 1: SALARY ---
with tab1:
    st.header("Salary Income")
    col1, col2 = st.columns(2)
    with col1:
        basic_salary = st.number_input("Annual Basic Salary (₹)", min_value=0, value=0)
        hra = st.number_input("House Rent Allowance (HRA) (₹)", min_value=0, value=0)
    with col2:
        bonus = st.number_input("Annual Bonus/Incentives (₹)", min_value=0, value=0)
        other_allowances = st.number_input("Other Allowances (₹)", min_value=0, value=0)
    total_salary_gross = basic_salary + hra + bonus + other_allowances

# --- TAB 2: HOUSE PROPERTY ---
with tab2:
    st.header("Income from House Property")
    rental_income = st.number_input("Annual Rental Income Received (₹)", min_value=0, value=0)
    municipal_taxes = st.number_input("Municipal Taxes Paid (₹)", min_value=0, value=0)
    home_loan_int = st.number_input("Interest on Home Loan (Section 24b) (₹)", min_value=0, value=0)
    # Net House Property = (Rental - Taxes) - Interest
    house_property_income = max(0, (rental_income - municipal_taxes) - home_loan_int)
    # Note: If it's a loss, it can be offset against salary. For this app, we'll keep it simple.
    st.write(f"**Net House Property Income: ₹{house_property_income:,.0f}**")

# --- TAB 3: BUSINESS/PROFESSION ---
with tab3:
    st.header("Business or Professional Income")
    biz_income = st.number_input("Net Profit from Business/Freelancing (₹)", min_value=0, value=0)
    biz_expenses = st.number_input("Allowable Business Expenses (₹)", min_value=0, value=0)
    net_biz_income = max(0, biz_income - biz_expenses)

# --- TAB 4: CAPITAL GAINS ---
with tab4:
    st.header("Capital Gains")
    stcg = st.number_input("Short Term Capital Gains (STCG) (₹)", min_value=0, value=0)
    ltcg = st.number_input("Long Term Capital Gains (LTCG) (₹)", min_value=0, value=0)
    total_cap_gains = stcg + ltcg

# --- TAB 5: OTHER SOURCES ---
with tab5:
    st.header("Income from Other Sources")
    bank_interest = st.number_input("Interest from Savings/FD (₹)", min_value=0, value=0)
    dividends = st.number_input("Dividend Income (₹)", min_value=0, value=0)
    other_misc = st.number_input("Other Miscellaneous Income (₹)", min_value=0, value=0)
    total_other_income = bank_interest + dividends + other_misc

# --- TAB 6: DEDUCTIONS (OLD REGIME ONLY) ---
with tab6:
    st.header("Deductions (Applicable only for Old Regime)")
    st.warning("These deductions are ignored in the New Regime.")
    
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        sec_80c = st.number_input("Section 80C (PPF, ELSS, LIC - Max 1.5L)", min_value=0, value=0)
        sec_80d = st.number_input("Section 80D (Medical Insurance - Self/Parents)", min_value=0, value=0)
        sec_80ccd = st.number_input("Section 80CCD(1B) (Additional NPS - Max 50k)", min_value=0, value=0)
    with col_d2:
        sec_80g = st.number_input("Section 80G (Donations)", min_value=0, value=0)
        sec_80tta = st.number_input("Section 80TTA (Savings Int. - Max 10k)", min_value=0, value=0)
        other_deductions = st.number_input("Other Exemptions/Deductions (₹)", min_value=0, value=0)
    
    total_old_deductions = min(sec_80c, 150000) + sec_80d + min(sec_80ccd, 50000) + sec_80g + min(sec_80tta, 10000) + other_deductions

# ==========================================
# FINAL CALCULATIONS
# ==========================================

gross_total_income = total_salary_gross + house_property_income + net_biz_income + total_cap_gains + total_other_income

# NEW REGIME Calculation
new_taxable = max(0, gross_total_income - TAX_CONFIG["NEW_REGIME"]["standard_deduction"])
new_base_tax = calculate_tax_amount(new_taxable, "NEW_REGIME")
new_total_tax = new_base_tax + (new_base_tax * TAX_CONFIG["CESS_RATE"])

# OLD REGIME Calculation
old_taxable = max(0, gross_total_income - total_old_deductions - TAX_CONFIG["OLD_REGIME"]["standard_deduction"])
old_base_tax = calculate_tax_amount(old_taxable, "OLD_REGIME")
old_total_tax = old_base_tax + (old_base_tax * TAX_CONFIG["CESS_RATE"])

# ==========================================
# FINAL DASHBOARD
# ==========================================
st.divider()
st.header("📊 Final Tax Comparison")

res_col1, res_col2, res_col3 = st.columns(3)

with res_col1:
    st.metric("Gross Total Income", f"₹{gross_total_income:,.0f}")

with res_col2:
    st.markdown("### 🟦 New Regime")
    st.metric("Tax Payable", f"₹{new_total_tax:,.0f}")
    st.write(f"Net Taxable Income: ₹{new_taxable:,.0f}")

with res_col3:
    st.markdown("### 🟧 Old Regime")
    st.metric("Tax Payable", f"₹{old_total_tax:,.0f}")
    st.write(f"Net Taxable Income: ₹{old_taxable:,.0f}")

if new_total_tax < old_total_tax:
    st.success(f"🚀 **Recommendation:** The **New Regime** is better. You save **₹{old_total_tax - new_total_tax:,.0f}**")
else:
    st.success(f"🚀 **Recommendation:** The **Old Regime** is better. You save **₹{new_total_tax - old_total_tax:,.0f}**")

# Detailed Table
st.markdown("### 🔍 Detailed Breakdown")
summary_data = {
    "Particulars": ["Gross Total Income", "Total Deductions", "Taxable Income", "Base Tax", "Cess (4%)", "Total Tax"],
    "New Regime": [gross_total_income, TAX_CONFIG["NEW_REGIME"]["standard_deduction"], new_taxable, new_base_tax, new_base_tax * TAX_CONFIG["CESS_RATE"], new_total_tax],
    "Old Regime": [gross_total_income, total_old_deductions + TAX_CONFIG["OLD_REGIME"]["standard_deduction"], old_taxable, old_base_tax, old_base_tax * TAX_CONFIG["CESS_RATE"], old_total_tax]
}
st.table(pd.DataFrame(summary_data))
