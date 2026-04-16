import streamlit as st
import pandas as pd
from datetime import date, datetime

# =============================================================================
# MULTI-YEAR TAX DATABASE
# Update these values as budgets are announced
# =============================================================================
TAX_DATABASE = {
    "FY 2025-26": {
        "NEW_REGIME": {
            "std_deduction": 75000,
            "rebate_limit": 700000,
            "slabs": [(300000, 0.00), (600000, 0.05), (900000, 0.10), (1200000, 0.15), (1500000, 0.20), (float('inf'), 0.30)]
        },
        "OLD_REGIME": {
            "std_deduction": 50000,
            "rebate_limit": 500000,
            "slabs": [(250000, 0.00), (500000, 0.05), (1000000, 0.20), (float('inf'), 0.30)]
        }
    },
    "FY 2026-27": {
        "NEW_REGIME": {
            "std_deduction": 75000, # Projected
            "rebate_limit": 700000, # Projected
            "slabs": [(300000, 0.00), (600000, 0.05), (900000, 0.10), (1200000, 0.15), (1500000, 0.20), (float('inf'), 0.30)]
        },
        "OLD_REGIME": {
            "std_deduction": 50000,
            "rebate_limit": 500000,
            "slabs": [(250000, 0.00), (500000, 0.05), (1000000, 0.20), (float('inf'), 0.30)]
        }
    }
}

CESS_RATE = 0.04 

def calculate_tax_amount(taxable_income, year, regime):
    config = TAX_DATABASE[year][regime]
    if taxable_income <= config["rebate_limit"]:
        return 0.0, "Rebate Applied (Section 87A)"
    
    tax, prev_limit, breakdown_text = 0, 0, ""
    for limit, rate in config["slabs"]:
        if taxable_income > prev_limit:
            taxable_in_slab = min(taxable_income, limit) - prev_limit
            slab_tax = taxable_in_slab * rate
            tax += slab_tax
            breakdown_text += f"₹{prev_limit:,.0f} to ₹{limit:,.0f} @ {rate*100}%: ₹{slab_tax:,.0f}\n"
            prev_limit = limit
        else: break
    return tax, breakdown_text

