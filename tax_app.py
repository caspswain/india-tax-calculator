import streamlit as st
import pandas as pd
from datetime import date
from fpdf import FPDF # This uses fpdf2

# =============================================================================
# CONFIGURATION & DATABASE
# =============================================================================
TAX_DATABASE = {
    "FY 2025-26": {
        "NEW_REGIME": {"std_deduction": 75000, "rebate_limit": 700000, "slabs": [(300000, 0.00), (600000, 0.05), (900000, 0.10), (1200000, 0.15), (1500000, 0.20), (float('inf'), 0.30)]},
        "OLD_REGIME": {"std_deduction": 50000, "rebate_limit": 500000, "slabs": [(250000, 0.00), (500000, 0.05), (1000000, 0.20), (float('inf'), 0.30)]}
    },
    "FY 2026-27": {
        "NEW_REGIME": {"std_deduction": 75000, "rebate_limit": 700000, "slabs": [(300000, 0.00), (600000, 0.05), (900000, 0.10), (1200000, 0.15), (1500000, 0.20), (float('inf'), 0.30)]},
        "OLD_REGIME": {"std_deduction": 50000, "rebate_limit": 500000, "slabs": [(250000, 0.00), (500000, 0.05), (1000000, 0.20), (float('inf'), 0.30)]}
    }
}
CESS_RATE = 0.04 

# --- EXEMPTION CALCULATORS ---
def calc_hra(actual, basic, rent, city):
    if rent == 0: return 0, "No rent paid"
    p = 0.5 if city == "Metro" else 0.4
    l1, l2, l3 = actual, rent - (0.1 * basic), p * basic
    exemp = max(0, min(l1, l2, l3))
    logic = f"Min of: Actual({l1:,.0f}), Rent-10%Basic({l2:,.0f}), {p*100}% Basic({l3:,.0f})"
    return exemp, logic

def calc_gratuity(received, years, last_sal):
    limit = (15/26) * last_sal * years
    exemp = min(received, limit, 2000000)
    logic = f"Min of: Received({received:,.0f}), Formula({limit:,.0f}), Cap(20L)"
    return exemp, logic

def calc_pension(commuted_amt, full_pension, percent):
    exemp = commuted_amt * (percent/100)
    logic = f"Commuted {percent}% of total pension"
    return exemp, logic

def calculate_slab_tax(taxable_income, year, regime):
    config = TAX_DATABASE[year][regime]
    if taxable_income <= config["rebate_limit"]: return 0.0, "Rebate Applied (Sec 87A)"
    tax, prev_limit, breakdown = 0, 0, ""
    for limit, rate in config["slabs"]:
        if taxable_income > prev_limit:
            taxable_in_slab = min(taxable_income, limit) - prev_limit
            slab_tax = taxable_in_slab * rate
            tax += slab_tax
            breakdown += f"₹{prev_limit:,.0f}-₹{limit:,.0f} @ {rate*100}%: ₹{slab_tax:,.0f}\n"
            prev_limit = limit
        else: break
    return tax, breakdown

# ==========================================
# UI & BRANDING
# ==========================================
st.set_page_config(page_title="S P C A & Co | Income Tax Calculator", layout="wide")
st.markdown("""<style>.main { background-color: #f5f7f9; } .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #1e3a8a; color: white; font-weight: bold; }</style>""", unsafe_allow_html=True)

# Updated Header as requested
st.title("🏛️ Income Tax Calculator")
st.markdown("<div style='text-align: center; color: #666; font-style: italic;'>Developed by <b>S P C A & Co, Chartered Accountants, Bhubaneswar</b><br><a href='http://www.caspca.net' target='_blank' style='color: #007bff;'>www.caspca.net</a></div>", unsafe_allow_html=True)

with st.sidebar:
    st.header("👤 Client Profile")
    u_name = st.text_input("Client Full Name", value="John Doe")
    u_pan = st.text_input("PAN Number", value="ABCDE1234F")
    selected_year = st.selectbox("Financial Year (FY):", options=list(TAX_DATABASE.keys()))

