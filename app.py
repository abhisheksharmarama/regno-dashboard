import datetime
import pytz
import hashlib
import pandas as pd
import streamlit as st
import rules
from data_sources import load_live_data, lookup_record, lookup_by_phone

st.set_page_config(
    page_title="Registration Lookup",
    layout="centered", 
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
  .control-panel {{ background-color: {CARD_BG}; padding: 1.5rem; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.02); border: 1px solid {BORDER}; }}
  .verdict-card {{ background-color: {CARD_BG}; padding: 1.5rem; border-radius: 12px; border-left: 6px solid; box-shadow: 0 4px 6px rgba(0,0,0,0.02); margin-top: 1.5rem; }}
  .verdict-card.warn {{ border-color: #FCD34D; }} 
  .verdict-card.ok {{ border-color: #86EFAC; }}   
  .verdict-card.neutral {{ border-color: #CBD5E1; }} 
  .verdict-card.miss {{ border-color: #FCA5A5; }}  
  .verdict-card h3 {{ margin-top: 0; font-size: 1.25rem; color: {TEXT_MAIN}; }}
  .verdict-card p {{ color: #64748B; font-size: 0.95rem; margin-bottom: 1.5rem; }}
  .fact-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; background-color: #F8FAFC; padding: 1.2rem; border-radius: 8px; border: 1px solid {BORDER}; }}
  .fact-item .label {{ font-size: 0.75rem; font-weight: 700; color: {TEXT_MUTED}; text-transform: uppercase; letter-spacing: 0.05em; }}
  .fact-item .value {{ font-size: 1.15rem; font-weight: 600; color: {TEXT_MAIN}; margin-top: 0.2rem; }}
  @media (max-width: 600px) {{ .fact-grid {{ grid-template-columns: 1fr 1fr; }} }}
  div[data-testid="stRadio"] > div {{ flex-direction: row; gap: 2rem; padding-bottom: 1rem; }}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="header-box"><h1>Registration Lookup & Fee Verification Dashboard</h1></div>', unsafe_allow_html=True)

def get_ist_sync_key():
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(ist)
    if now.hour < 1:
        return (now - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    return now.strftime('%Y-%m-%d')

with st.spinner("Syncing database... (This takes a few seconds but only occurs once a day after 1 AM)"):
    try:
        df = load_live_data(get_ist_sync_key())
    except Exception as exc:
        st.error(f"System Offline: Unable to sync with database. ({exc})")
        st.stop()

st.markdown('<div class="control-panel">', unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    valid_dates = df["_date_clean"].dropna()
    if not valid_dates.empty:
        min_date, max_date = valid_dates.min(), valid_dates.max()
        start_date = st.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date)
    else:
        start_date = None
        st.info("No dates")

with c2:
    if not valid_dates.empty:
        end_date = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date)
    else:
        end_date = None
        st.info("No dates")

programs = sorted(df["_program_clean"].dropna().unique())
selected_programs = st.multiselect("Program Name", options=programs, placeholder="Filter by program...")

st.markdown("<hr style='margin: 1.2rem 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)

# New Search Type Toggle
search_type = st.radio("Search Method", ["Registration Number", "Mobile Number"], label_visibility="collapsed")

if search_type == "Registration Number":
    search_query = st.text_input("Reg number check", placeholder="Enter 8-digit registration number...")
else:
    search_query = st.text_input("Mobile number check", placeholder="Enter 10-digit mobile number...")

st.markdown('</div>', unsafe_allow_html=True)

# Helper function to render a record card
def render_record_card(record):
    program_val = record.get("_program_clean", "—")
    fee_val = record.get("_fee_clean", None)
    verdict = rules.evaluate(program_val, fee_val)

    fee_display = f"₹ {fee_val:,.2f}" if pd.notna(fee_val) and fee_val is not None else "—"
    date_display = str(record.get("_date_clean", "—"))
    reg_display = record.get("_regno_clean", "—")

    st.markdown(f"""
    <div class="verdict-card {verdict.tone}">
      <h3>{verdict.headline}</h3>
      <p>{verdict.detail}</p>
      <div class="fact-grid">
        <div class="fact-item"><div class="label">REG NO</div><div class="value">{reg_display}</div></div>
        <div class="fact-item"><div class="label">PROGRAM</div><div class="value">{program_val}</div></div>
        <div class="fact-item"><div class="label">FEES PAID</div><div class="value">{fee_display}</div></div>
        <div class="fact-item"><div class="label">DATE</div><div class="value">{date_display}</div></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# Search Execution
if search_query.strip():
    filtered_df = df.copy()
    
    if start_date and end_date:
        if start_date > end_date:
            st.error("Start Date cannot be after End Date.")
            st.stop()
        filtered_df = filtered_df[(filtered_df["_date_clean"] >= start_date) & (filtered_df["_date_clean"] <= end_date)]
        
    if selected_programs:
        filtered_df = filtered_df[filtered_df["_program_clean"].isin(selected_programs)]
        
    found_match = False

    if search_type == "Registration Number":
        record = lookup_record(filtered_df, search_query)
        if record is not None:
            found_match = True
            render_record_card(record)
            
    elif search_type == "Mobile Number":
        # Instantly hash the user's input
        raw_phone = search_query.strip()
        phone_hash = hashlib.md5(raw_phone.encode()).hexdigest()
        
        # Show the generated hash as a subtle verification step
        st.caption(f"🔒 **Generated Masked Number:** `{phone_hash}`")
        
        matched_records_df = lookup_by_phone(filtered_df, phone_hash)
        
        if not matched_records_df.empty:
            found_match = True
            st.markdown(f"<p style='color: {TEXT_MUTED}; font-size: 0.9rem; margin-top: 1rem;'>Found {len(matched_records_df)} record(s) linked to this number.</p>", unsafe_allow_html=True)
            for _, row in matched_records_df.iterrows():
                render_record_card(row)

    # Universal Error Message
    if not found_match:
        st.markdown(f"""
        <div class="verdict-card miss">
          <h3>No results found in the records</h3>
          <p>Verify the given reg number or mobile number again.</p>
        </div>
        """, unsafe_allow_html=True)
