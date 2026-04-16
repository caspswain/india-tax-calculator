import streamlit as st
import pandas as pd

# ==========================================
# CONFIGURATION (FY 2026-27 Projected)
# ==========================================
TAX_CONFIG = {
    "NEW_REGIME": {
        "std_deduction": 75000,
        "rebate_limit": 700000,
        "slabs": [
            (300000, 0.00), (600000, 0.05), (900000, 0.10), 
            (1200000, 0.15), (1500000, 0.20), (float('inf'), 0.30)
        ]
    },
    "OLD_REGIME": {
        "std_deduction": 50000,
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
        return 0.0, "Rebate Applied (Section 87A)"
    
    tax = 0
    prev_limit = 0
    breakdown_text = ""
    
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
# UI SETUP
# ==========================================
st.set_page_config(page_title="India Tax Pro 26-27 | SPCA & Co", layout="wide")

# Custom CSS for branding and professional look
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; font-weight: bold; }
    .firm-credit { 
        text-align: center; 
        padding: 20px; 
        margin-top: 50px; 
        border-top: 1px solid #ddd; 
        color: #555; 
        font-size: 14px; 
    }
    .firm-link { 
        color: #007bff; 
        text-decoration: none; 
        font-weight: bold; 
    }
    </style>
    """, unsafe_allow_html=True)

# --- HEADER BRANDING ---
st.title("🏛️ India Income Tax Professional Engine")
st.markdown(
    "<div style='text-align: center; color: #666; font-style: italic; margin-bottom: 20px;'>"
    "Developed by <b>S P C A & Co, Chartered Accountants, Bhubaneswar</b><br>"
    "<a href='http://www.caspca.net' target='_blank' style='color: #007bff; text-decoration: none; font-weight: bold;'>Visit www.caspca.net</a>"
    "</div>", 
    unsafe_allow_html=True
)

st.markdown("#### Financial Year 2026-27 | Assessment Year 2027-28")
st.write("Complete all sections below, then click **'Calculate Tax'** to generate your computation sheet.")

# ==========================================
# INPUT SECTION
# ==========================================
with st.expander("📁 Step 1: Enter Income & Deduction Details", expanded=True):
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📋 Salary", "🏠 House Property", "💼 Business", "📈 Capital Gains", "💰 Other Sources", "📉 Deductions"
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

# ==========================================
# CALCULATION TRIGGER
# ==========================================
st.markdown("---")
calculate_btn = st.button("🚀 CALCULATE TAX NOW")

if calculate_btn:
    salary_total = basic + hra + bonus + other_allow
    house_total = max(0, (rent_rec - m_tax) - loan_int)
    biz_total = max(0, biz_rev - biz_exp)
    cap_total = stcg + ltcg
    other_total = int_inc + misc_inc
    
    gti = salary_total + house_total + biz_total + cap_total + other_total
    old_deductions = min(s80c, 150000) + s80d + min(s80ccd, 50000) + s80g
    
    new_taxable = max(0, gti - TAX_CONFIG["NEW_REGIME"]["std_deduction"])
    old_taxable = max(0, gti - old_deductions - TAX_CONFIG["OLD_REGIME"]["std_deduction"])

    new_base_tax, new_breakdown = calculate_tax_amount(new_taxable, "NEW_REGIME")
    old_base_tax, old_breakdown = calculate_tax_amount(old_taxable, "OLD_REGIME")

    new_total = new_base_tax + (new_base_tax * TAX_CONFIG["CESS_RATE"])
    old_total = old_base_tax + (old_base_tax * TAX_CONFIG["CESS_RATE"])

    # --- OUTPUT PHASE ---
    st.header("📊 Tax Computation Sheet")
    
    with st.expander("🔍 Step 1: Gross Total Income (GTI) Breakdown", expanded=True):
        gti_data = {
            "Income Head": ["Salary", "House Property", "Business/Prof", "Capital Gains", "Other Sources"],
            "Amount (₹)": [salary_total, house_total, biz_total, cap_total, other_total]
        }
        st.table(pd.DataFrame(gti_data))
        st.markdown(f"**Total Gross Income: ₹{gti:,.0f}**")

    st.subheader("🛠️ The Calculation Process")
    col_n, col_o = st.columns(2)

    with col_n:
        st.markdown("### 🟦 New Regime Journey")
        st.info(f"Gross Income: ₹{gti:,.0f}")
        st.write(f"(-) Standard Deduction: ₹{TAX_CONFIG['NEW_REGIME']['std_deduction']:,.0f}")
        st.markdown(f"**→ Net Taxable Income: ₹{new_taxable:,.0f}**")
        st.markdown("---")
        st.write("**Slab Breakdown:**")
        st.code(new_breakdown)
        st.write(f"Base Tax: ₹{new_base_tax:,.0f}")
        st.write(f"Cess (4%): ₹{new_base_tax * TAX_CONFIG['CESS_RATE']:,.0f}")
        st.metric("Final Tax Payable", f"₹{new_total:,.0f}")

    with col_o:
        st.markdown("### 🟧 Old Regime Journey")
        st.info(f"Gross Income: ₹{gti:,.0f}")
        st.write(f"(-) Section 80 Deductions: ₹{old_deductions:,.0f}")
        st.write(f"(-) Standard Deduction: ₹{TAX_CONFIG['OLD_REGIME']['std_deduction']:,.0f}")
        st.markdown(f"**→ Net Taxable Income: ₹{old_taxable:,.0f}**")
        st.markdown("---")
        st.write("**Slab Breakdown:**")
        st.code(old_breakdown)
        st.write(f"Base Tax: ₹{old_base_tax:,.0f}")
        st.write(f"Cess (4%): ₹{old_base_tax * TAX_CONFIG['CESS_RATE']:,.0f}")
        st.metric("Final Tax Payable", f"₹{old_total:,.0f}")

    st.divider()
    st.subheader("🏆 Final Verdict")
    if new_total < old_total:
        st.success(f"The **New Regime** is optimal. You save **₹{old_total - new_total:,.0f}** compared to the Old Regime.")
    else:
        st.success(f"The **Old Regime** is optimal. You save **₹{new_total - old_total:,.0f}** compared to the New Regime.")

# ==========================================
# FOOTER BRANDING
# ==========================================
st.markdown(f"""
    <div class="firm-credit">
        Created by <b>S P C A & Co, Chartered Accountants, Bhubaneswar</b><br>
        Official Website: <a href='http://www.caspca.net' target='_blank' class='firm-link'>www.caspca.net</a>
    </div>
    """, unsafe_allow_html=True)
