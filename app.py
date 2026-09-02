import datetime
import pytz
import hashlib
import re
import pandas as pd
import streamlit as st
import rules
from data_sources import load_live_data, lookup_record, lookup_by_phone, PHONE_COLUMNS

st.set_page_config(
    page_title="Registration Lookup",
    layout="wide", 
    initial_sidebar_state="collapsed",
)

BG_COLOR = "#F4F7FB"       
CARD_BG = "#FFFFFF"        
ACCENT = "#93C5FD"         
TEXT_MAIN = "#334155"      
TEXT_MUTED = "#94A3B8"     
BORDER = "#E2E8F0"         

st.markdown(f"""
<style>
  .stApp {{ background-color: {BG_COLOR}; color: {TEXT_MAIN}; font-family: 'Segoe UI', sans-serif; }}
  .header-box {{ background-color: {CARD_BG}; padding: 1.5rem; border-radius: 12px; border-top: 6px solid {ACCENT}; box-shadow: 0 4px 6px rgba(0,0,0,0.02); text-align: center; margin-bottom: 2rem; }}
  .header-box h1 {{ color: {TEXT_MAIN}; font-size: 1.6rem; font-weight: 700; margin: 0; }}
  .control-panel {{ background-color: {CARD_BG}; padding: 1.5rem; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border: 1px solid {BORDER}; max-width: 800px; margin: 0 auto; }}
  .verdict-card {{ background-color: {CARD_BG}; padding: 1.5rem; border-radius: 12px; border-left: 6px solid; box-shadow: 0 4px 6px rgba(0,0,0,0.02); margin-top: 1.5rem; }}
  .verdict-card.warn {{ border-color: #FCD34D; }} 
  .verdict-card.ok {{ border-color: #86EFAC; }}   
  .verdict-card.neutral {{ border-color: #CBD5E1; }} 
  .verdict-card.miss {{ border-color: #FCA5A5; }}  
  .verdict-card h3 {{ margin-top: 0; font-size: 1.25rem; color: {TEXT_MAIN}; }}
  .verdict-card p {{ color: #64748B; font-size: 0.95rem; margin-bottom: 1.5rem; }}
  div[data-testid="stRadio"] > div {{ flex-direction: row; gap: 2rem; padding-bottom: 1rem; }}
  
  .pastel-table-wrapper {{ overflow-x: auto; margin-top: 1rem; border-radius: 8px; border: 1px solid {BORDER}; }}
  table.pastel-grid {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; background: {CARD_BG}; text-align: center; }}
  table.pastel-grid th {{ background: #E0E7FF; color: {TEXT_MAIN}; font-weight: 700; padding: 0.8rem; border-bottom: 2px solid #C7D2FE; white-space: nowrap; text-transform: uppercase; font-size: 0.8rem; }}
  table.pastel-grid td {{ padding: 0.8rem; border-bottom: 1px solid {BORDER}; border-right: 1px solid {BORDER}; white-space: nowrap; }}
  table.pastel-grid td:last-child {{ border-right: none; }}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="header-box"><h1>Registration Lookup & Fee Verification Dashboard</h1></div>', unsafe_allow_html=True)

def get_ist_sync_key():
    """Forces cache to reset strictly at 11:00 AM IST."""
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(ist)
    if now.hour < 11:
        return (now - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    return now.strftime('%Y-%m-%d')

with st.spinner("Syncing database... (This takes a few seconds but only occurs once a day after 11:00 AM IST)"):
    try:
        # Load the master database into memory ONCE.
        master_df = load_live_data(get_ist_sync_key())
    except Exception as exc:
        st.error(f"System Offline: Unable to sync with database. ({exc})")
        st.stop()

st.markdown('<div class="control-panel">', unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    valid_dates = master_df["_date_clean"].dropna()
    if not valid_dates.empty:
        min_date, max_date = valid_dates.min(), valid_dates.max()
        
        ist = pytz.timezone('Asia/Kolkata')
        today = datetime.datetime.now(ist).date()
        thirty_days_ago = today - datetime.timedelta(days=30)
        default_start = max(min_date, thirty_days_ago)
        
        start_date = st.date_input("Start Date", value=default_start, min_value=min_date, max_value=max_date)
    else:
        start_date = None
        st.info("No dates available")

with c2:
    if not valid_dates.empty:
        default_end = min(max_date, today)
        end_date = st.date_input("End Date", value=default_end, min_value=min_date, max_value=max_date)
    else:
        end_date = None
        st.info("No dates available")

programs = sorted(master_df["_program_clean"].dropna().unique())
selected_programs = st.multiselect("Program Name", options=programs, placeholder="Filter by program...")

st.markdown("<hr style='margin: 1.2rem 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)

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

def render_record_card(record):
    program_val = record.get("_program_clean", "—")
    fee_val = record.get("_fee_clean", None)
    verdict = rules.evaluate(program_val, fee_val)

    fee_display = f"₹ {fee_val:,.2f}" if pd.notna(fee_val) and fee_val is not None else "—"
    date_display = str(record.get("_date_clean", "—"))
    reg_display = record.get("_regno_clean", "—")

    phones = {col: mask_mobile(record.get(col.casefold(), "—")) for col in PHONE_COLUMNS}

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

def record_passes_filters(rec) -> bool:
    """Validates if a single plucked record matches the UI filters."""
    # Check Program
    if selected_programs and rec.get("_program_clean") not in selected_programs:
        return False
    # Check Dates
    rec_date = rec.get("_date_clean")
    if start_date and end_date and pd.notna(rec_date):
        if not (start_date <= rec_date <= end_date):
            return False
    return True

# --- HIGH PERFORMANCE SEARCH EXECUTION ---
if search_query.strip():
    if start_date and end_date and start_date > end_date:
        st.error("Start Date cannot be after End Date.")
        st.stop()
        
    found_match = False

    if search_type == "Registration Number":
        # Pull 1 row from master memory instantly
        record = lookup_record(master_df, search_query)
        if record is not None and record_passes_filters(record):
            found_match = True
            render_record_card(record)
            
    elif search_type == "Mobile Number":
        raw_phone = search_query.strip()
        phone_hash = hashlib.md5(raw_phone.encode()).hexdigest()
        
        # Pull only matching rows (1-5 rows maximum)
        matched_records_df = lookup_by_phone(master_df, phone_hash)
        
        if not matched_records_df.empty:
            valid_records = []
            for _, row in matched_records_df.iterrows():
                if record_passes_filters(row):
                    valid_records.append(row)
            
            if valid_records:
                found_match = True
                st.caption(f"🔒 **Generated Masked Number:** `{phone_hash}`")
                st.markdown(f"<p style='color: {TEXT_MUTED}; font-size: 0.9rem; margin-top: 1rem; text-align: center;'>Found {len(valid_records)} record(s) linked to this number within the selected filters.</p>", unsafe_allow_html=True)
                for rec in valid_records:
                    render_record_card(rec)

    if not found_match:
        st.markdown(f"""
        <div class="verdict-card miss">
          <h3>No results found in the records</h3>
          <p>Verify the given reg number or mobile number again. Make sure it falls within the selected Program and Date Range.</p>
        </div>
        """, unsafe_allow_html=True)
