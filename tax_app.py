import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import date
from fpdf import FPDF
import math

# =============================================================================
# CONFIGURATION & DATABASE
# =============================================================================
TAX_DATABASE = {
    "FY 2025-26": {
        "NEW_REGIME": {
            "std_deduction": 75000,
            "rebate_limit": 700000,
            "slabs": [
                (300000, 0.00),
                (600000, 0.05),
                (900000, 0.10),
                (1200000, 0.15),
                (1500000, 0.20),
                (float('inf'), 0.30)
            ]
        },
        "OLD_REGIME": {
            "std_deduction": 50000,
            "rebate_limit": 500000,
            "slabs": [
                (250000, 0.00),
                (500000, 0.05),
                (1000000, 0.20),
                (float('inf'), 0.30)
            ]
        }
    },
    "FY 2026-27": {
        "NEW_REGIME": {
            "std_deduction": 75000,
            "rebate_limit": 1200000,  # Budget 2025 enhancement
            "slabs": [
                (400000, 0.00),
                (800000, 0.05),
                (1200000, 0.10),
                (1600000, 0.15),
                (2000000, 0.20),
                (2400000, 0.25),
                (float('inf'), 0.30)
            ]
        },
        "OLD_REGIME": {
            "std_deduction": 50000,
            "rebate_limit": 500000,
            "slabs": [
                (250000, 0.00),
                (500000, 0.05),
                (1000000, 0.20),
                (float('inf'), 0.30)
            ]
        }
    }
}

CESS_RATE = 0.04
SURCHARGE_SLABS = [
    (5000000, 0.00),
    (10000000, 0.10),
    (20000000, 0.15),
    (50000000, 0.25),
    (float('inf'), 0.37)  # Note: New Regime capped at 25%
]

# =============================================================================
# CALCULATION FUNCTIONS
# =============================================================================
def calc_hra(actual, basic, rent, city):
    if rent == 0:
        return 0, "No rent paid — HRA fully taxable"
    p = 0.5 if city == "Metro" else 0.4
    l1 = actual
    l2 = max(0, rent - (0.1 * basic))
    l3 = p * basic
    exemp = max(0, min(l1, l2, l3))
    logic = (f"Min of: (1) Actual HRA={l1:,.0f} | "
             f"(2) Rent-10%Basic={l2:,.0f} | "
             f"(3) {int(p*100)}% of Basic={l3:,.0f} → Exempt={exemp:,.0f}")
    return exemp, logic

def calc_gratuity(received, years, last_sal, govt_employee=False):
    if govt_employee:
        return received, "Govt employee: Full gratuity exempt"
    limit = (15 / 26) * last_sal * years
    exemp = min(received, limit, 2000000)
    logic = (f"Min of: (1) Received={received:,.0f} | "
             f"(2) 15/26 × {last_sal:,.0f} × {years} yrs={limit:,.0f} | "
             f"(3) Statutory Cap=20,00,000 → Exempt={exemp:,.0f}")
    return exemp, logic

def calc_leave_encashment(received, avg_salary, leave_days, govt_employee=False):
    if govt_employee:
        return received, "Govt employee: Full leave encashment exempt"
    avg_monthly = avg_salary / 12 if avg_salary > 0 else 0
    limit1 = avg_monthly * 10
    limit2 = avg_monthly * (leave_days / 30)
    exemp = min(received, limit1, limit2, 2500000)
    logic = (f"Min of: (1) Received={received:,.0f} | "
             f"(2) 10 months avg salary={limit1:,.0f} | "
             f"(3) Leave salary={limit2:,.0f} | "
             f"(4) Cap=25,00,000 → Exempt={exemp:,.0f}")
    return exemp, logic

def calc_pension_commutation(commuted_amt, has_gratuity):
    if has_gratuity:
        exemp = commuted_amt / 3
        logic = f"With gratuity: 1/3 of commuted pension exempt = {exemp:,.0f}"
    else:
        exemp = commuted_amt / 2
        logic = f"Without gratuity: 1/2 of commuted pension exempt = {exemp:,.0f}"
    return exemp, logic

def calc_surcharge(income, tax, regime="NEW_REGIME"):
    surcharge_rate = 0
    for limit, rate in SURCHARGE_SLABS:
        if income <= limit:
            break
        surcharge_rate = rate
    if regime == "NEW_REGIME" and surcharge_rate > 0.25:
        surcharge_rate = 0.25  # New regime surcharge capped at 25%
    surcharge = tax * surcharge_rate
    return surcharge, surcharge_rate

def calc_marginal_relief(income, tax, surcharge, threshold, regime, year):
    """Marginal relief: tax+surcharge should not exceed income above threshold"""
    excess_income = income - threshold
    total_tax = tax + surcharge
    if total_tax > excess_income:
        relief = total_tax - excess_income
        return max(0, relief)
    return 0

def calculate_slab_tax(taxable_income, year, regime):
    config = TAX_DATABASE[year][regime]
    
    # Check 87A rebate
    if taxable_income <= config["rebate_limit"]:
        return 0.0, "Rebate u/s 87A Applied — Zero Tax", True
    
    tax, prev_limit, breakdown = 0, 0, ""
    for limit, rate in config["slabs"]:
        if taxable_income > prev_limit:
            taxable_in_slab = min(taxable_income, limit) - prev_limit
            slab_tax = taxable_in_slab * rate
            tax += slab_tax
            limit_display = f"{limit:,.0f}" if limit != float('inf') else "Above"
            breakdown += (f"  ₹{prev_limit:,.0f} – ₹{limit_display} "
                          f"@ {rate*100:.0f}%: ₹{slab_tax:,.0f}\n")
            prev_limit = limit
        else:
            break
    return tax, breakdown, False

def format_inr(amount):
    """Format amount in Indian numbering system"""
    if amount < 0:
        return f"-₹{format_inr(-amount)}"
    amount = int(amount)
    s = str(amount)
    if len(s) <= 3:
        return f"₹{s}"
    last3 = s[-3:]
    rest = s[:-3]
    result = ""
    for i, c in enumerate(reversed(rest)):
        if i > 0 and i % 2 == 0:
            result = "," + result
        result = c + result
    return f"₹{result},{last3}"

