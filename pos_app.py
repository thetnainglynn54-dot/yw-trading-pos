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