with st.expander("📁 DETAILED INCOME & EXEMPTION INPUTS", expanded=True):
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["📋 Salary", "🏠 Property", "💼 Business", "📈 Gains", "💰 Other Sources", "📉 Deductions", "💳 Tax Paid"])

    with tab1:
        st.subheader("Salary & Exemption Calculators")
        with st.container(border=True):
            st.markdown("**🏠 HRA Exemption Calculator**")
            c1, c2, c3, c4 = st.columns(4)
            basic = c1.number_input("Basic Salary (₹)", min_value=0, value=0)
            actual_hra = c2.number_input("HRA Received (₹)", min_value=0, value=0)
            rent_paid = c3.number_input("Rent Paid (₹)", min_value=0, value=0)
            city = c4.selectbox("City", ["Non-Metro", "Metro"])
        with st.container(border=True):
            st.markdown("**🎁 Gratuity Exemption Calculator**")
            c1, c2, c3 = st.columns(3)
            gratuity_rec = c1.number_input("Gratuity Received (₹)", min_value=0, value=0)
            g_years = c2.number_input("Years of Service", min_value=0, value=0)
            g_last_sal = c3.number_input("Last Drawn Salary (₹)", min_value=0, value=0)
        with st.container(border=True):
            st.markdown("**👴 Commuted Pension Calculator**")
            c1, c2, c3 = st.columns(3)
            pension_rec = c1.number_input("Pension Amount Received (₹)", min_value=0, value=0)
            p_total = c2.number_input("Total Pension Amount (₹)", min_value=0, value=0)
            p_percent = c3.number_input("Commutation %", min_value=0, max_value=100, value=0)
        st.markdown("---")
        col_a, col_b = st.columns(2)
        bonus = col_a.number_input("Annual Bonus (₹)", min_value=0, value=0)
        other_allow = col_b.number_input("Other Allowances (₹)", min_value=0, value=0)

    with tab2:
        st.subheader("House Property")
        rent_rec = st.number_input("Annual Rent Received (₹)", min_value=0, value=0)
        m_tax = st.number_input("Municipal Taxes (₹)", min_value=0, value=0)
        loan_int = st.number_input("Interest on Home Loan (Sec 24b) (₹)", min_value=0, value=0)
    with tab3:
        st.subheader("Business / Profession")
        biz_rev = st.number_input("Gross Receipts (₹)", min_value=0, value=0)
        biz_exp = st.number_input("Business Expenses (₹)", min_value=0, value=0)
    with tab4:
        st.subheader("Capital Gains")
        stcg = st.number_input("Short Term Capital Gains (₹)", min_value=0, value=0)
        ltcg = st.number_input("Long Term Capital Gains (₹)", min_value=0, value=0)
    with tab5:
        st.subheader("Other Sources")
        col_o1, col_o2 = st.columns(2)
        with col_o1:
            st.markdown("**Slab Rate Income**")
            int_inc = st.number_input("Bank Interest/Dividends (₹)", min_value=0, value=0)
            misc_inc = st.number_input("Misc Income (₹)", min_value=0, value=0)
        with col_o2:
            st.markdown("**Special Rate Income (Flat 30%)**")
            crypto_inc = st.number_input("Crypto/VDA Income (₹)", min_value=0, value=0)
            lottery_inc = st.number_input("Lottery/Prize Money (₹)", min_value=0, value=0)
    with tab6:
        st.subheader("Deductions (Old Regime Only)")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            s80c = st.number_input("Section 80C (₹)", min_value=0, value=0)
            s80d = st.number_input("Section 80D (₹)", min_value=0, value=0)
        with col_d2:
            s80ccd = st.number_input("Section 80CCD(1B) (₹)", min_value=0, value=0)
            s80g = st.number_input("Section 80G (₹)", min_value=0, value=0)
    with tab7:
        st.subheader("Taxes Paid")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            tds_paid = st.number_input("TDS Deducted (₹)", min_value=0, value=0)
            advance_tax = st.number_input("Advance Tax Paid (₹)", min_value=0, value=0)
        with col_t2:
            self_assessment = st.number_input("Self Assessment Tax (₹)", min_value=0, value=0)
            filing_date = st.date_input("Filing Date", value=date.today())

