import datetime
import pytz
import hashlib
import re
import pandas as pd
import streamlit as st
import rules
# TYPO FIXED HERE
from data_sources import sync_sqlite_db, search_regno, search_phone, get_unique_programs, PHONE_COLS

st.set_page_config(
    page_title="Registration Lookup",
    layout="wide", 
    initial_sidebar_state="collapsed",
)

BG_COLOR = "#F8FAFC"       
CARD_BG = "#FFFFFF"        
ACCENT = "#93C5FD"         
TEXT_MAIN = "#334155"      
BORDER = "#E2E8F0"         

st.markdown(f"""
<style>
  .stApp {{ background-color: {BG_COLOR}; color: {TEXT_MAIN}; font-family: 'Segoe UI', sans-serif; }}
  .header-box {{ background-color: {CARD_BG}; padding: 1.2rem; border-radius: 8px; border-top: 5px solid {ACCENT}; box-shadow: 0 2px 4px rgba(0,0,0,0.02); text-align: left; margin-bottom: 1.5rem; }}
  .header-box h1 {{ color: {TEXT_MAIN}; font-size: 1.4rem; font-weight: 700; margin: 0; }}
  .control-panel {{ background-color: {CARD_BG}; padding: 1.5rem; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.02); border: 1px solid {BORDER}; margin-bottom: 1.5rem; }}
  
  .verdict-card {{ background-color: {CARD_BG}; padding: 1.5rem; border-radius: 8px; border-left: 5px solid; box-shadow: 0 2px 4px rgba(0,0,0,0.02); margin-top: 1rem; }}
  .verdict-card.warn {{ border-color: #FCD34D; }} 
  .verdict-card.ok {{ border-color: #86EFAC; }}   
  .verdict-card.neutral {{ border-color: #CBD5E1; }} 
  .verdict-card.miss {{ border-color: #FCA5A5; }}  
  .verdict-card h3 {{ margin-top: 0; font-size: 1.15rem; color: {TEXT_MAIN}; }}
  .verdict-card p {{ color: #64748B; font-size: 0.9rem; margin-bottom: 1rem; }}
  
  div[data-testid="stRadio"] > div {{ flex-direction: row; gap: 2rem; padding-bottom: 0.5rem; }}
  
  .pastel-table-wrapper {{ overflow-x: auto; margin-top: 1rem; border-radius: 6px; border: 1px solid {BORDER}; }}
  table.pastel-grid {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; background: {CARD_BG}; text-align: center; }}
  table.pastel-grid th {{ background: #EEF2FF; color: {TEXT_MAIN}; font-weight: 600; padding: 0.7rem; border-bottom: 2px solid #C7D2FE; white-space: nowrap; }}
  table.pastel-grid td {{ padding: 0.7rem; border-bottom: 1px solid {BORDER}; border-right: 1px solid {BORDER}; white-space: nowrap; }}
  table.pastel-grid td:last-child {{ border-right: none; }}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="header-box"><h1>Registration Lookup & Fee Verification Dashboard</h1></div>', unsafe_allow_html=True)

def get_ist_sync_key():
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(ist)
    if now.hour < 11:
        return (now - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    return now.strftime('%Y-%m-%d')

with st.spinner("Synchronizing database... (Happens once daily after 11:00 AM IST)"):
    try:
        sync_sqlite_db(get_ist_sync_key())
    except Exception as exc:
        st.error(f"System Offline: Unable to sync with Google Sheet. ({exc})")
        st.stop()

st.markdown('<div class="control-panel">', unsafe_allow_html=True)

c1, c2, c3 = st.columns([1, 1, 2])
ist = pytz.timezone('Asia/Kolkata')
today = datetime.datetime.now(ist).date()
thirty_days_ago = today - datetime.timedelta(days=30)

with c1:
    start_date = st.date_input("Start Date", value=thirty_days_ago, format="YYYY/MM/DD")
with c2:
    end_date = st.date_input("End Date", value=today, format="YYYY/MM/DD")
with c3:
    programs = get_unique_programs()
    selected_programs = st.multiselect("Program Name", options=programs, placeholder="Filter by program...")

st.markdown("<hr style='margin: 1rem 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)

search_type = st.radio("Search Method", ["Registration Number", "Mobile Number"], label_visibility="collapsed")

if search_type == "Registration Number":
    search_query = st.text_input("Reg number check", placeholder="Enter 8-digit registration number...")
else:
    search_query = st.text_input("Mobile number check", placeholder="Enter 10-digit mobile number...")

st.markdown('</div>', unsafe_allow_html=True)

def mask_mobile(val):
    if pd.isna(val) or not str(val).strip():
        return "—"
    s = str(val).strip()
    if len(s) == 32 and re.fullmatch(r"[a-fA-F0-9]{32}", s):
        return "[Secured Hash]"
    cleaned = re.sub(r"\D", "", s)
    if len(cleaned) >= 10:
        return cleaned[:2] + "xxxx" + cleaned[-4:]
    return s

def render_record_card(row_dict):
    prog_col = next((c for c in ["all_program", "program", "program_name", "course"] if c in row_dict), None)
    fee_col = next((c for c in ["fees_paid", "fee_paid", "fees", "fee"] if c in row_dict), None)
    
    program_val = row_dict.get(prog_col, "—") if prog_col else "—"
    raw_fee = row_dict.get(fee_col, None) if fee_col else None
    
    verdict = rules.evaluate(program_val, raw_fee)
    
    fee_display = f"₹ {rules.parse_fee(raw_fee):,.2f}" if pd.notna(raw_fee) and rules.parse_fee(raw_fee) is not None else "—"
    date_display = row_dict.get("_date_clean", "—")
    reg_display = row_dict.get("_regno_clean", "—")

    # TYPO FIXED HERE
    phones = {col: mask_mobile(row_dict.get(col, "—")) for col in PHONE_COLS}

    st.markdown(f"""
    <div class="verdict-card {verdict.tone}">
      <h3>{verdict.headline}</h3>
      <p>{verdict.detail}</p>
      <div class="pastel-table-wrapper">
        <table class="pastel-grid">
          <thead>
            <tr>
              <th>REG NO</th>
              <th>PROGRAM</th>
              <th>FEES PAID</th>
              <th>DATE</th>
              <th>mobile_no</th>
              <th>whatsapp_number</th>
              <th>father_mobile_no</th>
              <th>Mother_mobile_no</th>
              <th>class_recorded_mobile_no</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>{reg_display}</strong></td>
              <td>{program_val}</td>
              <td>{fee_display}</td>
              <td>{date_display}</td>
              <td>{phones.get('mobile_no', '—')}</td>
              <td>{phones.get('whatsapp_number', '—')}</td>
              <td>{phones.get('father_mobile_no', '—')}</td>
              <td>{phones.get('mother_mobile_no', '—')}</td>
              <td>{phones.get('class_recorded_mobile_no', '—')}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    """, unsafe_allow_html=True)

if search_query.strip():
    if start_date > end_date:
        st.error("Start Date cannot be after End Date.")
        st.stop()
        
    found_match = False
    results_df = pd.DataFrame()

    if search_type == "Registration Number":
        results_df = search_regno(search_query)
    elif search_type == "Mobile Number":
        raw_phone = search_query.strip()
        phone_hash = hashlib.md5(raw_phone.encode()).hexdigest()
        st.caption(f"🔒 **Generated Masked Number:** `{phone_hash}`")
        results_df = search_phone(phone_hash)

    if not results_df.empty:
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        results_df = results_df[(results_df["_date_clean"] >= start_str) & (results_df["_date_clean"] <= end_str)]
        
        if selected_programs:
            prog_col = next((c for c in ["all_program", "program", "program_name", "course"] if c in results_df.columns), None)
            if prog_col:
                results_df = results_df[results_df[prog_col].isin(selected_programs)]
                
    if not results_df.empty:
        found_match = True
        for _, row in results_df.iterrows():
            render_record_card(row.to_dict())

    if not found_match:
        st.markdown(f"""
        <div class="verdict-card miss">
          <h3>No results found in the records</h3>
          <p>Verify the given reg number or mobile number again. Ensure it matches the selected Program and Date Range.</p>
        </div>
        """, unsafe_allow_html=True)
