import streamlit as st
import pandas as pd

# ==========================================
# TAX CONFIGURATION (Same logic as before)
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
    previous_slab_limit = 0
    for limit, rate in config["slabs"]:
        if taxable_income > previous_slab_limit:
            taxable_in_this_slab = min(taxable_income, limit) - previous_slab_limit
            tax += taxable_in_this_slab * rate
            previous_slab_limit = limit
        else:
            break
    return tax

# ==========================================
# STREAMLIT UI DESIGN
# ==========================================
st.set_page_config(page_title="India Tax Calc 26-27", page_icon="💰")

st.title("🇮🇳 Income Tax Calculator")
st.subheader("Projected for Tax Year 2026-27")

# Sidebar for Inputs
st.sidebar.header("💰 Income Details")
gross_salary = st.sidebar.number_input("Annual Gross Salary (₹)", min_value=0, value=1000000, step=10000)
other_income = st.sidebar.number_input("Other Income (Interest, Rental) (₹)", min_value=0, value=0, step=1000)

st.sidebar.header("📉 Deductions (Old Regime)")
sec_80c = st.sidebar.number_input("Section 80C (Max 1.5L) (₹)", min_value=0, value=150000)
sec_80d = st.sidebar.number_input("Section 80D (Health Insurance) (₹)", min_value=0, value=25000)
hra_home_loan = st.sidebar.number_input("HRA / Home Loan Interest (₹)", min_value=0, value=0)

# Calculation Logic
total_income = gross_salary + other_income

# New Regime Calc
new_taxable = max(0, total_income - TAX_CONFIG["NEW_REGIME"]["standard_deduction"])
new_base_tax = calculate_tax_amount(new_taxable, "NEW_REGIME")
new_total_tax = new_base_tax + (new_base_tax * TAX_CONFIG["CESS_RATE"])

# Old Regime Calc
old_deductions = sec_80c + sec_80d + hra_home_loan + TAX_CONFIG["OLD_REGIME"]["standard_deduction"]
old_taxable = max(0, total_income - old_deductions)
old_base_tax = calculate_tax_amount(old_taxable, "OLD_REGIME")
old_total_tax = old_base_tax + (old_base_tax * TAX_CONFIG["CESS_RATE"])

# --- DISPLAY RESULTS ---
col1, col2 = st.columns(2)

with col1:
    st.markdown("### 🟦 New Regime")
    st.metric("Total Tax Payable", f"₹{new_total_tax:,.0f}")
    st.write(f"Taxable Income: ₹{new_taxable:,.0f}")
    st.write(f"Monthly Take-home: ₹{(total_income-new_total_tax)/12:,.0f}")

with col2:
    st.markdown("### 🟧 Old Regime")
    st.metric("Total Tax Payable", f"₹{old_total_tax:,.0f}")
    st.write(f"Taxable Income: ₹{old_taxable:,.0f}")
    st.write(f"Monthly Take-home: ₹{(total_income-old_total_tax)/12:,.0f}")

st.divider()

# Recommendation
if new_total_tax < old_total_tax:
    st.success(f"✅ Recommendation: **New Regime** saves you ₹{old_total_tax - new_total_tax:,.0f}")
else:
    st.success(f"✅ Recommendation: **Old Regime** saves you ₹{new_total_tax - old_total_tax:,.0f}")

# Show detailed table
st.markdown("### Detailed Breakdown")
data = {
    "Metric": ["Taxable Income", "Base Tax", "Total Tax (incl. Cess)", "Monthly Take-home"],
    "New Regime": [new_taxable, new_base_tax, new_total_tax, (total_income-new_total_tax)/12],
    "Old Regime": [old_taxable, old_base_tax, old_total_tax, (total_income-old_total_tax)/12]
}
st.table(pd.DataFrame(data))