# ==========================================
# ENGINE
# ==========================================
if st.button("🚀 GENERATE FINAL COMPUTATION"):
    hra_ex, hra_log = calc_hra(actual_hra, basic, rent_paid, city)
    gra_ex, gra_log = calc_gratuity(gratuity_rec, g_years, g_last_sal)
    pen_ex, pen_log = calc_pension(pension_rec, p_total, p_percent)
    
    salary_gross = basic + actual_hra + gratuity_rec + pension_rec + bonus + other_allow
    salary_taxable = salary_gross - (hra_ex + gra_ex + pen_ex)
    
    special_income = crypto_inc + lottery_inc
    total_slab_income = salary_taxable + max(0, (rent_rec-m_tax)-loan_int) + max(0, biz_rev-biz_exp) + stcg + ltcg + int_inc + misc_inc
    gti = total_slab_income + special_income
    
    old_ded = min(s80c, 150000) + s80d + min(s80ccd, 50000) + s80g
    new_tx_slab = max(0, total_slab_income - TAX_DATABASE[selected_year]["NEW_REGIME"]["std_deduction"])
    new_base, new_br = calculate_slab_tax(new_tx_slab, selected_year, "NEW_REGIME")
    
    old_tx_slab = max(0, total_slab_income - old_ded - TAX_DATABASE[selected_year]["OLD_REGIME"]["std_deduction"])
    old_base, old_br = calculate_slab_tax(old_tx_slab, selected_year, "OLD_REGIME")
    
    special_tax = special_income * 0.30
    new_total = (new_base + special_tax) * (1 + CESS_RATE)
    old_total = (old_base + special_tax) * (1 + CESS_RATE)
    
    final_tax = min(new_total, old_total)
    chosen = "New Regime" if new_total < old_total else "Old Regime"
    
    total_paid = tds_paid + advance_tax + self_assessment
    shortfall = max(0, final_tax - total_paid)
    
    due_date = date(filing_date.year, 7, 31)
    int_234 = 0
    if filing_date > due_date:
        months = (filing_date.year - due_date.year) * 12 + (filing_date.month - due_date.month)
        int_234 = shortfall * 0.01 * max(1, months)
    
    final_payable = shortfall + int_234
    final_refund = max(0, total_paid - final_tax - int_234)

    # --- OUTPUTS ---
    st.header(f"📊 Computation for {u_name} (PAN: {u_pan})")
    
    with st.expander("🔍 View Exemption Calculation Logic", expanded=True):
        st.write(f"**HRA:** ₹{hra_ex:,.0f} | {hra_log}")
        st.write(f"**Gratuity:** ₹{gra_ex:,.0f} | {gra_log}")
        st.write(f"**Pension:** ₹{pen_ex:,.0f} | {pen_log}")

    summary_data = {
        "Particulars": ["Gross Total Income", "Less: Exemptions (HRA/Gra/Pen)", "Net Slab Income", "Special Rate Income (30%)", "Less: Std Ded/80C", "Total Tax Liability (incl. Cess)", "Less: Taxes Paid", "Add: Sec 234 Interest", "Net Amount Payable/(Refund)"],
        "Amount (₹)": [gti, (hra_ex+gra_ex+pen_ex), total_slab_income, special_income, (total_slab_income - (new_tx_slab if chosen=="New Regime" else old_tx_slab)), final_tax, total_paid, int_234, (final_payable if final_payable > 0 else -final_refund)]
    }
    st.table(pd.DataFrame(summary_data))

    # --- FIXED PDF GENERATION ---
    def create_pdf():
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("helvetica", 'B', 16)
        pdf.cell(0, 10, "S P C A & Co, Chartered Accountants", ln=True, align='C')
        pdf.set_font("helvetica", '', 12)
        pdf.cell(0, 10, f"Income Tax Computation - {selected_year}", ln=True, align='C')
        pdf.ln(10)
        pdf.cell(0, 10, f"Client Name: {u_name}", ln=True)
        pdf.cell(0, 10, f"PAN: {u_pan}", ln=True)
        pdf.ln(5)
        pdf.set_font("helvetica", 'B', 12)
        pdf.cell(0, 10, "Computation Summary:", ln=True)
        pdf.set_font("helvetica", 'B', 10)
        pdf.cell(130, 10, "Particulars", 1)
        pdf.cell(40, 10, "Amount (INR)", 1, ln=True)
        pdf.set_font("helvetica", '', 10)
        for part, amt in zip(summary_data["Particulars"], summary_data["Amount (₹)"]):
            pdf.cell(130, 10, part, 1)
            pdf.cell(40, 10, f"{amt:,.0f}", 1, ln=True)
        
        # CRITICAL FIX: Explicitly cast the output to bytes
        return bytes(pdf.output()) 

    try:
        pdf_bytes = create_pdf()
        st.download_button(
            label="📄 Download Professional PDF Computation", 
            data=pdf_bytes, 
            file_name=f"{u_pan}_tax_comp.pdf", 
            mime="application/pdf"
        )
    except Exception as e:
        st.error(f"PDF generation failed: {e}")

st.markdown(f"<div class='firm-credit'>Created by <b>S P C A & Co, Chartered Accountants, Bhubaneswar</b><br>Official Website: <a href='http://www.caspca.net' target='_blank' class='firm-link'>www.caspca.net</a></div>", unsafe_allow_html=True)