def words_amount(n):
    """Convert number to Indian words"""
    if n == 0:
        return "Zero"
    ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven',
            'Eight', 'Nine', 'Ten', 'Eleven', 'Twelve', 'Thirteen',
            'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen']
    tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty',
            'Sixty', 'Seventy', 'Eighty', 'Ninety']
    
    def helper(num):
        if num == 0:
            return ''
        elif num < 20:
            return ones[num] + ' '
        elif num < 100:
            return tens[num // 10] + ' ' + helper(num % 10)
        elif num < 1000:
            return ones[num // 100] + ' Hundred ' + helper(num % 100)
        return ''
    
    result = ''
    if n >= 10000000:
        result += helper(n // 10000000) + 'Crore '
        n %= 10000000
    if n >= 100000:
        result += helper(n // 100000) + 'Lakh '
        n %= 100000
    if n >= 1000:
        result += helper(n // 1000) + 'Thousand '
        n %= 1000
    result += helper(n)
    return result.strip() + ' Only'

# =============================================================================
# PAGE CONFIGURATION & STYLING
# =============================================================================
st.set_page_config(
    page_title="S P C A & Co | Income Tax Calculator",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Crimson+Pro:wght@400;600;700&family=DM+Sans:wght@300;400;500;600&display=swap');
    
    :root {
        --navy: #0f2557;
        --navy-light: #1e3a8a;
        --emerald: #065f46;
        --emerald-light: #059669;
        --gold: #b45309;
        --gold-light: #f59e0b;
        --cream: #fefce8;
        --bg: #f0f4f8;
        --white: #ffffff;
        --text: #1e293b;
        --border: #e2e8f0;
        --red: #dc2626;
        --green-bg: #ecfdf5;
        --red-bg: #fef2f2;
    }
    
    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
        color: var(--text);
    }
    
    .main { background-color: var(--bg); }
    
    /* HEADER */
    .firm-header {
        background: linear-gradient(135deg, var(--navy) 0%, #1e3a8a 60%, #1e40af 100%);
        color: white;
        padding: 28px 36px;
        border-radius: 16px;
        margin-bottom: 24px;
        position: relative;
        overflow: hidden;
        box-shadow: 0 8px 32px rgba(15, 37, 87, 0.3);
    }
    .firm-header::before {
        content: '';
        position: absolute;
        top: -40px; right: -40px;
        width: 200px; height: 200px;
        border-radius: 50%;
        background: rgba(245, 158, 11, 0.15);
    }
    .firm-header::after {
        content: '';
        position: absolute;
        bottom: -60px; left: 30%;
        width: 300px; height: 150px;
        border-radius: 50%;
        background: rgba(255,255,255,0.05);
    }
    .firm-title {
        font-family: 'Crimson Pro', serif;
        font-size: 2.2rem;
        font-weight: 700;
        letter-spacing: 0.5px;
        margin: 0;
    }
    .firm-subtitle {
        font-size: 0.95rem;
        opacity: 0.85;
        margin-top: 4px;
        font-weight: 300;
    }
    .firm-badge {
        background: var(--gold-light);
        color: var(--navy);
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 600;
        display: inline-block;
        margin-top: 10px;
    }
    
    /* METRIC CARDS */
    .metric-card {
        background: white;
        border-radius: 12px;
        padding: 20px 24px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        border-left: 5px solid var(--navy-light);
        margin-bottom: 12px;
    }
    .metric-card.green { border-left-color: var(--emerald-light); }
    .metric-card.gold { border-left-color: var(--gold); }
    .metric-card.red { border-left-color: var(--red); }
    .metric-card-label { font-size: 0.78rem; color: #64748b; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; }
    .metric-card-value { font-family: 'Crimson Pro', serif; font-size: 1.8rem; font-weight: 700; color: var(--navy); margin-top: 4px; }
    .metric-card-sub { font-size: 0.8rem; color: #94a3b8; margin-top: 2px; }
    
    /* REGIME BADGE */
    .regime-recommended {
        background: linear-gradient(135deg, var(--emerald), var(--emerald-light));
        color: white;
        padding: 8px 20px;
        border-radius: 8px;
        font-weight: 600;
        font-size: 1rem;
        display: inline-block;
        margin: 8px 0;
    }
    
    /* SECTION HEADERS */
    .section-header {
        font-family: 'Crimson Pro', serif;
        font-size: 1.3rem;
        font-weight: 600;
        color: var(--navy);
        border-bottom: 2px solid var(--gold-light);
        padding-bottom: 6px;
        margin: 20px 0 14px;
    }
    
    /* COMPARISON TABLE */
    .comp-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
    .comp-table th {
        background: var(--navy);
        color: white;
        padding: 10px 14px;
        text-align: right;
        font-weight: 500;
    }
    .comp-table th:first-child { text-align: left; }
    .comp-table td { padding: 8px 14px; border-bottom: 1px solid var(--border); }
    .comp-table td:not(:first-child) { text-align: right; font-family: 'Crimson Pro', serif; font-size: 1rem; }
    .comp-table tr:nth-child(even) { background: #f8fafc; }
    .comp-table tr.total-row td { font-weight: 700; background: #eff6ff; border-top: 2px solid var(--navy); }
    .comp-table tr.winner td { background: var(--green-bg); color: var(--emerald); font-weight: 700; }
    
    /* TIPS BOX */
    .tip-box {
        background: var(--cream);
        border: 1px solid var(--gold-light);
        border-left: 4px solid var(--gold);
        border-radius: 8px;
        padding: 14px 18px;
        font-size: 0.88rem;
        color: #78350f;
        margin: 12px 0;
    }
    .tip-box strong { color: var(--gold); }
    
    /* DISCLAIMER */
    .disclaimer {
        background: #fef2f2;
        border: 1px solid #fecaca;
        border-radius: 8px;
        padding: 12px 16px;
        font-size: 0.82rem;
        color: #991b1b;
        margin-top: 24px;
    }
    
    /* BUTTON */
    .stButton > button {
        background: linear-gradient(135deg, var(--navy), var(--navy-light)) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 14px 32px !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px !important;
        width: 100% !important;
        box-shadow: 0 4px 16px rgba(15,37,87,0.25) !important;
        transition: all 0.2s !important;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, var(--navy-light), #3b82f6) !important;
        box-shadow: 0 6px 24px rgba(15,37,87,0.35) !important;
        transform: translateY(-1px) !important;
    }
    
    /* SIDEBAR */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f2557 0%, #1e3a8a 100%);
    }
    [data-testid="stSidebar"] * { color: white !important; }
    [data-testid="stSidebar"] .stTextInput > div > div > input {
        background: rgba(255,255,255,0.1) !important;
        border: 1px solid rgba(255,255,255,0.3) !important;
        color: white !important;
        border-radius: 8px !important;
    }
    [data-testid="stSidebar"] .stSelectbox > div > div {
        background: rgba(255,255,255,0.1) !important;
        border: 1px solid rgba(255,255,255,0.3) !important;
        border-radius: 8px !important;
    }
    [data-testid="stSidebar"] label { color: rgba(255,255,255,0.8) !important; font-size: 0.85rem !important; }
    
    /* TABS */
    .stTabs [data-baseweb="tab-list"] { background: #f1f5f9; border-radius: 10px; padding: 4px; gap: 4px; }
    .stTabs [data-baseweb="tab"] { border-radius: 8px; font-weight: 500; color: #64748b; font-size: 0.88rem; }
    .stTabs [aria-selected="true"] { background: var(--navy) !important; color: white !important; }
    
    /* EXPANDER */
    .streamlit-expanderHeader {
        background: #eff6ff !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        color: var(--navy) !important;
    }
    
    /* FOOTER */
    .firm-footer {
        text-align: center;
        padding: 20px;
        color: #94a3b8;
        font-size: 0.82rem;
        border-top: 1px solid var(--border);
        margin-top: 40px;
    }
    .firm-footer a { color: var(--navy-light); text-decoration: none; font-weight: 500; }
    
    /* NUMBER INPUT */
    .stNumberInput > div > div > input { border-radius: 8px !important; }
    
    /* SUCCESS / WARNING / INFO */
    .saving-badge {
        background: var(--green-bg);
        border: 1px solid #6ee7b7;
        color: var(--emerald);
        padding: 12px 16px;
        border-radius: 10px;
        font-weight: 600;
        font-size: 1.05rem;
        text-align: center;
    }
    
    .info-pill {
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        color: var(--navy-light);
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 500;
        display: inline-block;
        margin: 3px;
    }
    
    /* HIDE streamlit branding */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# HEADER
# =============================================================================
st.markdown("""
<div class="firm-header">
    <div style="position:relative; z-index:1;">
        <div class="firm-title">🏛️ S P C A & Co, Chartered Accountants</div>
        <div class="firm-subtitle">Bhubaneswar, Odisha &nbsp;|&nbsp; www.caspca.net &nbsp;|&nbsp; +91 9692156373</div>
        <div class="firm-badge">⚖️ Income Tax Computation Tool — FY 2025-26 & 2026-27</div>
    </div>
</div>
""", unsafe_allow_html=True)

# =============================================================================
# SIDEBAR
# =============================================================================
with st.sidebar:
    st.markdown("### 👤 Client Profile")
    u_name = st.text_input("Client Full Name", value="", placeholder="Eg: Ramesh Kumar Sharma")
    u_pan = st.text_input("PAN Number", value="", placeholder="ABCDE1234F")
    u_dob = st.date_input("Date of Birth", value=date(1980, 1, 1))
    
    # Calculate age for senior citizen benefit
    today = date.today()
    age = today.year - u_dob.year - ((today.month, today.day) < (u_dob.month, u_dob.day))
    if age >= 80:
        st.markdown('<div class="info-pill">👴 Super Senior Citizen (80+)</div>', unsafe_allow_html=True)
    elif age >= 60:
        st.markdown('<div class="info-pill">🧓 Senior Citizen (60-79)</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="info-pill">👤 Below 60 years</div>', unsafe_allow_html=True)
    
    u_status = st.selectbox("Residential Status", ["Resident Indian", "NRI", "RNOR"])
    u_category = st.selectbox("Category", ["Individual", "HUF"])
    u_employment = st.selectbox("Employment Type", ["Salaried", "Business/Profession", "Both", "Retired/Pensioner"])
    selected_year = st.selectbox("Financial Year", options=list(TAX_DATABASE.keys()))
    
    st.markdown("---")
    st.markdown("### ⚙️ Settings")
    show_comparison = st.checkbox("Show Regime Comparison", value=True)
    show_charts = st.checkbox("Show Visual Charts", value=True)
    show_tips = st.checkbox("Show Tax Planning Tips", value=True)
    is_govt_employee = st.checkbox("Government Employee", value=False)

    # Adjust rebate limits for senior citizens (old regime)
    if age >= 80:
        TAX_DATABASE[selected_year]["OLD_REGIME"]["slabs"] = [
            (500000, 0.00), (1000000, 0.20), (float('inf'), 0.30)
        ]
    elif age >= 60:
        TAX_DATABASE[selected_year]["OLD_REGIME"]["slabs"] = [
            (300000, 0.00), (500000, 0.05), (1000000, 0.20), (float('inf'), 0.30)
        ]
    
    st.markdown("---")
    st.markdown("""
    <div style="font-size:0.78rem; color:rgba(255,255,255,0.6); line-height:1.6;">
    📞 +91 9692156373<br>
    📧 info@caspca.net<br>
    🌐 www.caspca.net<br><br>
    <em>For professional consultation<br>contact us directly.</em>
    </div>
    """, unsafe_allow_html=True)

# =============================================================================
# MAIN INPUT TABS
# =============================================================================
st.markdown('<div class="section-header">📋 Income & Deduction Details</div>', unsafe_allow_html=True)

with st.expander("📁 CLICK TO ENTER INCOME & EXEMPTION DETAILS", expanded=True):
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "💼 Salary", "🏠 House Property", "📊 Business", "📈 Capital Gains",
        "💰 Other Sources", "📉 Deductions", "🧾 Tax Paid"
    ])

    # =========== TAB 1: SALARY ===========
    with tab1:
        st.markdown("#### 💼 Salary Income & Exemptions")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            basic = st.number_input("Basic Salary (₹/yr)", min_value=0, value=0, step=1000,
                                    help="Annual basic salary as per appointment letter")
        with col2:
            da = st.number_input("Dearness Allowance DA (₹/yr)", min_value=0, value=0, step=1000,
                                 help="Annual DA component")
        with col3:
            actual_hra = st.number_input("HRA Received (₹/yr)", min_value=0, value=0, step=1000,
                                         help="Annual HRA component of salary")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            bonus = st.number_input("Bonus/Incentives (₹)", min_value=0, value=0, step=1000)
        with col2:
            lta = st.number_input("LTA Received (₹)", min_value=0, value=0, step=1000,
                                   help="Leave Travel Allowance — exempt up to actuals for 2 journeys in 4-yr block")
        with col3:
            other_allow = st.number_input("Other Taxable Allowances (₹)", min_value=0, value=0, step=1000)
        
        # NPS Employer Contribution
        col1, col2 = st.columns(2)
        with col1:
            nps_employer = st.number_input("NPS Employer Contribution (₹) [Sec 80CCD(2)]", min_value=0, value=0, step=1000,
                                            help="Available in BOTH regimes. Up to 10% of Basic+DA")
        with col2:
            perquisites = st.number_input("Perquisites / ESOPs (₹)", min_value=0, value=0, step=1000,
                                          help="Value of perquisites as per Form 16")
        
        st.markdown("---")
        
        # HRA Calculator
        with st.container(border=True):
            st.markdown("**🏠 HRA Exemption Calculator** *(u/s 10(13A))*")
            c1, c2, c3 = st.columns(3)
            rent_paid = c1.number_input("Rent Paid p.a. (₹)", min_value=0, value=0, step=1000,
                                         help="Annual rent actually paid")
            city = c2.selectbox("City Type", ["Non-Metro", "Metro"],
                                help="Metro: Delhi, Mumbai, Kolkata, Chennai")
            lta_claimed = c3.number_input("LTA Claimed as Exempt (₹)", min_value=0, value=0, step=1000,
                                           help="Exempt LTA (actual travel cost, economy class)")
        
        # Gratuity Calculator
        with st.container(border=True):
            st.markdown("**🎁 Gratuity Exemption** *(u/s 10(10))*")
            c1, c2, c3 = st.columns(3)
            gratuity_rec = c1.number_input("Gratuity Received (₹)", min_value=0, value=0, step=1000)
            g_years = c2.number_input("Completed Years of Service", min_value=0, value=0)
            g_last_sal = c3.number_input("Last Month Basic+DA (₹)", min_value=0, value=0, step=1000)
        
        # Leave Encashment
        with st.container(border=True):
            st.markdown("**📅 Leave Encashment Exemption** *(u/s 10(10AA))*")
            c1, c2, c3 = st.columns(3)
            leave_enc = c1.number_input("Leave Encashment Received (₹)", min_value=0, value=0, step=1000)
            avg_sal_le = c2.number_input("Average Annual Salary (₹)", min_value=0, value=0, step=1000)
            leave_days = c3.number_input("Earned Leave Balance (days)", min_value=0, value=0)
        
        # Pension
        with st.container(border=True):
            st.markdown("**👴 Commuted Pension** *(u/s 10(10A))*")
            c1, c2 = st.columns(2)
            pension_commuted = c1.number_input("Commuted Pension Received (₹)", min_value=0, value=0, step=1000)
            has_gratuity = c2.checkbox("Also receiving Gratuity?", value=False,
                                        help="If yes: 1/3 exempt; If no: 1/2 exempt")
            uncommuted_pension = st.number_input("Uncommuted (Monthly) Pension × 12 (₹ annual)", min_value=0, value=0, step=1000,
                                                  help="Fully taxable as salary")

    # =========== TAB 2: HOUSE PROPERTY ===========
    with tab2:
        st.markdown("#### 🏠 Income from House Property")
        
        col1, col2 = st.columns(2)
        prop_type = col1.selectbox("Property Type", ["Self-Occupied", "Let Out", "Deemed Let Out"])
        
        if prop_type == "Self-Occupied":
            st.info("ℹ️ Self-Occupied: Annual Value = Nil. Only home loan interest (max ₹2L) deductible u/s 24(b)")
            loan_int = st.number_input("Interest on Home Loan (₹) [Sec 24(b)]", min_value=0, value=0, step=1000,
                                        help="Max ₹2,00,000 for self-occupied property")
            rent_rec = 0
            m_tax = 0
        else:
            c1, c2, c3 = st.columns(3)
            rent_rec = c1.number_input("Annual Rent Received (₹)", min_value=0, value=0, step=1000)
            m_tax = c2.number_input("Municipal Taxes Paid (₹)", min_value=0, value=0, step=1000)
            loan_int = c3.number_input("Interest on Home Loan (₹) [Sec 24(b)]", min_value=0, value=0, step=1000)
        
        # Calculate Net Annual Value
        if prop_type == "Self-Occupied":
            nav = 0
            hp_income = max(-200000, -min(loan_int, 200000))
        else:
            nav = rent_rec - m_tax
            std_ded_hp = 0.30 * nav  # 30% standard deduction
            hp_income = nav - std_ded_hp - loan_int
        
        st.info(f"📌 Net HP Income/(Loss): ₹{hp_income:,.0f} {'(Set-off limited to ₹2L against other income)' if hp_income < 0 else ''}")
        hp_loss_setoff = max(-200000, hp_income) if hp_income < 0 else hp_income

    # =========== TAB 3: BUSINESS ===========
    with tab3:
        st.markdown("#### 📊 Business / Profession Income")
        
        biz_scheme = st.selectbox("Computation Method", [
            "Regular Books (Actuals)",
            "Presumptive u/s 44AD (Businesses — 6%/8%)",
            "Presumptive u/s 44ADA (Professionals — 50%)",
            "Presumptive u/s 44AE (Transporters)"
        ])
        
        col1, col2 = st.columns(2)
        biz_rev = col1.number_input("Gross Receipts / Turnover (₹)", min_value=0, value=0, step=10000)
        
        if "44AD" in biz_scheme:
            digital = col2.checkbox("All receipts via Banking/Digital?")
            rate = 0.06 if digital else 0.08
            biz_exp = 0
            presumptive_inc = biz_rev * rate
            st.info(f"📌 Presumptive Income u/s 44AD @ {rate*100}% = ₹{presumptive_inc:,.0f}")
        elif "44ADA" in biz_scheme:
            biz_exp = 0
            presumptive_inc = biz_rev * 0.50
            st.info(f"📌 Presumptive Income u/s 44ADA @ 50% = ₹{presumptive_inc:,.0f}")
        elif "44AE" in biz_scheme:
            vehicles = col2.number_input("No. of Vehicles (HGV)", min_value=0, value=0)
            presumptive_inc = vehicles * 1000 * 12  # ₹1000/ton/month simplified
            biz_exp = 0
            st.info(f"📌 Presumptive Income u/s 44AE = ₹{presumptive_inc:,.0f} (approx)")
        else:
            biz_exp = col2.number_input("Allowable Business Expenses (₹)", min_value=0, value=0, step=10000)
            presumptive_inc = max(0, biz_rev - biz_exp)
        
        biz_income = presumptive_inc if "Regular" not in biz_scheme else max(0, biz_rev - biz_exp)
        
        col1, col2 = st.columns(2)
        biz_depreciation = col1.number_input("Additional Depreciation/Losses (₹)", min_value=0, value=0, step=1000,
                                              help="Only for regular books. WDV depreciation, etc.")
        brought_fwd_loss = col2.number_input("Business Loss Brought Forward (₹)", min_value=0, value=0, step=1000)
        
        net_biz_income = max(0, biz_income - biz_depreciation - brought_fwd_loss)
        if biz_income > 0:
            st.info(f"📌 Net Business Income: ₹{net_biz_income:,.0f}")

    # =========== TAB 4: CAPITAL GAINS ===========
    with tab4:
        st.markdown("#### 📈 Capital Gains")
        
        st.markdown("**Short Term Capital Gains (STCG)**")
        col1, col2 = st.columns(2)
        stcg_111a = col1.number_input("STCG u/s 111A (Listed Equity @ 20%)", min_value=0, value=0, step=1000,
                                       help="Shares/equity MF held ≤ 12 months, taxed @ 20% (Budget 2024)")
        stcg_other = col2.number_input("Other STCG (@ Slab Rate)", min_value=0, value=0, step=1000,
                                        help="Debt MF, property, etc. held ≤ 24 months")
        
        st.markdown("**Long Term Capital Gains (LTCG)**")
        col1, col2, col3 = st.columns(3)
        ltcg_112a = col1.number_input("LTCG u/s 112A (Equity @ 12.5% above ₹1.25L)", min_value=0, value=0, step=1000,
                                       help="Listed equity/MF held > 12 months. First ₹1.25L exempt")
        ltcg_112 = col2.number_input("LTCG u/s 112 (Other Assets @ 20%)", min_value=0, value=0, step=1000,
                                      help="Property, unlisted shares, debt MF held > 24/36 months")
        ltcg_exemption = col3.number_input("LTCG Exemption (54/54EC/54F) (₹)", min_value=0, value=0, step=1000,
                                            help="Reinvestment in property or bonds")
        
        # Calculate CG tax separately
        ltcg_112a_taxable = max(0, ltcg_112a - 125000 - ltcg_exemption)
        ltcg_112_net = max(0, ltcg_112 - ltcg_exemption)
        
        cg_tax = (stcg_111a * 0.20) + (stcg_other * 0)  # other STCG at slab
        cg_tax += (ltcg_112a_taxable * 0.125) + (ltcg_112_net * 0.20)
        
        st.info(f"📌 Flat Rate CG Tax (before cess): ₹{cg_tax:,.0f} | STCG (slab) added to total income: ₹{stcg_other:,.0f}")

    # =========== TAB 5: OTHER SOURCES ===========
    with tab5:
        st.markdown("#### 💰 Income from Other Sources")
        
        st.markdown("**At Slab Rates**")
        col1, col2, col3 = st.columns(3)
        int_bank = col1.number_input("Bank Interest (SB/FD) (₹)", min_value=0, value=0, step=1000)
        int_nsc = col2.number_input("NSC Interest / Post Office (₹)", min_value=0, value=0, step=1000)
        dividends = col3.number_input("Dividends Received (₹)", min_value=0, value=0, step=1000,
                                       help="Fully taxable since FY 2020-21")
        misc_inc = st.number_input("Miscellaneous Income (₹)", min_value=0, value=0, step=1000)
        
        st.markdown("**At Special Flat Rates**")
        col1, col2 = st.columns(2)
        crypto_inc = col1.number_input("Crypto / VDA Income (₹) [@ 30%]", min_value=0, value=0, step=1000,
                                        help="No set-off, no deduction u/s 115BBH")
        lottery_inc = col2.number_input("Lottery / Game Show Winnings (₹) [@ 30%]", min_value=0, value=0, step=1000,
                                         help="TDS u/s 194B @ 30%. No deductions allowed.")
        
        # 80TTA / 80TTB
        if age >= 60:
            tta_limit = min(int_bank + int_nsc, 50000)  # 80TTB for seniors
            st.info(f"ℹ️ 80TTB (Senior Citizen): Bank/PO interest deduction available = ₹{tta_limit:,.0f}")
        else:
            tta_limit = min(int_bank, 10000)  # 80TTA for others
            st.info(f"ℹ️ 80TTA: Savings bank interest deduction available = ₹{tta_limit:,.0f} (max ₹10,000)")

    # =========== TAB 6: DEDUCTIONS ===========
    with tab6:
        st.markdown("#### 📉 Chapter VI-A Deductions *(Old Regime Only)*")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Section 80C Group (Max ₹1,50,000)**")
            s80c_ppf = st.number_input("PPF / EPF / VPF (₹)", min_value=0, value=0, step=1000)
            s80c_lic = st.number_input("LIC Premium / ULIP (₹)", min_value=0, value=0, step=1000)
            s80c_elss = st.number_input("ELSS Mutual Fund (₹)", min_value=0, value=0, step=1000)
            s80c_housing = st.number_input("Home Loan Principal (₹)", min_value=0, value=0, step=1000)
            s80c_tuition = st.number_input("Children Tuition Fee (₹)", min_value=0, value=0, step=1000)
            s80c_nsc = st.number_input("NSC / SCSS / Tax Saver FD (₹)", min_value=0, value=0, step=1000)
        
        with col2:
            st.markdown("**Health & Other Deductions**")
            s80d_self = st.number_input("80D: Health Ins. (Self/Family) (₹)", min_value=0, value=0, step=1000,
                                         help="Max ₹25,000 (₹50,000 for senior citizen)")
            s80d_parent = st.number_input("80D: Health Ins. (Parents) (₹)", min_value=0, value=0, step=1000,
                                           help="Max ₹25,000 (₹50,000 if parents are senior citizens)")
            s80ccd_1b = st.number_input("80CCD(1B): NPS Self (₹)", min_value=0, value=0, step=1000,
                                         help="Additional ₹50,000 over 80C limit")
            s80g = st.number_input("80G: Donations (₹)", min_value=0, value=0, step=1000)
            s80e = st.number_input("80E: Education Loan Interest (₹)", min_value=0, value=0, step=1000,
                                    help="No limit — full interest deductible for 8 years")
            s80ee = st.number_input("80EEA: Addl Home Loan Interest (₹)", min_value=0, value=0, step=1000,
                                     help="Additional ₹1.5L for affordable housing (check eligibility)")
        
        # Calculate deductions
        s80c_total = min(s80c_ppf + s80c_lic + s80c_elss + s80c_housing + s80c_tuition + s80c_nsc, 150000)
        s80d_limit_self = 50000 if age >= 60 else 25000
        s80d_limit_parent = 50000  # assume parents are senior citizens
        s80d_total = min(s80d_self, s80d_limit_self) + min(s80d_parent, s80d_limit_parent)
        s80ccd_total = min(s80ccd_1b, 50000)
        
        if age >= 60:
            tta_ded = min(int_bank + int_nsc, 50000)
        else:
            tta_ded = min(int_bank, 10000)
        
        total_old_ded = s80c_total + s80d_total + s80ccd_total + s80g + s80e + min(s80ee, 150000) + tta_ded
        
        st.markdown(f"""
        <div class="tip-box">
        <strong>📊 Deduction Summary (Old Regime):</strong><br>
        80C Group: ₹{s80c_total:,.0f} | 80D Health: ₹{s80d_total:,.0f} | 80CCD(1B) NPS: ₹{s80ccd_total:,.0f}<br>
        80G Donations: ₹{s80g:,.0f} | 80E Education Loan: ₹{s80e:,.0f} | 80TTA/B: ₹{tta_ded:,.0f}<br>
        <strong>Total Chapter VI-A Deductions: ₹{total_old_ded:,.0f}</strong>
        </div>
        """, unsafe_allow_html=True)

    # =========== TAB 7: TAX PAID ===========
    with tab7:
        st.markdown("#### 🧾 Taxes Already Paid")
        
        col1, col2 = st.columns(2)
        with col1:
            tds_salary = st.number_input("TDS on Salary (Form 16 Part A) (₹)", min_value=0, value=0, step=100)
            tds_other = st.number_input("TDS on Other Income (26AS/AIS) (₹)", min_value=0, value=0, step=100)
            advance_tax = st.number_input("Advance Tax Paid (₹)", min_value=0, value=0, step=100)
        
        with col2:
            self_assessment = st.number_input("Self-Assessment Tax Paid (₹)", min_value=0, value=0, step=100)
            tcs_credit = st.number_input("TCS Credit (₹)", min_value=0, value=0, step=100)
            filing_date = st.date_input("Expected Filing Date", value=date.today())
        
        total_paid = tds_salary + tds_other + advance_tax + self_assessment + tcs_credit
        
        # Determine due date
        due_date_july = date(filing_date.year, 7, 31)
        if total_paid > 0:
            st.info(f"📌 Total Taxes Paid: ₹{total_paid:,.0f} | Due Date: 31-Jul-{filing_date.year}")

# =============================================================================
# CALCULATE BUTTON
# =============================================================================
st.markdown("<br>", unsafe_allow_html=True)
col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
with col_btn2:
    calculate = st.button("🚀 COMPUTE INCOME TAX & GENERATE REPORT", type="primary")

# =============================================================================
# CALCULATION ENGINE
# =============================================================================
if calculate:
    
    # --- Exemptions ---
    hra_ex, hra_log = calc_hra(actual_hra, basic + da, rent_paid, city)
    gra_ex, gra_log = calc_gratuity(gratuity_rec, g_years, g_last_sal, is_govt_employee)
    le_ex, le_log = calc_leave_encashment(leave_enc, avg_sal_le, leave_days, is_govt_employee)
    pen_ex, pen_log = calc_pension_commutation(pension_commuted, has_gratuity)
    lta_exempt = min(lta, lta_claimed)
    nps_emp_exempt = min(nps_employer, 0.10 * (basic + da))  # 80CCD(2) - in both regimes
    
    total_exemptions = hra_ex + gra_ex + le_ex + pen_ex + lta_exempt
    
    # --- Salary Income ---
    salary_gross = basic + da + actual_hra + gratuity_rec + pension_commuted + uncommuted_pension + bonus + lta + other_allow + perquisites + nps_employer + leave_enc
    salary_taxable_before_std = salary_gross - total_exemptions - nps_emp_exempt
    
    # --- Other Heads ---
    hp_net = hp_loss_setoff
    biz_net = net_biz_income
    other_slab = int_bank + int_nsc + dividends + misc_inc + stcg_other
    special_income = crypto_inc + lottery_inc
    
    # --- GTI (Gross Total Income) ---
    # Slab income (excluding special rate and flat rate CG)
    gti_slab = salary_taxable_before_std + hp_net + biz_net + other_slab + stcg_other
    gti = gti_slab + special_income + stcg_111a + ltcg_112a + ltcg_112

    # --- NEW REGIME COMPUTATION ---
    new_std_ded = TAX_DATABASE[selected_year]["NEW_REGIME"]["std_deduction"]
    new_slab_income = max(0, (salary_taxable_before_std - new_std_ded) + hp_net + biz_net + other_slab)
    new_base_tax, new_breakdown, new_rebate = calculate_slab_tax(new_slab_income, selected_year, "NEW_REGIME")
    new_surcharge, new_surcharge_rate = calc_surcharge(new_slab_income, new_base_tax, "NEW_REGIME")
    new_cg_tax = cg_tax
    new_special_tax = special_income * 0.30
    new_total_before_cess = new_base_tax + new_surcharge + new_cg_tax + new_special_tax
    new_total = new_total_before_cess * (1 + CESS_RATE)
    
    # --- OLD REGIME COMPUTATION ---
    old_std_ded = TAX_DATABASE[selected_year]["OLD_REGIME"]["std_deduction"]
    old_slab_income = max(0, (salary_taxable_before_std - old_std_ded) + hp_net + biz_net + other_slab - total_old_ded)
    old_base_tax, old_breakdown, old_rebate = calculate_slab_tax(old_slab_income, selected_year, "OLD_REGIME")
    old_surcharge, old_surcharge_rate = calc_surcharge(old_slab_income, old_base_tax, "OLD_REGIME")
    old_cg_tax = cg_tax
    old_special_tax = special_income * 0.30
    old_total_before_cess = old_base_tax + old_surcharge + old_cg_tax + old_special_tax
    old_total = old_total_before_cess * (1 + CESS_RATE)
    
    # --- OPTIMAL REGIME ---
    chosen = "New Regime" if new_total <= old_total else "Old Regime"
    final_tax = min(new_total, old_total)
    saving = abs(new_total - old_total)
    
    # --- LIABILITY ---
    total_paid = tds_salary + tds_other + advance_tax + self_assessment + tcs_credit
    shortfall = max(0, final_tax - total_paid)
    refund = max(0, total_paid - final_tax)
    
    # Section 234A/B/C Interest (simplified 234A only)
    int_234a = 0
    due_date = date(filing_date.year, 7, 31)
    if filing_date > due_date and shortfall > 0:
        months = (filing_date.year - due_date.year) * 12 + (filing_date.month - due_date.month)
        if (filing_date.day > due_date.day): months += 1
        int_234a = shortfall * 0.01 * months
    
    # Simplified 234B (advance tax shortfall)
    int_234b = 0
    if (advance_tax + tcs_credit) < (final_tax * 0.90):
        int_234b = max(0, final_tax - advance_tax - tcs_credit) * 0.01 * 12  # approximate
    
    total_interest = int_234a + int_234b
    net_payable = max(0, shortfall + total_interest)
    net_refund = max(0, refund - total_interest)
    
    # ==========================================================================
    # DISPLAY RESULTS
    # ==========================================================================
    st.markdown("---")
    st.markdown(f"## 📊 Tax Computation — {u_name or 'Client'} | {u_pan or 'PAN'} | {selected_year}")
    
    # TOP METRIC CARDS
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-card-label">Gross Total Income</div>
            <div class="metric-card-value">{format_inr(int(gti))}</div>
            <div class="metric-card-sub">Before any deductions</div>
        </div>""", unsafe_allow_html=True)
    
    with col2:
        color = "green" if chosen == "New Regime" else "gold"
        st.markdown(f"""
        <div class="metric-card {color}">
            <div class="metric-card-label">Optimal Regime</div>
            <div class="metric-card-value" style="font-size:1.4rem;">{chosen}</div>
            <div class="metric-card-sub">Saving ₹{saving:,.0f} vs other</div>
        </div>""", unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card gold">
            <div class="metric-card-label">Total Tax Liability</div>
            <div class="metric-card-value">{format_inr(int(final_tax))}</div>
            <div class="metric-card-sub">Including cess @ 4%</div>
        </div>""", unsafe_allow_html=True)
    
    with col4:
        if net_payable > 0:
            st.markdown(f"""
            <div class="metric-card red">
                <div class="metric-card-label">Amount Payable</div>
                <div class="metric-card-value">{format_inr(int(net_payable))}</div>
                <div class="metric-card-sub">Including interest u/s 234</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="metric-card green">
                <div class="metric-card-label">Refund Due</div>
                <div class="metric-card-value">{format_inr(int(net_refund))}</div>
                <div class="metric-card-sub">To be claimed in ITR</div>
            </div>""", unsafe_allow_html=True)
    
    # REGIME COMPARISON TABLE
    if show_comparison:
        st.markdown('<div class="section-header">⚖️ Old vs New Regime — Detailed Comparison</div>', unsafe_allow_html=True)
        
        comparison_data = [
            ("Gross Salary", salary_gross, salary_gross),
            ("Less: Exemptions (HRA/Gra/LE/LTA)", -total_exemptions, -total_exemptions),
            ("Less: NPS Employer Contribution (80CCD2)", -nps_emp_exempt, -nps_emp_exempt),
            ("Less: Standard Deduction", -old_std_ded, -new_std_ded),
            ("Add: HP Income/(Loss)", hp_net, hp_net),
            ("Add: Business Income", biz_net, biz_net),
            ("Add: Other Sources (Slab)", other_slab, other_slab),
            ("Less: Chapter VI-A Deductions", -total_old_ded, 0),
            ("Net Slab Taxable Income", old_slab_income, new_slab_income),
            ("Base Slab Tax", old_base_tax, new_base_tax),
            ("Add: Surcharge", old_surcharge, new_surcharge),
            ("Add: CG Tax (Flat Rate)", cg_tax, cg_tax),
            ("Add: Special Income Tax (30%)", special_income * 0.30, special_income * 0.30),
            ("Add: H&EC Cess @ 4%", old_total_before_cess * 0.04, new_total_before_cess * 0.04),
        ]
        
        html_rows = ""
        for label, old_val, new_val in comparison_data:
            old_str = f"₹{old_val:,.0f}" if old_val >= 0 else f"(₹{-old_val:,.0f})"
            new_str = f"₹{new_val:,.0f}" if new_val >= 0 else f"(₹{-new_val:,.0f})"
            html_rows += f"<tr><td>{label}</td><td>{old_str}</td><td>{new_str}</td></tr>"
        
        # Total row
        old_str = f"<strong>₹{old_total:,.0f}</strong>"
        new_str = f"<strong>₹{new_total:,.0f}</strong>"
        html_rows += f'<tr class="total-row"><td>TOTAL TAX LIABILITY</td><td>{old_str}</td><td>{new_str}</td></tr>'
        
        # Winner row
        old_w = "✅ RECOMMENDED" if chosen == "Old Regime" else ""
        new_w = "✅ RECOMMENDED" if chosen == "New Regime" else ""
        html_rows += f'<tr class="winner"><td>Regime Recommendation</td><td>{old_w}</td><td>{new_w}</td></tr>'
        
        st.markdown(f"""
        <table class="comp-table">
            <thead><tr>
                <th>Particulars</th>
                <th>Old Regime (₹)</th>
                <th>New Regime (₹)</th>
            </tr></thead>
            <tbody>{html_rows}</tbody>
        </table>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="saving-badge">
            💰 {chosen} saves ₹{saving:,.0f} in taxes for {selected_year}
        </div>
        """, unsafe_allow_html=True)
    
    # EXEMPTION BREAKDOWN
    with st.expander("🔍 Detailed Exemption Calculation Logic", expanded=False):
        st.markdown(f"**HRA Exemption:** ₹{hra_ex:,.0f}")
        st.info(hra_log)
        st.markdown(f"**Gratuity Exemption:** ₹{gra_ex:,.0f}")
        st.info(gra_log)
        st.markdown(f"**Leave Encashment Exemption:** ₹{le_ex:,.0f}")
        st.info(le_log)
        st.markdown(f"**Commuted Pension Exemption:** ₹{pen_ex:,.0f}")
        st.info(pen_log)
    
    # SLAB BREAKDOWN
    with st.expander(f"📋 Slab-wise Tax Breakdown ({chosen})", expanded=False):
        st.text(new_breakdown if chosen == "New Regime" else old_breakdown)
    
    # FINAL SUMMARY TABLE
    st.markdown('<div class="section-header">📋 Final Net Tax Position</div>', unsafe_allow_html=True)
    
    final_data = {
        "Particulars": [
            "Gross Total Income (GTI)",
            f"Less: Deductions (Std Ded + Ch.VI-A) [{chosen}]",
            "Net Taxable Income",
            "Income Tax on Slab",
            "Add: Surcharge",
            "Add: CG / Special Income Tax",
            "Add: H&EC Cess @ 4%",
            "TOTAL TAX LIABILITY",
            "Less: TDS (Salary + Other)",
            "Less: Advance Tax / Self-Assessment",
            "Add: Interest u/s 234A",
            "Add: Interest u/s 234B (Approx.)",
            "NET AMOUNT PAYABLE / (REFUND)"
        ],
        f"Amount (₹) — {chosen}": [
            f"{gti:,.0f}",
            f"({total_exemptions + (new_std_ded if chosen == 'New Regime' else old_std_ded + total_old_ded):,.0f})",
            f"{new_slab_income if chosen == 'New Regime' else old_slab_income:,.0f}",
            f"{new_base_tax if chosen == 'New Regime' else old_base_tax:,.0f}",
            f"{new_surcharge if chosen == 'New Regime' else old_surcharge:,.0f}",
            f"{cg_tax + special_income * 0.30:,.0f}",
            f"{new_total_before_cess * 0.04 if chosen == 'New Regime' else old_total_before_cess * 0.04:,.0f}",
            f"{final_tax:,.0f}",
            f"({tds_salary + tds_other:,.0f})",
            f"({advance_tax + self_assessment + tcs_credit:,.0f})",
            f"{int_234a:,.0f}",
            f"{int_234b:,.0f}",
            f"{'(' + format_inr(int(net_refund)) + ') REFUND' if net_refund > 0 else format_inr(int(net_payable)) + ' PAYABLE'}"
        ]
    }
    
    df_final = pd.DataFrame(final_data)
    st.dataframe(df_final, hide_index=True, use_container_width=True)
    
    # Amount in words
    amt_in_words = words_amount(int(net_payable) if net_payable > 0 else int(net_refund))
    st.markdown(f"**In Words:** *{amt_in_words}*")
    
    # CHARTS
    if show_charts:
        st.markdown('<div class="section-header">📊 Visual Tax Analysis</div>', unsafe_allow_html=True)
        
        col_c1, col_c2 = st.columns(2)
        
        with col_c1:
            # Regime comparison bar chart
            fig_bar = go.Figure()
            categories = ["Base Tax", "Surcharge", "CG/Special Tax", "Cess"]
            old_vals = [
                old_base_tax,
                old_surcharge,
                cg_tax + old_special_tax,
                old_total_before_cess * 0.04
            ]
            new_vals = [
                new_base_tax,
                new_surcharge,
                cg_tax + new_special_tax,
                new_total_before_cess * 0.04
            ]
            
            fig_bar.add_trace(go.Bar(name="Old Regime", x=categories, y=old_vals,
                                     marker_color="#1e3a8a", text=[f"₹{v:,.0f}" for v in old_vals],
                                     textposition="outside"))
            fig_bar.add_trace(go.Bar(name="New Regime", x=categories, y=new_vals,
                                     marker_color="#059669", text=[f"₹{v:,.0f}" for v in new_vals],
                                     textposition="outside"))
            
            fig_bar.update_layout(
                title="Old vs New Regime Tax Components",
                barmode="group",
                plot_bgcolor="white",
                font=dict(family="DM Sans"),
                title_font=dict(family="Crimson Pro", size=16),
                showlegend=True,
                height=350,
                yaxis=dict(tickprefix="₹", tickformat=",")
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        
        with col_c2:
            # Income breakdown pie
            income_components = {
                "Salary (Net)": max(0, salary_taxable_before_std),
                "House Property": max(0, hp_net),
                "Business": max(0, biz_net),
                "Capital Gains": stcg_other + stcg_111a + max(0, ltcg_112a - 125000) + ltcg_112,
                "Other Sources": int_bank + int_nsc + dividends + misc_inc,
                "Special Income": special_income
            }
            
            filtered = {k: v for k, v in income_components.items() if v > 0}
            
            if filtered:
                fig_pie = go.Figure(go.Pie(
                    labels=list(filtered.keys()),
                    values=list(filtered.values()),
                    hole=0.45,
                    marker_colors=["#0f2557", "#1e3a8a", "#3b82f6", "#059669", "#b45309", "#dc2626"]
                ))
                fig_pie.update_layout(
                    title="Income Composition",
                    title_font=dict(family="Crimson Pro", size=16),
                    font=dict(family="DM Sans"),
                    height=350,
                    showlegend=True
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("Enter income data to see composition chart.")
        
        # Tax Rate Gauge
        effective_rate = (final_tax / gti * 100) if gti > 0 else 0
        marginal_rate = 30  # simplified
        
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=round(effective_rate, 2),
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Effective Tax Rate (%)", 'font': {'family': "Crimson Pro", 'size': 18}},
            delta={'reference': 30, 'increasing': {'color': "#dc2626"}, 'decreasing': {'color': "#059669"}},
            gauge={
                'axis': {'range': [None, 35], 'tickwidth': 1},
                'bar': {'color': "#1e3a8a"},
                'steps': [
                    {'range': [0, 10], 'color': "#ecfdf5"},
                    {'range': [10, 20], 'color': "#fef9c3"},
                    {'range': [20, 30], 'color': "#fff7ed"},
                    {'range': [30, 35], 'color': "#fef2f2"}
                ],
                'threshold': {
                    'line': {'color': "#dc2626", 'width': 3},
                    'thickness': 0.8,
                    'value': 30
                }
            }
        ))
        fig_gauge.update_layout(height=280, font=dict(family="DM Sans"))
        st.plotly_chart(fig_gauge, use_container_width=True)
    
    # TAX PLANNING TIPS
    if show_tips:
        st.markdown('<div class="section-header">💡 Tax Planning Recommendations</div>', unsafe_allow_html=True)
        
        tips = []
        
        if chosen == "New Regime" and s80c_total < 150000:
            tips.append(("Consider investments for Old Regime next year",
                          f"80C gap: ₹{150000 - s80c_total:,.0f} unused. If you invest in PPF/ELSS, old regime may save more."))
        
        if s80ccd_1b < 50000:
            tips.append(("Invest in NPS for additional ₹50,000 deduction",
                          f"80CCD(1B) unused: ₹{50000 - s80ccd_1b:,.0f}. Available even in New Regime via employer NPS!"))
        
        if ltcg_112a > 125000:
            tips.append(("Harvest LTCG annually within ₹1.25L exemption",
                          "Sell and re-buy equity holdings each year to reset cost basis and utilize the ₹1.25L LTCG exemption."))
        
        if s80d_self < s80d_limit_self:
            tips.append(("Health Insurance premium underutilized",
                          f"80D gap: ₹{s80d_limit_self - s80d_self:,.0f}. Buy/upgrade health insurance before March 31."))
        
        if nps_employer == 0 and u_employment == "Salaried":
            tips.append(("Request NPS employer contribution",
                          "Ask employer to contribute to NPS instead of CTC component. Exempt u/s 80CCD(2) in BOTH regimes."))
        
        if int_234b > 0:
            tips.append(("Pay Advance Tax to avoid 234B interest",
                          f"Pay advance tax quarterly. Estimated 234B interest this year: ₹{int_234b:,.0f}"))
        
        if not tips:
            tips.append(("Tax computation is optimized",
                          "No major gaps identified. Review annually as income changes."))
        
        for title, desc in tips:
            st.markdown(f"""
            <div class="tip-box">
            <strong>💡 {title}</strong><br>{desc}
            </div>
            """, unsafe_allow_html=True)
    
    # DISCLAIMER
    st.markdown("""
    <div class="disclaimer">
    ⚠️ <strong>Disclaimer:</strong> This computation is for advisory/planning purposes only. 
    Actual tax liability may differ based on specific facts, applicable deductions, AO assessments, 
    and changes in law. This tool does not constitute professional tax advice. Consult 
    <strong>S P C A & Co, Chartered Accountants</strong> for filing and litigation support.<br>
    Prepared using law applicable to Indian residents as on date. Subject to change per Finance Acts.
    </div>
    """, unsafe_allow_html=True)
    
    # PDF GENERATION
    def create_professional_pdf():
        pdf = FPDF()
        pdf.add_page()
        pdf.set_margins(15, 15, 15)
        
        # Header with branding
        pdf.set_fill_color(15, 37, 87)
        pdf.rect(0, 0, 210, 40, 'F')
        pdf.set_font("helvetica", 'B', 18)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(15, 8)
        pdf.cell(180, 10, "S P C A & Co, Chartered Accountants", ln=True, align='C')
        pdf.set_font("helvetica", '', 10)
        pdf.set_xy(15, 20)
        pdf.cell(180, 6, "Bhubaneswar, Odisha | www.caspca.net | +91 9692156373 | info@caspca.net", ln=True, align='C')
        pdf.set_xy(15, 28)
        pdf.set_font("helvetica", 'B', 11)
        pdf.set_text_color(245, 158, 11)
        pdf.cell(180, 8, f"INCOME TAX COMPUTATION STATEMENT — {selected_year}", ln=True, align='C')
        
        # Client Info Box
        pdf.set_xy(15, 48)
        pdf.set_fill_color(239, 246, 255)
        pdf.set_draw_color(30, 58, 138)
        pdf.set_line_width(0.5)
        pdf.rect(15, 45, 180, 22, 'FD')
        pdf.set_text_color(15, 37, 87)
        pdf.set_font("helvetica", 'B', 11)
        pdf.set_xy(18, 48)
        pdf.cell(85, 7, f"Client: {u_name}", ln=False)
        pdf.cell(85, 7, f"PAN: {u_pan}", ln=True)
        pdf.set_xy(18, 55)
        pdf.set_font("helvetica", '', 10)
        pdf.cell(85, 7, f"Assessment Year: {selected_year.replace('FY ', 'AY ').replace('2025-26','2026-27').replace('2026-27','2027-28')}", ln=False)
        pdf.cell(85, 7, f"Regime: {chosen}", ln=True)
        
        pdf.ln(12)
        
        def section_header(title):
            pdf.set_fill_color(15, 37, 87)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("helvetica", 'B', 10)
            pdf.cell(0, 8, f"  {title}", ln=True, fill=True)
            pdf.set_text_color(30, 41, 59)
        
        def data_row(label, amount, bold=False):
            pdf.set_font("helvetica", 'B' if bold else '', 9)
            if bold:
                pdf.set_fill_color(219, 234, 254)
                pdf.cell(130, 7, f"  {label}", 1, fill=True)
                pdf.cell(50, 7, f"Rs.{amount:,.0f}", 1, ln=True, align='R')
            else:
                pdf.set_fill_color(255, 255, 255)
                pdf.cell(130, 6, f"  {label}", 1)
                pdf.cell(50, 6, f"Rs.{amount:,.0f}", 1, ln=True, align='R')
        
        # I. Income Heads
        section_header("I. INCOME FROM ALL HEADS")
        data_row("Gross Salary Income", salary_gross)
        data_row("Less: Exemptions (HRA/Gratuity/Leave Enc/LTA)", -total_exemptions)
        data_row("Less: NPS Employer Contribution u/s 80CCD(2)", -nps_emp_exempt)
        data_row("Income from House Property", hp_net)
        data_row("Income from Business/Profession", biz_net)
        data_row("STCG (slab rate) + Other Sources", stcg_other + other_slab)
        data_row("Special Rate Income (Crypto/Lottery @ 30%)", special_income)
        data_row("STCG u/s 111A @ 20%", stcg_111a)
        data_row("LTCG u/s 112A @ 12.5%", ltcg_112a)
        data_row("LTCG u/s 112 @ 20%", ltcg_112)
        data_row("GROSS TOTAL INCOME", gti, bold=True)
        
        pdf.ln(3)
        
        # II. Old vs New comparison
        section_header("II. REGIME COMPARISON SUMMARY")
        pdf.set_font("helvetica", 'B', 9)
        pdf.set_fill_color(30, 58, 138)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(100, 7, "  Particulars", 1, fill=True)
        pdf.cell(40, 7, "Old Regime", 1, align='C', fill=True)
        pdf.cell(40, 7, "New Regime", 1, align='C', ln=True, fill=True)
        
        pdf.set_text_color(30, 41, 59)
        rows = [
            ("Standard Deduction", old_std_ded, new_std_ded),
            ("Chapter VI-A Deductions", total_old_ded, 0),
            ("Net Taxable Income (Slab)", old_slab_income, new_slab_income),
            ("Base Tax", old_base_tax, new_base_tax),
            ("Surcharge", old_surcharge, new_surcharge),
            ("CG + Special Tax", cg_tax + old_special_tax, cg_tax + new_special_tax),
            ("H&EC Cess @ 4%", old_total_before_cess * 0.04, new_total_before_cess * 0.04),
            ("TOTAL TAX LIABILITY", old_total, new_total),
        ]
        
        for label, old_v, new_v in rows:
            bold = "TOTAL" in label
            pdf.set_font("helvetica", 'B' if bold else '', 9)
            if bold:
                pdf.set_fill_color(219, 234, 254)
                pdf.cell(100, 7, f"  {label}", 1, fill=True)
                pdf.cell(40, 7, f"Rs.{old_v:,.0f}", 1, align='R', fill=True)
                pdf.cell(40, 7, f"Rs.{new_v:,.0f}", 1, align='R', ln=True, fill=True)
            else:
                pdf.set_fill_color(248, 250, 252)
                pdf.cell(100, 6, f"  {label}", 1, fill=True)
                pdf.cell(40, 6, f"Rs.{old_v:,.0f}", 1, align='R')
                pdf.cell(40, 6, f"Rs.{new_v:,.0f}", 1, align='R', ln=True)
        
        pdf.ln(3)
        
        # III. Final Position
        section_header("III. FINAL TAX LIABILITY & PAYMENT POSITION")
        data_row(f"Total Tax Liability ({chosen})", final_tax, bold=True)
        data_row("Less: TDS on Salary", tds_salary)
        data_row("Less: TDS on Other Income", tds_other)
        data_row("Less: Advance Tax Paid", advance_tax)
        data_row("Less: Self-Assessment Tax", self_assessment)
        data_row("Less: TCS Credit", tcs_credit)
        data_row("Add: Interest u/s 234A", int_234a)
        data_row("Add: Interest u/s 234B (Approx.)", int_234b)
        
        if net_payable > 0:
            data_row("NET AMOUNT PAYABLE", net_payable, bold=True)
            pdf.set_font("helvetica", 'I', 9)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 6, f"  In Words: {words_amount(int(net_payable))}", ln=True)
        else:
            data_row("NET REFUND DUE", net_refund, bold=True)
        
        pdf.ln(3)
        
        # IV. Exemption Logic
        section_header("IV. EXEMPTION CALCULATION DETAILS")
        pdf.set_font("helvetica", '', 9)
        pdf.set_text_color(30, 41, 59)
        pdf.multi_cell(0, 6, f"HRA (Sec 10(13A)): Rs.{hra_ex:,.0f}\n{hra_log.replace('₹','Rs.')}")
        pdf.multi_cell(0, 6, f"\nGratuity (Sec 10(10)): Rs.{gra_ex:,.0f}\n{gra_log.replace('₹','Rs.')}")
        pdf.multi_cell(0, 6, f"\nLeave Encashment (Sec 10(10AA)): Rs.{le_ex:,.0f}\n{le_log.replace('₹','Rs.')}")
        pdf.multi_cell(0, 6, f"\nCommuted Pension (Sec 10(10A)): Rs.{pen_ex:,.0f}\n{pen_log.replace('₹','Rs.')}")
        
        # Footer
        pdf.set_y(-25)
        pdf.set_fill_color(241, 245, 249)
        pdf.rect(0, pdf.get_y(), 210, 25, 'F')
        pdf.set_font("helvetica", 'I', 8)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(0, 5, "DISCLAIMER: This computation is for advisory/planning purposes. Actual liability may differ. Not a substitute for professional advice.", ln=True, align='C')
        pdf.cell(0, 5, f"Prepared by: S P C A & Co, Chartered Accountants, Bhubaneswar | www.caspca.net | Dated: {date.today().strftime('%d-%b-%Y')}", ln=True, align='C')
        pdf.cell(0, 5, "Subject to changes in Income Tax Act, Finance Act provisions and CBDT circulars.", ln=True, align='C')
        
        return bytes(pdf.output())
    
    # DOWNLOAD BUTTONS
    st.markdown('<div class="section-header">📥 Download Reports</div>', unsafe_allow_html=True)
    
    col_dl1, col_dl2, col_dl3 = st.columns(3)
    
    with col_dl1:
        try:
            pdf_bytes = create_professional_pdf()
            st.download_button(
                label="📄 Download Full PDF Report",
                data=pdf_bytes,
                file_name=f"TaxComp_{u_pan or 'Client'}_{selected_year}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"PDF Error: {e}")
    
    with col_dl2:
        # Excel Export
        import io
        output = io.BytesIO()
        
        df_export = pd.DataFrame({
            "Particulars": [
                "Client Name", "PAN", "Financial Year", "Assessment Year",
                "Gross Total Income", "Optimal Regime", "Total Tax",
                "TDS/Advance Tax Paid", "Net Payable", "Net Refund"
            ],
            "Value": [
                u_name, u_pan, selected_year,
                selected_year.replace("FY 2025-26", "AY 2026-27").replace("FY 2026-27", "AY 2027-28"),
                gti, chosen, final_tax,
                total_paid, net_payable, net_refund
            ]
        })
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_export.to_excel(writer, sheet_name="Summary", index=False)
            pd.DataFrame(final_data).to_excel(writer, sheet_name="Detailed Computation", index=False)
        
        st.download_button(
            label="📊 Download Excel Report",
            data=output.getvalue(),
            file_name=f"TaxComp_{u_pan or 'Client'}_{selected_year}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    
    with col_dl3:
        # WhatsApp Summary
        wa_text = (
            f"📊 *Tax Computation Summary*\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"👤 *{u_name}* | {u_pan}\n"
            f"📅 *{selected_year}*\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"💰 GTI: ₹{gti:,.0f}\n"
            f"🏆 Best Regime: *{chosen}*\n"
            f"💸 Tax Liability: ₹{final_tax:,.0f}\n"
            f"✅ Taxes Paid: ₹{total_paid:,.0f}\n"
            f"{'🔴 Payable: ₹' + str(f'{net_payable:,.0f}') if net_payable > 0 else '🟢 Refund: ₹' + str(f'{net_refund:,.0f}')}\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"📞 S P C A & Co: +91 9692156373\n"
            f"🌐 www.caspca.net"
        )
        st.download_button(
            label="📱 Download WhatsApp Summary",
            data=wa_text,
            file_name=f"TaxSummary_{u_pan or 'Client'}.txt",
            mime="text/plain",
            use_container_width=True
        )

# =============================================================================
# FOOTER
# =============================================================================
st.markdown("""
<div class="firm-footer">
    <strong>S P C A & Co, Chartered Accountants</strong> &nbsp;|&nbsp; 
    Bhubaneswar, Odisha &nbsp;|&nbsp;
    <a href="http://www.caspca.net" target="_blank">www.caspca.net</a> &nbsp;|&nbsp;
    📞 +91 9692156373 &nbsp;|&nbsp;
    ✉️ info@caspca.net<br><br>
    <em>Providing quality CA services in GST, Income Tax, Audit, Corporate Compliance & Project Finance</em>
</div>
""", unsafe_allow_html=True)