# ==========================================
# UI SETUP & BRANDING
# ==========================================
st.set_page_config(page_title="Tax Computation | SPCA & Co", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #1e3a8a; color: white; font-weight: bold; }
    .firm-credit { text-align: center; padding: 20px; margin-top: 50px; border-top: 1px solid #ddd; color: #555; font-size: 14px; }
    .firm-link { color: #007bff; text-decoration: none; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏛️ Professional Tax Computation Statement")
st.markdown(
    "<div style='text-align: center; color: #666; font-style: italic; margin-bottom: 20px;'>"
    "Developed by <b>S P C A & Co, Chartered Accountants, Bhubaneswar</b><br>"
    "<a href='http://www.caspca.net' target='_blank' style='color: #007bff; text-decoration: none; font-weight: bold;'>Visit www.caspca.net</a>"
    "</div>", 
    unsafe_allow_html=True
)

# --- YEAR SELECTION ---
st.markdown("### 📅 Select Assessment Period")
selected_year = st.selectbox("Choose Financial Year (FY):", options=list(TAX_DATABASE.keys()), index=0)
st.info(f"You are currently calculating taxes for **{selected_year}**.")

# ==========================================
# INPUT SECTION
# ==========================================
with st.expander("📁 Step 1: Income, Deductions & Tax Payments", expanded=True):
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📋 Salary", "🏠 Property", "💼 Business", "📈 Capital Gains", "💰 Other", "📉 Deductions", "💳 Tax Paid"
    ])

    with tab1:
        st.subheader("Salary Income")
        col1, col2 = st.columns(2)
        with col1:
            basic = st.number_input("Annual Basic Salary (₹)", min_value=0, value=0)
            hra = st.number_input("HRA (₹)", min_value=0, value=0)
        with col2:
            bonus = st.number_input("Annual Bonus (₹)", min_value=0, value=0)
            other_allow = st.number_input("Other Allowances (₹)", min_value=0, value=0)

    with tab2:
        st.subheader("House Property")
        rent_rec = st.number_input("Annual Rent Received (₹)", min_value=0, value=0)
        m_tax = st.number_input("Municipal Taxes Paid (₹)", min_value=0, value=0)
        loan_int = st.number_input("Home Loan Interest (Sec 24b) (₹)", min_value=0, value=0)

    with tab3:
        st.subheader("Business / Profession")
        biz_rev = st.number_input("Gross Business Receipts (₹)", min_value=0, value=0)
        biz_exp = st.number_input("Allowable Business Expenses (₹)", min_value=0, value=0)

    with tab4:
        st.subheader("Capital Gains")
        stcg = st.number_input("Short Term Capital Gains (₹)", min_value=0, value=0)
        ltcg = st.number_input("Long Term Capital Gains (₹)", min_value=0, value=0)

    with tab5:
        st.subheader("Other Sources")
        int_inc = st.number_input("Bank Interest/Dividends (₹)", min_value=0, value=0)
        misc_inc = st.number_input("Other Misc Income (₹)", min_value=0, value=0)

    with tab6:
        st.subheader("Deductions (Old Regime Only)")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            s80c = st.number_input("Section 80C (Max 1.5L) (₹)", min_value=0, value=0)
            s80d = st.number_input("Section 80D (Medical) (₹)", min_value=0, value=0)
        with col_d2:
            s80ccd = st.number_input("Section 80CCD(1B) (NPS Max 50k) (₹)", min_value=0, value=0)
            s80g = st.number_input("Section 80G (Donations) (₹)", min_value=0, value=0)

    with tab7:
        st.subheader("Taxes Paid & Filing Details")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            tds_paid = st.number_input("TDS Deducted (₹)", min_value=0, value=0)
            advance_tax = st.number_input("Advance Tax Paid (₹)", min_value=0, value=0)
        with col_t2:
            self_assessment = st.number_input("Self Assessment Tax Paid (₹)", min_value=0, value=0)
            filing_date = st.date_input("Expected Date of Filing Return", value=date.today())

# ==========================================
# CALCULATION TRIGGER
# ==========================================
st.markdown("---")
calculate_btn = st.button("🚀 GENERATE COMPUTATION SHEET")

if calculate_btn:
    # 1. GROSS TOTAL INCOME (GTI)
    salary_total = basic + hra + bonus + other_allow
    house_total = max(0, (rent_rec - m_tax) - loan_int)
    biz_total = max(0, biz_rev - biz_exp)
    cap_total = stcg + ltcg
    other_total = int_inc + misc_inc
    gti = salary_total + house_total + biz_total + cap_total + other_total
    
    # 2. REGIME CALCULATIONS based on Selected Year
    old_deductions = min(s80c, 150000) + s80d + min(s80ccd, 50000) + s80g
    
    # New Regime for Selected Year
    new_taxable = max(0, gti - TAX_DATABASE[selected_year]["NEW_REGIME"]["std_deduction"])
    new_base_tax, new_breakdown = calculate_tax_amount(new_taxable, selected_year, "NEW_REGIME")
    new_total_tax = new_base_tax + (new_base_tax * CESS_RATE)
    
    # Old Regime for Selected Year
    old_taxable = max(0, gti - old_deductions - TAX_DATABASE[selected_year]["OLD_REGIME"]["std_deduction"])
    old_base_tax, old_breakdown = calculate_tax_amount(old_taxable, selected_year, "OLD_REGIME")
    old_total_tax = old_base_tax + (old_base_tax * CESS_RATE)

    # Optimal Regime
    final_tax_liability = min(new_total_tax, old_total_tax)
    chosen_regime = "New Regime" if new_total_tax < old_total_tax else "Old Regime"

    # 3. TAX PAID & INTEREST (Section 234)
    total_tax_paid = tds_paid + advance_tax + self_assessment
    net_tax_shortfall = max(0, final_tax_liability - total_tax_paid)
    
    due_date = date(filing_date.year, 7, 31)
    int_234a = 0
    if filing_date > due_date:
        months_delay = (filing_date.year - due_date.year) * 12 + (filing_date.month - due_date.month)
        int_234a = net_tax_shortfall * 0.01 * max(1, months_delay)

    int_234b = 0
    if advance_tax < (0.9 * final_tax_liability):
        int_234b = net_tax_shortfall * 0.01 * 6 
    
    total_interest = int_234a + int_234b
    final_payable = net_tax_shortfall + total_interest
    final_refund = max(0, total_tax_paid - final_tax_liability - total_interest)

    # ==========================================
    # OUTPUT PHASE
    # ==========================================
    st.header(f"📊 Tax Computation Sheet - {selected_year}")
    
    summary_df = pd.DataFrame({
        "Description": ["Gross Total Income", "Total Deductions (Optimal)", "Net Taxable Income", "Total Tax Liability (incl. Cess)", "Less: TDS/Advance/Self-Tax", "Add: Interest u/s 234A/B", "Net Amount Payable / (Refund)"],
        "Amount (₹)": [gti, (gti - (new_taxable if chosen_regime == "New Regime" else old_taxable)), (new_taxable if chosen_regime == "New Regime" else old_taxable), final_tax_liability, total_tax_paid, total_interest, (final_payable if final_payable > 0 else -final_refund)]
    })
    st.table(summary_df)

    col_n, col_o = st.columns(2)
    with col_n:
        st.markdown(f"### 🟦 New Regime ({selected_year})")
        st.info(f"Taxable Income: ₹{new_taxable:,.0f}")
        st.code(new_breakdown)
        st.metric("Liability", f"₹{new_total_tax:,.0f}")

    with col_o:
        st.markdown(f"### 🟧 Old Regime ({selected_year})")
        st.info(f"Taxable Income: ₹{old_taxable:,.0f}")
        st.code(old_breakdown)
        st.metric("Liability", f"₹{old_total_tax:,.0f}")

    st.divider()
    if final_payable > 0:
        st.error(f"### 🚩 Final Tax Payable: ₹{final_payable:,.0f}")
    else:
        st.success(f"### 💰 Estimated Tax Refund: ₹{final_refund:,.0f}")

# ==========================================
# FOOTER
# ==========================================
st.markdown(f"""
    <div class="firm-credit">
        Created by <b>S P C A & Co, Chartered Accountants, Bhubaneswar</b><br>
        Official Website: <a href='http://www.caspca.net' target='_blank' class='firm-link'>www.caspca.net</a>
    </div>
    """, unsafe_allow_html=True)
