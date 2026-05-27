import streamlit as st
import pandas as pd
import os
from datetime import datetime, date
from streamlit_gsheets import GSheetsConnection


conn = st.connection("gsheets", type=GSheetsConnection)

EXPECTED_COLS = ["Date", "Customer", "Payment", "Brand", "Category", "Item",
                 "Before Amt", "Purchase Qty", "Pur Price", "Sale Qty", "Sale Price",
                 "Stock", "Balance", "Other Income", "Expense"]


def clear_data_cache():
    st.cache_data.clear()


def update_admin_password(new_password):
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    if not os.path.exists(secrets_path):
        raise RuntimeError(
            "Password changes are disabled on hosted deployments. "
            "Update admin_password in your hosting secret manager instead."
        )

    password_line = f'admin_password = "{new_password}"'

    with open(secrets_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    replaced = False
    for i, line in enumerate(lines):
        if line.strip().startswith("admin_password"):
            lines[i] = password_line
            replaced = True
            break

    if not replaced:
        lines.insert(0, password_line)

    with open(secrets_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


def get_worksheet():
    return conn.client._select_worksheet(
        spreadsheet=conn.client._spreadsheet,
        worksheet=conn.client._worksheet
    )


def as_sheet_value(value):
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    return value


def recalculate_items_in_df(all_df, items):
    numeric_cols = ["Before Amt", "Purchase Qty", "Pur Price", "Sale Qty", "Stock", "Balance"]
    for col in numeric_cols:
        if col in all_df.columns:
            all_df[col] = pd.to_numeric(all_df[col], errors="coerce").fillna(0.0)

    for item_name in items:
        if not item_name or str(item_name).strip() == "-":
            continue

        item_mask = all_df["Item"] == item_name
        running_stock = 0.0

        for idx in all_df.index[item_mask]:
            p_qty = float(all_df.at[idx, "Purchase Qty"] or 0)
            s_qty = float(all_df.at[idx, "Sale Qty"] or 0)
            p_pr = float(all_df.at[idx, "Pur Price"] or 0)
            existing_stock = float(all_df.at[idx, "Stock"] or 0)
            existing_balance = float(all_df.at[idx, "Balance"] or 0)

            # Rows entered directly in Google Sheets can represent opening stock.
            # Keep that stock as the running balance when no purchase/sale happened.
            if p_qty == 0 and s_qty == 0 and existing_stock > 0:
                all_df.at[idx, "Before Amt"] = running_stock
                all_df.at[idx, "Stock"] = existing_stock
                if p_pr > 0:
                    all_df.at[idx, "Balance"] = existing_stock * p_pr
                else:
                    all_df.at[idx, "Balance"] = existing_balance
                running_stock = existing_stock
                continue

            before_amt = running_stock
            after_stock = max((before_amt + p_qty) - s_qty, 0)
            balance = after_stock * p_pr if p_pr > 0 else 0

            all_df.at[idx, "Before Amt"] = before_amt
            all_df.at[idx, "Stock"] = after_stock
            all_df.at[idx, "Balance"] = balance

            running_stock = after_stock

    return all_df


# ၂။ Data ဖတ်ရန် function (SQLite အစား Cloud ကနေ ဖတ်မည်)
def load_data():
    try:
        # ttl="0" သည် data ကို cache မလုပ်ဘဲ အမြဲ fresh ဖြစ်စေရန်ဖြစ်သည်
        df = conn.read(ttl=60) 
        
        if df is not None and not df.empty:
            # Date column ကို datetime format ပြောင်းခြင်း
            df['Date'] = pd.to_datetime(df['Date']).dt.date
            # Date အလိုက် အသစ်ဆုံးကို အပေါ်ကပြရန် Sort လုပ်ခြင်း
            return df.sort_values(by=['Date'], ascending=[False])
        
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading data from Google Sheets: {e}")
        return pd.DataFrame()


# AA-1 >>> Page Setup -----
try:
    from assets import LOGO_DATA
    logo_url = f"data:image/png;base64,{LOGO_DATA}"
    st.set_page_config(layout="wide", page_title="YW Trading", page_icon=logo_url)
except ImportError:
    st.set_page_config(layout="wide", page_title="YW Trading")
    # Cloud ပေါ်မှာ Assets folder မပါရင် warning မပြဘဲ ငြိမ်နေစေချင်ရင် အောက်ကစာကြောင်းကို comment ပိတ်ထားနိုင်ပါတယ်
    # st.warning("⚠️ Logo file NOT found")

# AA_2 >>> CSS -----
st.markdown("""
    <style>
    /* ၁။ App တစ်ခုလုံးရဲ့ Background ကို ဖြူစင်သောအရောင် ထားခြင်း */
    .stApp {
        background-color: #FFFFFF !important;
    }
    /* Login ခလုတ်ကို အပြာရောင်ပြောင်းရန် */
    div.stButton > button:first-child[kind="primary"] {
        background-color: #007bff !important;
        border-color: #007bff !important;
        color: white !important;
    }
    div.stButton > button:hover {
        background-color: #0056b3 !important;
        border-color: #0056b3 !important;
    }
    .sidebar-bottom-spacer {
        height: calc(100vh - 560px);
        min-height: 180px;
    }
    .mobile-bottom-nav {
        display: none;
    }
    .mobile-page-anchor {
        scroll-margin-top: 1rem;
    }
    @media (max-width: 640px) {
        .block-container {
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
            padding-top: 1rem !important;
            padding-bottom: 6.5rem !important;
        }
        [data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
        }
        [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
            gap: 0.75rem !important;
        }
        div.stButton > button {
            min-height: 44px !important;
            white-space: normal !important;
        }
        [data-testid="stDataFrame"],
        [data-testid="stDataEditor"] {
            overflow-x: auto !important;
        }
        .mobile-app-title {
            display: block !important;
            font-size: 1.35rem;
            font-weight: 800;
            color: #111827;
            padding: 0.35rem 0 0.75rem 0;
            text-align: center;
        }
        .mobile-bottom-nav {
            position: fixed;
            left: 0.75rem;
            right: 0.75rem;
            bottom: 0.75rem;
            z-index: 999999;
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.35rem;
            padding: 0.65rem 0.5rem;
            background: rgba(255, 255, 255, 0.96);
            border: 1px solid #e5e7eb;
            border-radius: 22px;
            box-shadow: 0 10px 28px rgba(15, 23, 42, 0.16);
            backdrop-filter: blur(10px);
        }
        .mobile-bottom-nav a {
            color: #6b7280 !important;
            text-decoration: none !important;
            text-align: center;
            font-size: 0.74rem;
            font-weight: 700;
            line-height: 1.1;
            padding: 0.35rem 0.15rem;
            border-radius: 14px;
        }
        .mobile-bottom-nav a span {
            display: block;
            font-size: 1.15rem;
            margin-bottom: 0.18rem;
        }
        .mobile-bottom-nav a.active {
            color: #f59e0b !important;
            background: #fff7ed;
        }
        div[data-testid="stVerticalBlock"] > div:has(.mobile-nav-marker) + div[data-testid="stHorizontalBlock"] {
            position: fixed;
            left: 0.75rem;
            right: 0.75rem;
            bottom: 0.75rem;
            z-index: 999999;
            display: grid !important;
            grid-template-columns: repeat(3, 1fr);
            gap: 0.35rem;
            padding: 0.65rem 0.5rem;
            background: rgba(255, 255, 255, 0.96);
            border: 1px solid #e5e7eb;
            border-radius: 22px;
            box-shadow: 0 10px 28px rgba(15, 23, 42, 0.16);
            backdrop-filter: blur(10px);
        }
        div[data-testid="stVerticalBlock"] > div:has(.mobile-nav-marker) + div[data-testid="stHorizontalBlock"] [data-testid="column"] {
            width: auto !important;
            flex: 1 1 0 !important;
        }
        div[data-testid="stVerticalBlock"] > div:has(.mobile-nav-marker) + div[data-testid="stHorizontalBlock"] button {
            min-height: 3.25rem !important;
            border-radius: 14px !important;
            white-space: pre-line !important;
            font-size: 0.78rem !important;
            font-weight: 700 !important;
            line-height: 1.15 !important;
            padding: 0.25rem !important;
        }
        div[data-testid="stVerticalBlock"] > div:has(.mobile-nav-marker) + div[data-testid="stHorizontalBlock"] button[kind="secondary"] {
            background: #ffffff !important;
            border-color: transparent !important;
            color: #6b7280 !important;
        }
        div[data-testid="stVerticalBlock"] > div:has(.mobile-nav-marker) + div[data-testid="stHorizontalBlock"] button[kind="primary"] {
            background: #fff7ed !important;
            border-color: #fed7aa !important;
            color: #f59e0b !important;
        }
        div.element-container:has(.mobile-nav-marker) {
            display: none !important;
        }
        div.element-container:has(.mobile-nav-marker) + div[data-testid="stHorizontalBlock"],
        div.element-container:has(.mobile-nav-marker) + div.element-container,
        div.element-container:has(.mobile-nav-marker) + div.element-container div[data-testid="stHorizontalBlock"] {
            position: fixed !important;
            left: 0.75rem !important;
            right: 0.75rem !important;
            bottom: 0.75rem !important;
            z-index: 999999 !important;
            display: grid !important;
            grid-template-columns: repeat(3, 1fr) !important;
            gap: 0.35rem !important;
            padding: 0.65rem 0.5rem !important;
            background: rgba(255, 255, 255, 0.96) !important;
            border: 1px solid #e5e7eb !important;
            border-radius: 22px !important;
            box-shadow: 0 10px 28px rgba(15, 23, 42, 0.16) !important;
            backdrop-filter: blur(10px) !important;
        }
        div.element-container:has(.mobile-nav-marker) + div[data-testid="stHorizontalBlock"] [data-testid="column"],
        div.element-container:has(.mobile-nav-marker) + div.element-container [data-testid="column"] {
            width: auto !important;
            flex: 1 1 0 !important;
        }
        div.element-container:has(.mobile-nav-marker) + div[data-testid="stHorizontalBlock"] button,
        div.element-container:has(.mobile-nav-marker) + div.element-container button {
            min-height: 3.25rem !important;
            border-radius: 14px !important;
            white-space: pre-line !important;
            font-size: 0.78rem !important;
            font-weight: 700 !important;
            line-height: 1.15 !important;
            padding: 0.25rem !important;
        }
        div.element-container:has(.mobile-nav-marker) + div[data-testid="stHorizontalBlock"] button[kind="secondary"],
        div.element-container:has(.mobile-nav-marker) + div.element-container button[kind="secondary"] {
            background: #ffffff !important;
            border-color: transparent !important;
            color: #6b7280 !important;
        }
        div.element-container:has(.mobile-nav-marker) + div[data-testid="stHorizontalBlock"] button[kind="primary"],
        div.element-container:has(.mobile-nav-marker) + div.element-container button[kind="primary"] {
            background: #fff7ed !important;
            border-color: #fed7aa !important;
            color: #f59e0b !important;
        }
    }
    @media (min-width: 641px) {
        .mobile-app-title {
            display: none !important;
        }
    }
    </style>
""", unsafe_allow_html=True)

# AA_3 >>> Database Name (Cloud စနစ်တွင် မလိုအပ်တော့ပါ) -----
# DB_NAME = "inventory_mgmt.db"  <-- ဒီစာကြောင်းကို ဖျက်လိုက်ပါ သို့မဟုတ် Comment ပိတ်ပါ
# အစားထိုးရန် မလိုအပ်ပါ။ conn object ကိုသာ တိုက်ရိုက်သုံးပါမည်။

# AA_4 >>> LOGIN SESSION INITIALIZATION ------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "cart" not in st.session_state:
    st.session_state.cart = []

if "show_values" not in st.session_state:
    st.session_state.show_values = False

if "last_updated_item" not in st.session_state:
    st.session_state.last_updated_item = None

# Input fields များအတွက် Session State များ
if "pp" not in st.session_state: st.session_state.pp = 0.0
if "sp" not in st.session_state: st.session_state.sp = 0.0
if "pq" not in st.session_state: st.session_state.pq = 0.0
if "sq" not in st.session_state: st.session_state.sq = 0.0

# Reset trigger (Input များ ရှင်းထုတ်ရန်)
if "reset_trigger" not in st.session_state:
    st.session_state.reset_trigger = False


# BB_1 >>> LOGIN PAGE UI -----
if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center; color: #2e7d32;'>Inventory Login</h2>", unsafe_allow_html=True)
    
    # Login Box ချိန်ညှိခြင်း -----
    _, col_login, _ = st.columns([1, 1.5, 1])
    with col_login:
        with st.container(border=True):
            user_input = st.text_input("Username", value="admin")
            pass_input = st.text_input("Password", type="password", placeholder="000000")
            
            st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
            
            if st.button("Log In", use_container_width=True, type="primary"):

                # Password Format စစ်ဆေးခြင်း -----
                if len(pass_input) == 6 and pass_input.isdigit():
                    
                    # Google Sheets သုံးတဲ့အခါ Password ကို Sheet ထဲကနေ ဖတ်မယ့်အစား
                    # Streamlit Secrets ထဲမှာ သိမ်းထားတာက ပိုလုံခြုံပါတယ်
                    # ဒါမှမဟုတ် အောက်ကအတိုင်း ရိုးရိုးပဲ စစ်လိုက်လို့ ရပါတယ်
                    
                    try:
                        # နည်းလမ်း (၁) - Secrets ထဲမှာ 'admin_password' ဆိုပြီး သိမ်းထားရင် သုံးရန်
                        db_pass = st.secrets.get("admin_password", "123456") 
                    except:
                        # Secrets မသတ်မှတ်ရသေးရင် Default သုံးရန်
                        db_pass = "123456"

                    # Password တိုက်ဆိုင်စစ်ဆေးခြင်း -----
                    if pass_input == db_pass:
                        st.session_state.logged_in = True
                        
                        # Delete လုပ်ချိန်တွင် Password ပြန်စစ်ရန်အတွက် သိမ်းထားခြင်း
                        st.session_state["password"] = pass_input 
                        
                        st.success("Login Success")
                        st.rerun()
                    else:
                        st.error("Wrong Password")
                else:
                    st.warning("⚠️ Password must be 6 digits (0-9) only")
    st.stop()


# CC_1 >>> Database Initialization (Cloud Version) -----
def init_db():
    """
    Google Sheets သုံးလျှင် Local SQLite Table များ ဆောက်ရန် မလိုတော့ပါ။
    သို့သော် Code ထဲတွင် init_db() ခေါ်ထားပါက Error မတက်စေရန် 
    Function ကို အလွတ် (Pass) အနေဖြင့် ထားရှိပါမည်။
    """
    pass

# CC_2 >>> Stock ပြန်လည်တွက်ချက်သည့် Logic (Google Sheets Version) -----
# (ဒီအပိုင်းက သင်ပို့ပေးထားတဲ့အတိုင်း အဆင်ပြေပါတယ်၊ ပြင်ရန်မလိုပါ)
def recalculate_inventory_logic(item_name):
    if not item_name or item_name == "-":
        return

    all_df = conn.read(
        worksheet="inventory",
        ttl=60
    )
    if all_df is None or all_df.empty:
        return

    all_df = recalculate_items_in_df(all_df, [item_name])
    conn.update(data=all_df)
    clear_data_cache()

# CC_3 >>> Full Stock Rebuild (Cloud Version) -----
def rebuild_all_stock():
    """Recalculate all stock values in memory, then update Google Sheets once."""
    all_df = conn.read(ttl=60)
    
    if all_df is None or all_df.empty:
        st.warning("No data found to rebuild.")
        return

    required_cols = ["Item", "Before Amt", "Purchase Qty", "Pur Price", "Sale Qty", "Stock", "Balance"]
    missing_cols = [col for col in required_cols if col not in all_df.columns]
    if missing_cols:
        st.error(f"Missing columns: {', '.join(missing_cols)}")
        return

    items = [item for item in all_df["Item"].dropna().unique() if str(item).strip() != "-"]
    if not items:
        st.warning("No item rows found to rebuild.")
        return

    progress_bar = st.progress(0.0)
    for i, item_name in enumerate(items):
        all_df = recalculate_items_in_df(all_df, [item_name])
        progress_bar.progress((i + 1) / len(items))

    conn.update(data=all_df)
    clear_data_cache()
    
    st.success("✅ Stock အားလုံးကို အောင်မြင်စွာ ပြန်လည်တွက်ချက်ပြီးပါပြီ။")


# DD_1 >>> Google Sheets မှ Data ကို DataFrame အဖြစ် ဖတ်ယူခြင်း -----
def load_data():
    try:
        # ၁။ Google Sheet မှ data ကို cache မလုပ်ဘဲ ဖတ်ယူပါ
        df = conn.read(ttl=60)
        
        if df is not None and not df.empty:
            # ၂။ Column အမည်များ တူညီမှုရှိစေရန် သတ်မှတ်ခြင်း 
            # (Google Sheet တွင် rowid မရှိသဖြင့် Index ကိုသာ ID အဖြစ် သုံးပါမည်)
            # Column ပေါင်း ၁၅ ခု (ID မပါဘဲ)
            expected_cols = ["Date", "Customer", "Payment", "Brand", "Category", "Item", 
                             "Before Amt", "Purchase Qty", "Pur Price", "Sale Qty", "Sale Price", 
                             "Stock", "Balance", "Other Income", "Expense"]
            
            # Column အမည်များ လွဲချော်နေပါက ပြန်ညှိပေးခြင်း
            df.columns = expected_cols
            df["Original_Index"] = df.index
            
            # ၃။ Date format ကို တိကျအောင် ပြောင်းလဲခြင်း
            df['Date'] = pd.to_datetime(df['Date']).dt.date
            
            # ၄။ Stock တွက်ချက်မှု မှန်ကန်စေရန် Date အလိုက် အရင်စီပါ (Old to New)
            df = df.sort_values(
                by=["Date", "Original_Index"],
                ascending=[True, True],
                kind="mergesort"
            ).reset_index(drop=True)
            
            # ၅။ မျက်မြင်ဇယားတွင် အသစ်ဆုံး (နောက်ဆုံးစာရင်း) ကို အပေါ်ဆုံးမှာ ပြချင်ပါက 
            # ဤနေရာတွင် မစီသေးဘဲ UI ပြသခါနီးမှသာ ပြောင်းပြန်စီပေးရပါမည်။
            # သို့မဟုတ် UI အတွက် သီးသန့် return ပြန်ပေးပါမည်။
            return df
            
        else:
            # Data မရှိလျှင် column အလွတ်များဖြင့် DataFrame အသစ်ပြန်ပေးပါ
            cols = ["Date", "Customer", "Payment", "Brand", "Category", "Item", 
                    "Before Amt", "Purchase Qty", "Pur Price", "Sale Qty", "Sale Price", 
                    "Stock", "Balance", "Other Income", "Expense"]
            return pd.DataFrame(columns=cols)

    except Exception as e:
        st.error(f"❌ Data Loading Error: {e}")
        # Error တက်လျှင်လည်း structure မပျက်အောင် column အလွတ်များ ပြန်ပေးပါ
        cols = ["Date", "Customer", "Payment", "Brand", "Category", "Item", 
                "Before Amt", "Purchase Qty", "Pur Price", "Sale Qty", "Sale Price", 
                "Stock", "Balance", "Other Income", "Expense"]
        return pd.DataFrame(columns=cols)

# မျက်လုံးခလုတ် အခြေအနေမှတ်ရန် ------
if "show_values" not in st.session_state:
    st.session_state.show_values = False


# EE_1 >>> စတင် Run ခြင်း (Cloud Version) -----
# init_db() ကို အပေါ်က CC_1 မှာ pass လုပ်ထားခဲ့တဲ့အတွက် error မတက်ဘဲ ကျော်သွားပါလိမ့်မယ်
init_db()

df = load_data()

# Reset Logic (စာရင်းသွင်းပြီးပါက Input Box များ ပြန်ရှင်းရန်) -----
if "reset_trigger" not in st.session_state:
    st.session_state.reset_trigger = False

if st.session_state.reset_trigger:
    # သတ်မှတ်ထားသော key များကို loop ပတ်၍ အလွတ် (သို့မဟုတ်) 0 ပြန်ပြောင်းခြင်း
    keys_to_reset = ["pq", "pp", "sq", "sp", "fi", "fe", "c_name", "p_type_new"]
    for k in keys_to_reset:
        if k in st.session_state:
            # စာသားဖြစ်ပါက အလွတ်၊ ဂဏန်းဖြစ်ပါက 0.0 ထားမည်
            st.session_state[k] = "" if any(word in k for word in ["name", "type"]) else 0.0
            
    # Sidebar Dropdown များကို မူလအတိုင်း ပြန်ထားခြင်း
    dropdown_keys = {
        "b_drop": "Choose Brand",
        "c_drop": "Choose Category",
        "i_drop": "Choose Item",
        "cust_drop": "Choose Customer",
        "pay_drop": "Choose Payment"
    }
    for key, default_val in dropdown_keys.items():
        if key in st.session_state:
            st.session_state[key] = default_val
    
    st.session_state.reset_trigger = False

# EE_2 >>> Receipt UI Function -----
def show_receipt_ui(customer_name, items_list, total_amount):
    from datetime import datetime
    now = datetime.now()
    
    # ဘောင်ချာထဲက ပစ္စည်းစာရင်း HTML Row များ တည်ဆောက်ခြင်း
    rows_html = "".join([f"""
        <tr>
            <td style='padding: 5px 0;'>{i['name']}</td>
            <td style='text-align: center;'>{int(i['qty'])}</td>
            <td style='text-align: right;'>{i['price']:,.0f}</td>
            <td style='text-align: right;'>{i['amount']:,.0f}</td>
        </tr>
    """ for i in items_list])

    # EE_3 >>> Voucher Design (Thermal Printer အတွက်) -----
    # စာလုံးပေါင်းနှင့် ဒီဇိုင်းကို Cloud Version နှင့် အံကိုက်ဖြစ်အောင် ထိန်းထားပါသည်
    receipt_content = f"""
    <div id='print-area' style='width: 300px; font-family: "Courier New", monospace; padding: 10px; color: black;'>
        <div style='text-align: center;'>
            <h3 style='margin: 0;'> YOON WADDY - Skincare </h3>
        </div>
        <hr style='border-top: 1px dashed black;'>
        <div style='font-size: 12px;'>
            <p style='margin: 2px 0;'>Vr. No: {now.strftime('%m%d%Y%H%M%S')}</p>
            <p style='margin: 2px 0;'>Date: {now.strftime('%d/%m/%Y %H:%M:%S')}</p>
            <p style='margin: 2px 0;'>Name: {customer_name}</p>
        </div>
        <hr style='border-top: 1px dashed black;'>
        <table style='width: 100%; font-size: 12px; border-collapse: collapse;'>
            <tr style='border-bottom: 1px solid black;'>
                <th align='left'>ITEM</th>
                <th align='center'>QTY</th>
                <th align='right'>PRICE</th>
                <th align='right'>AMT</th>
            </tr>
            {rows_html}
        </table>
        <hr style='border-top: 1px dashed black;'>
        <div style='font-weight: bold; font-size: 14px; display: flex; justify-content: space-between;'>
            <span>TOTAL:</span><span>{total_amount:,.0f}</span>
        </div>
        <div style='text-align: center; margin-top: 20px; font-size: 10px;'>
            <p>*** Thank You ***</p>
        </div>
    </div>
    """

    # EE_4 >>> JavaScript Print Trigger -----
    # HTML content ကို JavaScript အတွက် ဘေးကင်းအောင် ပြင်ဆင်ခြင်း
    safe_content = receipt_content.replace("\n", "").replace('"', "'")
    
    js_print = f"""
        <script>
        function printVoucher() {{
            var printWindow = window.open('', '', 'width=350,height=600');
            printWindow.document.write('<html><head><title>Print Receipt</title>');
            printWindow.document.write('<style>@page {{ size: auto; margin: 0mm; }} body {{ margin: 10px; }}</style>');
            printWindow.document.write('</head><body>');
            printWindow.document.write("{safe_content}");
            printWindow.document.write('</body></html>');
            printWindow.document.close();
            printWindow.focus();
            setTimeout(function() {{ printWindow.print(); printWindow.close(); }}, 500);
        }}
        printVoucher();
        </script>
    """
    st.components.v1.html(js_print, height=0)

        
# FF-1 >>> Sidebar (Fixing Logic & Cloud Version) -----
st.sidebar.write("### ⚙️ Setting")
if not df.empty:
    with st.sidebar.expander("Edit Names", expanded=False):
        edit_reset_key = st.session_state.get("edit_names_reset_key", 0)
        edit_type = st.radio("What to change?", ["Brand", "Category", "Item", "Customer", "Payment"], key=f"side_edit_type_{edit_reset_key}")
        
        # Group Selection -----
        if edit_type in ["Brand", "Category", "Item"]:
            sel_b = st.selectbox("Select Brand", options=sorted(df["Brand"].unique()), key=f"edit_sel_b_{edit_reset_key}")
            cat_list = sorted(df[df["Brand"] == sel_b]["Category"].unique())
            sel_c = st.selectbox("Select Category", options=cat_list, key=f"edit_sel_c_{edit_reset_key}")
            
            if edit_type == "Brand":
                current_list = [sel_b]
            elif edit_type == "Category":
                current_list = [sel_c]
            else: # Item
                current_list = sorted(df[(df["Brand"] == sel_b) & (df["Category"] == sel_c)]["Item"].unique())
        else:
            current_list = sorted([str(x) for x in df[edit_type].unique() if str(x) not in ["-", "0", "nan", ""]])

        # FF_2 >>> Cloud Update Logic -----
        if current_list:
            old_val = st.selectbox(f"Select existing {edit_type}", options=current_list, key=f"side_old_val_{edit_reset_key}")
            new_val = st.text_input(f"New name for {old_val}", key=f"side_new_val_{edit_reset_key}")
            
            if st.button(f"Update {edit_type}", type="primary", use_container_width=True, key=f"update_name_{edit_reset_key}"):
                if old_val and new_val and old_val != new_val:
                    try:
                        # ၁။ လက်ရှိ data အားလုံးကို ဖတ်ပါ
                        all_df = conn.read(ttl=60)
                        
                        # ၂။ သက်ဆိုင်ရာ Row များကို ရှာဖွေပြီး အမည်သစ်ဖြင့် အစားထိုးပါ
                        if edit_type == "Category":
                            mask = (all_df["Brand"] == sel_b) & (all_df["Category"] == old_val)
                        elif edit_type == "Item":
                            mask = (all_df["Brand"] == sel_b) & (all_df["Category"] == sel_c) & (all_df["Item"] == old_val)
                        else:
                            mask = all_df[edit_type] == old_val
                        
                        all_df.loc[mask, edit_type] = new_val
                        
                        # ၃။ Cloud ပေါ်သို့ Update လုပ်ပါ
                        # ၄။ Item အမည်ပြောင်းလဲခြင်းဖြစ်ပါက Stock များကို ပြန်ညှိပါ
                        if edit_type == "Item":
                            all_df = recalculate_items_in_df(all_df, [new_val])

                        conn.update(data=all_df)
                        clear_data_cache()
                        
                        st.success(f"✅ Updated {edit_type} to '{new_val}'!")
                        st.session_state.edit_names_reset_key = edit_reset_key + 1
                        st.session_state.reset_trigger = True
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Error: {e}")
                else:
                    st.warning("⚠️ နာမည်အသစ် ရိုက်ထည့်ပေးပါ။")

# FF_3 >>> Cloud Security Section (Using Secrets Note) -----
with st.sidebar:
    with st.expander("Security"):
        current_pw = st.session_state.get("password", st.secrets.get("admin_password", "123456"))
        old_pw = st.text_input("Current Password", type="password", key="security_old_pw")
        new_pw = st.text_input("New Password", type="password", key="security_new_pw")
        confirm_pw = st.text_input("Confirm New Password", type="password", key="security_confirm_pw")

        if st.button("Change Password", use_container_width=True, type="primary", key="change_admin_password"):
            if old_pw != current_pw:
                st.error("Wrong current password")
            elif len(new_pw) != 6 or not new_pw.isdigit():
                st.warning("Password must be 6 digits")
            elif new_pw != confirm_pw:
                st.error("New passwords do not match")
            else:
                try:
                    update_admin_password(new_pw)
                    st.session_state["password"] = new_pw
                    st.success("Password changed successfully")
                except Exception as e:
                    st.error(f"Password update error: {e}")

# FF_4 >>> Emergency Stock Repair -----
with st.sidebar:
    st.markdown('<div class="sidebar-bottom-spacer"></div>', unsafe_allow_html=True)
    st.markdown("---")
    if st.button("Rebuild All Stocks", use_container_width=True):
        with st.spinner("🔄 စာရင်းအားလုံးကို ပြန်လည်တွက်ချက်နေပါသည်..."):
            rebuild_all_stock()
        st.success("All stock rebuilt successfully.")
        st.rerun()

# FF_5 >>> Sidebar Logout Section ------
with st.sidebar:
    if st.button("Log Out", use_container_width=True, type="primary"):
        st.session_state.logged_in = False
        st.session_state.cart = []
        st.rerun()

st.components.v1.html("""
<script>
(function () {
  const doc = window.parent.document;
  const navId = "yw-mobile-bottom-nav";
  const styleId = "yw-mobile-bottom-nav-style";
  const pages = ["dashboard", "new", "history"];
  let activePage = window.parent.sessionStorage.getItem("yw_mobile_page") || "dashboard";

  function installStyle() {
    if (doc.getElementById(styleId)) return;
    const style = doc.createElement("style");
    style.id = styleId;
    style.textContent = `
      #${navId} { display: none; }
      @media (max-width: 640px) {
        #${navId} {
          position: fixed;
          left: 0.75rem;
          right: 0.75rem;
          bottom: 0.75rem;
          z-index: 2147483647;
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 0.35rem;
          padding: 0.65rem 0.5rem;
          background: rgba(255,255,255,0.96);
          border: 1px solid #e5e7eb;
          border-radius: 22px;
          box-shadow: 0 10px 28px rgba(15,23,42,0.16);
          backdrop-filter: blur(10px);
        }
        #${navId} button {
          min-height: 3.25rem;
          border: 0;
          border-radius: 14px;
          background: #fff;
          color: #6b7280;
          font-size: 0.74rem;
          font-weight: 800;
          line-height: 1.15;
          white-space: pre-line;
        }
        #${navId} button.active {
          background: #fff7ed;
          color: #f59e0b;
          border: 1px solid #fed7aa;
        }
        section.main .block-container,
        div[data-testid="stAppViewContainer"] .block-container {
          padding-bottom: 6.5rem !important;
        }
      }
    `;
    doc.head.appendChild(style);
  }

  function ensureNav() {
    let nav = doc.getElementById(navId);
    if (nav) return nav;
    nav = doc.createElement("nav");
    nav.id = navId;
    nav.setAttribute("aria-label", "Mobile bottom navigation");
    nav.innerHTML = `
      <button type="button" data-page="dashboard">D\nDashboard</button>
      <button type="button" data-page="new">+\nNew</button>
      <button type="button" data-page="history">H\nHistory</button>
    `;
    doc.body.appendChild(nav);
    nav.querySelectorAll("button").forEach((button) => {
      button.addEventListener("click", () => {
        activePage = button.dataset.page;
        window.parent.sessionStorage.setItem("yw_mobile_page", activePage);
        applyMode();
        window.parent.scrollTo({ top: 0, behavior: "smooth" });
      });
    });
    return nav;
  }

  function markerContainer(section) {
    const marker = doc.querySelector(`.mobile-section-marker[data-section="${section}"]`);
    if (!marker) return null;
    return marker.closest("div.element-container") || marker.parentElement || marker;
  }

  function sectionElements(section) {
    const start = markerContainer(section);
    if (!start) return [];
    const ordered = pages.map(markerContainer).filter(Boolean);
    const currentIndex = ordered.indexOf(start);
    const next = ordered[currentIndex + 1] || null;
    const elements = [];
    let node = start;
    while (node && node !== next) {
      elements.push(node);
      node = node.nextElementSibling;
    }
    return elements;
  }

  function setVisible(nodes, visible) {
    nodes.forEach((node) => {
      node.style.display = visible ? "" : "none";
    });
  }

  function findText(text) {
    return Array.from(doc.querySelectorAll("p, label, span, div"))
      .find((node) => (node.textContent || "").trim() === text);
  }

  function horizontalBlockFor(label) {
    const labelNode = findText(label);
    return labelNode ? labelNode.closest('div[data-testid="stHorizontalBlock"]') : null;
  }

  function clearPhoneGrid(block) {
    if (!block) return;
    block.style.removeProperty("display");
    block.style.removeProperty("grid-template-columns");
    block.style.removeProperty("gap");
    block.querySelectorAll('[data-testid="column"], div.element-container').forEach((node) => {
      node.style.removeProperty("display");
      node.style.removeProperty("grid-column");
      node.style.removeProperty("width");
      node.style.removeProperty("flex");
    });
  }

  function makePhoneGrid(block) {
    if (!block) return;
    block.style.setProperty("display", "grid", "important");
    block.style.setProperty("grid-template-columns", "minmax(0, 1fr) minmax(0, 1fr)", "important");
    block.style.setProperty("gap", "0.65rem", "important");
    block.querySelectorAll('[data-testid="column"]').forEach((column) => {
      column.style.setProperty("display", "contents", "important");
      column.style.setProperty("width", "auto", "important");
      column.style.setProperty("flex", "initial", "important");
    });
    block.querySelectorAll("div.element-container").forEach((element) => {
      const text = (element.textContent || "").trim();
      const hasButton = !!element.querySelector("button");
      const isSpacer = !text && element.querySelector('[style*="margin-top"]');
      if (isSpacer) {
        element.style.setProperty("display", "none", "important");
      }
      if (hasButton) {
        element.style.setProperty("grid-column", "1 / -1", "important");
      }
    });
  }

  function applyPhoneFieldRows(isMobile) {
    const blocks = [
      horizontalBlockFor("Dash Start Date"),
      horizontalBlockFor("Purchase Qty"),
      horizontalBlockFor("Start Date")
    ].filter(Boolean);

    blocks.forEach((block) => {
      if (isMobile) {
        makePhoneGrid(block);
      } else {
        clearPhoneGrid(block);
      }
    });
  }

  function applyMode() {
    const isMobile = window.parent.matchMedia("(max-width: 640px)").matches;
    const nav = ensureNav();
    nav.querySelectorAll("button").forEach((button) => {
      button.classList.toggle("active", button.dataset.page === activePage);
    });
    pages.forEach((page) => {
      setVisible(sectionElements(page), !isMobile || page === activePage);
    });
    applyPhoneFieldRows(isMobile);
  }

  installStyle();
  ensureNav();
  applyMode();
  window.parent.addEventListener("resize", applyMode);
  setTimeout(applyMode, 500);
  setTimeout(applyMode, 1500);
  setTimeout(applyMode, 3000);
})();
</script>
""", height=0)

# GG_1>>> Dashboard Area -----
st.markdown('<div id="dashboard" class="mobile-page-anchor mobile-section-marker" data-section="dashboard"></div>', unsafe_allow_html=True)

# --- Dashboard Metric Box များအတွက် CSS Styling ---
st.markdown("""
    <style>
    /* Metric Box များကို ပိုမိုလှပအောင် ပြုပြင်ခြင်း */
    [data-testid="stMetric"] {
        background-color: #ffffff !important;
        border-left: 6px solid #00bcd4 !important;
        padding: 15px !important;
        border-radius: 10px !important;
        box-shadow: 2px 2px 8px rgba(0,0,0,0.05) !important;
    }

    .stApp {
        background-color: #ffffff !important;
    }

    div.stButton > button[kind="primary"] { background-color: #007bff !important; color: white !important; }
    div.stButton > button[kind="secondary"] { background-color: #ff4b4b !important; color: white !important; }
    </style>
""", unsafe_allow_html=True)

st.write("<h2 style='text-align: left; color: #000000;'> 📊 Yoon Waddy Dashboard</h2>", unsafe_allow_html=True)

with st.container(border=True):
    dash_col1, dash_col2, dash_col3 = st.columns([2, 2, 2])
    d_start = dash_col1.date_input("Dash Start Date", value=date.today(), key="ds_key")
    d_end = dash_col2.date_input("Dash End Date", value=date.today(), key="de_key")
    dash_col3.markdown('<div style="margin-top: 28px;"></div>', unsafe_allow_html=True)

    if dash_col3.button("🔍 Search Dash", use_container_width=True, type="primary"):
        st.rerun()

    # --- Filter Logic ---
    # df ကို load_data() ကနေ Date အလိုက် Ascending စီပြီးသား အခြေအနေမှာ သုံးပါမယ်
    mask = (df["Date"] >= d_start) & (df["Date"] <= d_end)
    f_df = df.loc[mask]

    # တွက်ချက်မှုများ (ရွေးချယ်ထားသော ရက်စွဲအတွင်း)
    t_pur = (f_df["Purchase Qty"] * f_df["Pur Price"]).sum()
    t_sales = (f_df["Sale Qty"] * f_df["Sale Price"]).sum()
    t_inc = f_df["Other Income"].sum()
    t_exp = f_df["Expense"].sum()
    total_profit = t_sales - t_pur # အခြေခံအမြတ်တွက်နည်း

    # Stock Balance Value (လက်ကျန်ပစ္စည်းတန်ဖိုး) Cloud Version ---
    if not df.empty:
        # ID မရှိသဖြင့် DataFrame ၏ Row အစီအစဉ်အတိုင်း နောက်ဆုံး Row ကို ယူပါမည်
        # load_data တွင် Date အလိုက် စီထားပြီးဖြစ်သဖြင့် tail(1) သည် နောက်ဆုံးစာရင်း ဖြစ်ပါသည်
        current_balance = df.groupby('Item').tail(1)['Balance'].sum()
    else:
        current_balance = 0

    # မျက်လုံးခလုတ် (Show/Hide Values) -----
    d_col_title, d_col_eye = st.columns([0.92, 0.08])
    with d_col_eye:
        icon = "👁️" if st.session_state.show_values else "🙈" 
        if st.button(icon, key="dash_eye"):
            st.session_state.show_values = not st.session_state.show_values
            st.rerun()

    # Masking Function -----
    def mask_v(val):
        if st.session_state.get('show_values', False):
            return f"{val:,.0f} THB"
        return "****** THB"

    # Metric များပြသခြင်း -----
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Purchase", mask_v(t_pur))
    m2.metric("Total Sales", mask_v(t_sales))
    m3.metric("Stock Balance Value", mask_v(current_balance))

    s1, s2, s3 = st.columns(3)
    s1.metric("Other Income", mask_v(t_inc))
    s2.metric("Expense", mask_v(t_exp))
    s3.metric("Profit (Sales - Pur)", mask_v(total_profit))

    st.divider()



# HH_1 >>> New Transaction Area -----
st.markdown('<div id="new-transaction" class="mobile-page-anchor mobile-section-marker" data-section="new"></div>', unsafe_allow_html=True)
st.write("#### ➕ New Transaction")
r1_c1, r1_c2, r1_c3 = st.columns([1, 1, 1])

with r1_c1:
    tr_date = st.date_input("Date", date.today(), key="tr_date_key")

with r1_c2:
    cust_list = sorted([str(x) for x in df["Customer"].unique() if str(x) not in ["-", "nan"]]) if not df.empty else []
    c_sel = st.selectbox("Customer Name", ["Choose Customer"] + cust_list + ["+ Add New"], key="cust_drop")
    cust_name = st.text_input("New Customer Name", placeholder="Enter customer name...", key="c_name") if c_sel == "+ Add New" else (c_sel if c_sel != "Choose Customer" else "")

with r1_c3:
    pay_list = sorted([str(x) for x in df["Payment"].unique() if str(x) not in ["-", "nan"]]) if not df.empty else ["Cash", "KPay", "Wave"]
    p_sel = st.selectbox("Payment Method", ["Choose Payment"] + pay_list + ["+ Add New"], key="pay_drop")
    pay_type = st.text_input("New Payment Method", key="p_type_new") if p_sel == "+ Add New" else (p_sel if p_sel != "Choose Payment" else "Cash")

f2, f3, f4 = st.columns(3)
with f2:
    b_list = sorted([str(x) for x in df["Brand"].unique() if str(x) not in ["-", "nan"]]) if not df.empty else []
    b_sel = st.selectbox("Brand", ["Choose Brand"] + b_list + ["+ Add New"], key="b_drop")
    f_brand = st.text_input("New Brand", key="new_b_input") if b_sel == "+ Add New" else (b_sel if b_sel != "Choose Brand" else "")

with f3:
    if f_brand and b_sel != "+ Add New":
        filtered_cats = sorted([str(x) for x in df[df["Brand"] == f_brand]["Category"].unique() if str(x) not in ["-", "nan"]])
    else:
        filtered_cats = []

    is_cat_disabled = (f_brand == "" or b_sel == "Choose Brand")
    c_sel_val = st.selectbox("Category", ["Choose Category"] + filtered_cats + ["+ Add New"], 
                             key="c_drop", 
                             disabled=is_cat_disabled)
    f_cat = st.text_input("New Category", key="new_c_input") if c_sel_val == "+ Add New" else (c_sel_val if c_sel_val != "Choose Category" else "")

with f4:
    if f_cat and c_sel_val != "+ Add New":
        filtered_items = sorted([str(x) for x in df[(df["Brand"] == f_brand) & (df["Category"] == f_cat)]["Item"].unique() if str(x) not in ["-", "nan"]])
    else:
        filtered_items = []

    is_item_disabled = (f_cat == "" or c_sel_val == "Choose Category")
    i_sel = st.selectbox("Item Name", ["Choose Item"] + filtered_items + ["+ Add New"], 
                         key="i_drop", 
                         disabled=is_item_disabled)
    f_item = st.text_input("New Item", key="new_i_input") if i_sel == "+ Add New" else (i_sel if i_sel != "Choose Item" else "")

# --- Stock နှင့် နောက်ဆုံးဈေးနှုန်းများ ရှာဖွေခြင်း (Cloud Version) ---
l_stock, l_price, l_pur_price = 0.0, 0.0, 0.0 

if f_item and f_item not in ["Choose Item", "+ Add New", ""]:
    # ၁။ ရွေးချယ်ထားသော Item နှင့် ကိုက်ညီသည့် Row များကို ရှာပါ
    matched = df[(df["Brand"] == f_brand) & (df["Category"] == f_cat) & (df["Item"] == f_item)]

    if not matched.empty:
        # ၂။ နောက်ဆုံးသွင်းထားသော Record (နောက်ဆုံး Row) ကို ယူပါ
        # load_data() တွင် Date အလိုက် စီထားပြီးဖြစ်သဖြင့် iloc[-1] က အသစ်ဆုံးဖြစ်ပါသည်
        latest_row = matched.iloc[-1]
    
        l_stock = float(latest_row["Stock"])
        l_price = float(latest_row["Sale Price"])
        l_pur_price = float(latest_row["Pur Price"])

# UI ပေါ်တွင် လက်ရှိ Stock ပြသခြင်း
if f_item and f_item not in ["Choose Item", "+ Add New", ""]:
    if l_stock <= 0:
        st.error(f"❌ Current Stock for **{f_item}** : **{l_stock:,.0f}** (Out of Stock)")
    else:
        st.info(f"💡 Current Stock for **{f_item}** : **{l_stock:,.0f}** units")

# အလိုအလျောက် ဈေးနှုန်းဖြည့်ပေးမည့် Logic
def update_input_fields():
    pq = st.session_state.get("pq", 0)
    sq = st.session_state.get("sq", 0)

    if pq > 0:
        st.session_state.pp = float(l_pur_price)
        st.session_state.sp = float(l_price)
    elif sq > 0:
        st.session_state.sp = float(l_price)
        st.session_state.pp = 0.0
    else:
        st.session_state.pp = 0.0
        st.session_state.sp = 0.0


# II_1 >>> Input Sections -----

# Session State ထဲတွင် key များ ရှိမရှိ အရင်စစ်ဆေးပြီး Default သတ်မှတ်ခြင်း
if "pq" not in st.session_state: st.session_state.pq = 0.0
if "sq" not in st.session_state: st.session_state.sq = 0.0
if "pp" not in st.session_state: st.session_state.pp = 0.0
if "sp" not in st.session_state: st.session_state.sp = 0.0

col_p, col_s, col_o = st.columns(3)

with col_p:
    # Purchase Qty: sq (အရောင်း) ရှိနေလျှင် နှိပ်၍မရအောင် ပိတ်ထားမည်
    p_qty = st.number_input(
        "Purchase Qty", 
        min_value=0.0, 
        step=1.0, 
        key="pq", 
        on_change=update_input_fields,
        disabled=(st.session_state.sq > 0)
    )

    # Purchase Price logic: 
    # Purchase Qty (pq) ရှိမှသာ သို့မဟုတ် အသစ်ထည့်ရန်ဖြစ်ပါက ဝယ်ဈေးကို ပြင်ခွင့်ပေးမည်
    pur_price_disabled = (st.session_state.pq <= 0)
    p_pr = st.number_input(
        "Purchase Price (THB)", 
        min_value=0.0, 
        step=1.0, 
        key="pp", 
        disabled=pur_price_disabled
    )

with col_s:
    # Sale Qty: pq (ဝယ်ယူမှု) ရှိနေလျှင် နှိပ်၍မရအောင် ပိတ်ထားမည်
    s_qty = st.number_input(
        "Sale Qty", 
        min_value=0.0, 
        step=1.0, 
        key="sq", 
        on_change=update_input_fields,
        disabled=(st.session_state.pq > 0)
    )

    # Sale Price logic: 
    # ဝယ်ယူမှု (pq) သွင်းနေချိန်တွင်လည်း နောက်နောင်ရောင်းရန် ဈေးနှုန်းသတ်မှတ်နိုင်ရမည်
    # အရောင်း (sq) ရှိနေလျှင်လည်း ဈေးနှုန်းပြင်နိုင်ရမည်
    sale_price_disabled = (st.session_state.pq <= 0 and st.session_state.sq <= 0)
    s_pr = st.number_input(
        "Sale Price (THB)", 
        min_value=0.0, 
        step=1.0, 
        key="sp",
        disabled=sale_price_disabled
    )

with col_o:
    f_inc_val = st.number_input("Other Income", min_value=0.0, step=1.0, key="fi")
    f_exp_val = st.number_input("Expense", min_value=0.0, step=1.0, key="fe")


# JJ_1 >>> Saving Logic (Google Sheets Version) -----
if st.button("Save Transaction", use_container_width=True, type="primary"):
    # ၁။ အရောင်းသွင်းလျှင် Stock ရှိမရှိ အရင်စစ်မည်
    if s_qty > 0 and l_stock < s_qty:
        st.error(f"❌ လက်ကျန် Stock ({l_stock:,.0f}) ထက် ပိုရောင်း၍မရပါ။")
        st.stop()

    # ၂။ အနှုတ်ဂဏန်းများ မဝင်အောင် ကာကွယ်ခြင်း
    if p_qty < 0 or s_qty < 0 or f_inc_val < 0 or f_exp_val < 0:
        st.error("❌ Quantity သို့မဟုတ် Amount များသည် အနှုတ်ဂဏန်း (Negative) မဖြစ်ရပါ။")
        st.stop()

    # ၃။ အနည်းဆုံး အချက်အလက် တစ်ခုခု ပါဝင်မှ သိမ်းမည်
    elif (f_item or f_inc_val > 0 or f_exp_val > 0):
        try:
            with st.spinner("☁️ Cloud ပေါ်သို့ သိမ်းဆည်းနေပါသည်..."):
                before_amt = float(l_stock) if f_item and f_item != "-" else 0.0
                after_stock = max((before_amt + float(p_qty)) - float(s_qty), 0.0)
                balance = after_stock * float(p_pr) if float(p_pr) > 0 else 0.0

                # သိမ်းဆည်းမည့် Row တန်ဖိုးများ (Column ၁၅ ခု)
                row_data = {
                    "Date": tr_date, # load_data နှင့် ညီစေရန် Date object အတိုင်း ထားပါ
                    "Customer": cust_name if cust_name else "-",
                    "Payment": pay_type if pay_type else "Cash",
                    "Brand": f_brand if f_brand else "-",
                    "Category": f_cat if f_cat else "-",
                    "Item": f_item if f_item else "-",
                    "Before Amt": before_amt,
                    "Purchase Qty": float(p_qty),
                    "Pur Price": float(p_pr),
                    "Sale Qty": float(s_qty),
                    "Sale Price": float(s_pr),
                    "Stock": after_stock,
                    "Balance": balance,
                    "Other Income": float(f_inc_val),
                    "Expense": float(f_exp_val)
                }

                worksheet = get_worksheet()
                worksheet.append_row(
                    [as_sheet_value(row_data[col]) for col in EXPECTED_COLS],
                    value_input_option="USER_ENTERED"
                )
                clear_data_cache()

                # ၅။ ပြီးဆုံးကြောင်း အသိပေးပြီး UI Reset လုပ်မည်
                st.session_state.reset_trigger = True
                st.success("✅ စာရင်းကို Cloud ပေါ်သို့ သိမ်းဆည်းပြီး Stock ပြန်လည်တွက်ချက်ပြီးပါပြီ!")
                st.rerun()

        except Exception as e:
            st.error(f"❌ Google Sheets Error: {e}")
        
    else:
        st.warning("⚠️ သိမ်းဆည်းရန် အချက်အလက်များ ပြည့်စုံစွာ ဖြည့်စွက်ပေးပါ။")



# KK_1 >>> History Table (Cloud Version) -----
st.markdown('<div id="history" class="mobile-page-anchor mobile-section-marker" data-section="history"></div>', unsafe_allow_html=True)
st.write("#### 📋 Transaction History")

if not df.empty:
    # Filter များကို တစ်တန်းတည်းပြခြင်း
    f1, f2, f3, f4, f5 = st.columns(5)
    with f1: sel_cus = st.selectbox("Filter by Customer", ["All"] + sorted(df["Customer"].dropna().unique().tolist()), key="f_cus")
    with f2: sel_pay = st.selectbox("Filter by Payment", ["All"] + sorted(df["Payment"].dropna().unique().tolist()), key="f_pay")
    with f3: sel_brand = st.selectbox("Filter by Brand", ["All"] + sorted(df["Brand"].dropna().unique().tolist()), key="f_brand")
    with f4: sel_cat = st.selectbox("Filter by Category", ["All"] + sorted(df["Category"].dropna().unique().tolist()), key="f_cat")
    with f5: sel_item = st.selectbox("Filter by Item", ["All"] + sorted(df["Item"].dropna().unique().tolist()), key="f_item")

    # Date Range နှင့် ခလုတ်များ
    with st.container(border=True):
        h_col1, h_col2, h_col3, h_col4, h_col5, h_col6 = st.columns([1, 1, 1, 1, 1, 1])
        h_start = h_col1.date_input("Start Date", value=date.today(), key="h_start_val")
        h_end = h_col2.date_input("End Date", value=date.today(), key="h_end_val")
    
        h_col3.markdown('<div style="margin-top: 28px;"></div>', unsafe_allow_html=True)
        history_search = h_col3.button("🔍 Search", use_container_width=True, type="primary")    

        h_col4.markdown('<div style="margin-top: 28px;"></div>', unsafe_allow_html=True)
        edit_btn = h_col4.button("📝 Edit", use_container_width=True, type="secondary") 

        h_col5.markdown('<div style="margin-top: 28px;"></div>', unsafe_allow_html=True)
        print_btn = h_col5.button("🖨 Print", use_container_width=True, type="primary")

        h_col6.markdown('<div style="margin-top: 28px;"></div>', unsafe_allow_html=True)
        delete_btn = h_col6.button("🗑 Delete", use_container_width=True, type="secondary")

    # Filter Logic
    h_df = df.copy()
    mask = (h_df["Date"] >= h_start) & (h_df["Date"] <= h_end)
    h_df = h_df.loc[mask]

    if sel_cus != "All": h_df = h_df[h_df["Customer"] == sel_cus]
    if sel_pay != "All": h_df = h_df[h_df["Payment"] == sel_pay]
    if sel_brand != "All": h_df = h_df[h_df["Brand"] == sel_brand]
    if sel_cat != "All": h_df = h_df[h_df["Category"] == sel_cat]
    if sel_item != "All": h_df = h_df[h_df["Item"] == sel_item]

    # Data Editor (ရွေးချယ်နိုင်သော ဇယား)
    # Original_Index သည် Google Sheet ထဲရှိ row order ကို ထိန်းထားသည်။
    if "Original_Index" not in h_df.columns:
        h_df["Original_Index"] = h_df.index
    h_df = h_df.sort_values(by="Original_Index", ascending=False).reset_index(drop=True)
    display_df = h_df.copy()
    display_df.insert(0, "Select", False)

    t_key = f"hist_table_{st.session_state.get('table_key', 0)}"
    edited_df = st.data_editor(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Select": st.column_config.CheckboxColumn("Select", default=False),
            "Original_Index": None # User ကို မပြပါ
        },
        key=t_key
    )

    # LL_1 >>> EDIT DIALOG (Cloud Version) -----
    @st.dialog("📝 Edit Transaction Record")
    def edit_transaction_dialog(row_data, original_idx):
        target_idx = int(original_idx)
        target_item = str(row_data["Item"])

        st.write(f"Editing Item: {target_item}")

        current_date = pd.to_datetime(row_data["Date"]).date()
        current_customer = str(row_data.get("Customer", "-"))
        current_payment = str(row_data.get("Payment", "Cash"))
        current_pq = float(row_data.get("Purchase Qty", 0) or 0)
        current_pp = float(row_data.get("Pur Price", 0) or 0)
        current_sq = float(row_data.get("Sale Qty", 0) or 0)
        current_sp = float(row_data.get("Sale Price", 0) or 0)

        customer_list = sorted([str(x) for x in df["Customer"].dropna().unique().tolist()])
        payment_list = sorted([str(x) for x in df["Payment"].dropna().unique().tolist()])
        if current_customer not in customer_list:
            customer_list.insert(0, current_customer)
        if current_payment not in payment_list:
            payment_list.insert(0, current_payment)

        col1, col2, col3 = st.columns(3)
        with col1:
            new_date = st.date_input("Date", value=current_date, key=f"edit_date_{target_idx}")
        with col2:
            new_customer = st.selectbox(
                "Customer",
                options=customer_list,
                index=customer_list.index(current_customer) if current_customer in customer_list else 0,
                key=f"edit_customer_{target_idx}"
            )
        with col3:
            new_payment = st.selectbox(
                "Payment",
                options=payment_list,
                index=payment_list.index(current_payment) if current_payment in payment_list else 0,
                key=f"edit_payment_{target_idx}"
            )

        st.markdown("### Item Info")
        i1, i2, i3 = st.columns(3)
        with i1:
            st.text_input("Brand", value=str(row_data["Brand"]), disabled=True, key=f"edit_brand_{target_idx}")
        with i2:
            st.text_input("Category", value=str(row_data["Category"]), disabled=True, key=f"edit_cat_{target_idx}")
        with i3:
            st.text_input("Item", value=target_item, disabled=True, key=f"edit_item_{target_idx}")

        st.markdown("---")
        q1, q2 = st.columns(2)
        with q1:
            new_p_qty = st.number_input(
                "Purchase Qty",
                min_value=0.0,
                value=current_pq,
                step=1.0,
                key=f"edit_pq_{target_idx}"
            )
            new_p_price = st.number_input(
                "Purchase Price",
                min_value=0.0,
                value=current_pp,
                step=1.0,
                key=f"edit_pp_{target_idx}"
            )
        with q2:
            new_s_qty = st.number_input(
                "Sale Qty",
                min_value=0.0,
                value=current_sq,
                step=1.0,
                key=f"edit_sq_{target_idx}"
            )
            new_s_price = st.number_input(
                "Sale Price",
                min_value=0.0,
                value=current_sp,
                step=1.0,
                key=f"edit_sp_{target_idx}"
            )

        st.markdown("---")
        if st.button("Confirm Update", type="primary", use_container_width=True, key=f"confirm_update_{target_idx}"):
            try:
                all_df = conn.read(ttl=60)

                all_df.loc[target_idx, "Date"] = as_sheet_value(new_date)
                all_df.loc[target_idx, "Customer"] = new_customer
                all_df.loc[target_idx, "Payment"] = new_payment
                all_df.loc[target_idx, "Purchase Qty"] = float(new_p_qty)
                all_df.loc[target_idx, "Pur Price"] = float(new_p_price)
                all_df.loc[target_idx, "Sale Qty"] = float(new_s_qty)
                all_df.loc[target_idx, "Sale Price"] = float(new_s_price)

                all_df = recalculate_items_in_df(all_df, [target_item])
                conn.update(data=all_df)
                clear_data_cache()

                st.success("Transaction Updated Successfully")
                st.session_state.table_key = st.session_state.get("table_key", 0) + 1
                st.rerun()
            except Exception as e:
                st.error(f"Update Error: {e}")

    # LL_2 >>> DELETE DIALOG (Cloud Version) -----
    @st.dialog("⚠️ Confirm Delete")
    def delete_confirmation_dialog(selected_df):
        st.warning(f"Delete {len(selected_df)} selected records?")
        confirm_pw = st.text_input("Admin Password", type="password")
    
        if st.button("Confirm Delete", type="primary", use_container_width=True):
            if confirm_pw == st.session_state.get("password", "123456"):
                all_df = conn.read(ttl=60)
                # ရွေးထားသော Original_Index များကို ဖယ်ထုတ်ပါ
                indices_to_drop = [int(idx) for idx in selected_df["Original_Index"].tolist()]
                all_df = all_df.drop(indices_to_drop)
            
                affected_items = [item for item in selected_df["Item"].unique() if item != "-"]
                all_df = recalculate_items_in_df(all_df, affected_items)
                conn.update(data=all_df)
                clear_data_cache()
            
                st.success("Deleted Successfully!")
                st.rerun()
            else:
                st.error("Wrong Password")

    # MM_1, 2, 3 Logic
    if edit_btn:
        selected_to_edit = edited_df[edited_df["Select"] == True]
        if len(selected_to_edit) == 1:
            edit_transaction_dialog(selected_to_edit.iloc[0], selected_to_edit.iloc[0]["Original_Index"])
        else:
            st.warning("Please select exactly one record to edit.")

    if delete_btn:
        selected_to_delete = edited_df[edited_df["Select"] == True]
        if not selected_to_delete.empty:
            delete_confirmation_dialog(selected_to_delete)
        else:
            st.warning("Select transactions to delete.")

    if print_btn:
        # သင်၏ မူရင်း Print Logic အတိုင်း ဆက်လက်အသုံးပြုနိုင်ပါသည်
        selected_rows = edited_df[edited_df["Select"] == True]
        if not selected_rows.empty:
            cust_name = str(selected_rows.iloc[0]['Customer'])
            items_to_print = []
            grand_total = 0
            for _, row in selected_rows.iterrows():
                if row['Sale Qty'] > 0:
                    amount = row['Sale Qty'] * row['Sale Price']
                    items_to_print.append({"name": f"{row['Brand']} {row['Item']}", "qty": row['Sale Qty'], "price": row['Sale Price'], "amount": amount})
                    grand_total += amount
            show_receipt_ui(cust_name, items_to_print, grand_total)

else:
    st.info("No transaction history found.")
