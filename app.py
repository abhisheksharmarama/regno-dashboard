import datetime
import pytz
import hashlib
import re
import pandas as pd
import streamlit as st
import rules
from data_sources import load_live_data, search_by_regno, search_by_phone, PHONE_COLUMNS

st.set_page_config(page_title="Registration Lookup", layout="wide", initial_sidebar_state="collapsed")

BG_COLOR, CARD_BG, ACCENT, TEXT_MAIN, TEXT_MUTED, BORDER = "#F4F7FB", "#FFFFFF", "#93C5FD", "#334155", "#94A3B8", "#E2E8F0"

st.markdown(f"""
<style>
  .stApp {{ background-color: {BG_COLOR}; color: {TEXT_MAIN}; font-family: 'Segoe UI', sans-serif; }}
  .header-box {{ background-color: {CARD_BG}; padding: 1.5rem; border-radius: 12px; border-top: 6px solid {ACCENT}; text-align: center; margin-bottom: 2rem; box-shadow: 0 4px 6px rgba(0,0,0,0.02); }}
  .header-box h1 {{ color: {TEXT_MAIN}; font-size: 1.6rem; font-weight: 700; margin: 0; }}
  .control-panel {{ background-color: {CARD_BG}; padding: 1.5rem; border-radius: 12px; border: 1px solid {BORDER}; max-width: 800px; margin: 0 auto; box-shadow: 0 4px 6px rgba(0,0,0,0.02); }}
  .verdict-card {{ background-color: {CARD_BG}; padding: 1.5rem; border-radius: 12px; border-left: 6px solid; margin-top: 1.5rem; box-shadow: 0 4px 6px rgba(0,0,0,0.02); }}
  .verdict-card.warn {{ border-color: #FCD34D; }} .verdict-card.ok {{ border-color: #86EFAC; }} .verdict-card.neutral {{ border-color: #CBD5E1; }} .verdict-card.miss {{ border-color: #FCA5A5; }}  
  .pastel-table-wrapper {{ overflow-x: auto; margin-top: 1rem; border-radius: 8px; border: 1px solid {BORDER}; }}
  table.pastel-grid {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; background: {CARD_BG}; text-align: center; }}
  table.pastel-grid th {{ background: #E0E7FF; color: {TEXT_MAIN}; font-weight: 700; padding: 0.8rem; border-bottom: 2px solid #C7D2FE; font-size: 0.8rem; text-transform: uppercase; }}
  table.pastel-grid td {{ padding: 0.8rem; border-bottom: 1px solid {BORDER}; border-right: 1px solid {BORDER}; white-space: nowrap; }}
  table.pastel-grid td:last-child {{ border-right: none; }}
  div[data-testid="stRadio"] > div {{ flex-direction: row; gap: 2rem; padding-bottom: 1rem; }}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="header-box"><h1>Registration Lookup & Fee Verification</h1></div>', unsafe_allow_html=True)

def get_ist_sync_key():
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(ist)
    if now.hour < 11:
        return (now - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    return now.strftime('%Y-%m-%d')

with st.spinner("Loading 30-Day Database..."):
    try:
        df = load_live_data(get_ist_sync_key())
    except Exception as exc:
        st.error(f"System Offline: ({exc})")
        st.stop()

st.markdown('<div class="control-panel">', unsafe_allow_html=True)

valid_dates = df["_date_clean"].dropna()
c1, c2 = st.columns(2)
with c1:
    default_start = valid_dates.min() if not valid_dates.empty else datetime.date.today()
    start_date = st.date_input("Start Date", value=default_start)
with c2:
    default_end = valid_dates.max() if not valid_dates.empty else datetime.date.today()
    end_date = st.date_input("End Date", value=default_end)

programs = sorted(df["_program_clean"].dropna().unique())
selected_programs = st.multiselect("Program Name", options=programs, placeholder="Filter by program...")

st.markdown("<hr style='margin: 1.2rem 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)

search_type = st.radio("Search Method", ["Registration Number", "Mobile Number"], label_visibility="collapsed")
search_query = st.text_input("Search", placeholder="Enter Reg No or 10-digit Mobile...", label_visibility="collapsed")

st.markdown('</div>', unsafe_allow_html=True)

def mask_mobile(val):
    if pd.isna(val) or not str(val).strip(): return "—"
    s = str(val).strip()
    if len(s) == 32 and re.fullmatch(r"[a-fA-F0-9]{32}", s): return "[Secured Hash]"
    cleaned = re.sub(r"\D", "", s)
    if len(cleaned) >= 10: return cleaned[:2] + "xxxx" + cleaned[-4:]
    return s

def render_record_card(record):
    program_val = record.get("_program_clean", "—")
    fee_val = record.get("_fee_clean", None)
    verdict = rules.evaluate(program_val, fee_val)
    fee_display = f"₹ {fee_val:,.2f}" if pd.notna(fee_val) else "—"
    
    phones = {col: mask_mobile(record.get(col, "—")) for col in PHONE_COLUMNS}

    st.markdown(f"""
    <div class="verdict-card {verdict.tone}">
      <h3>{verdict.headline}</h3>
      <p>{verdict.detail}</p>
      <div class="pastel-table-wrapper">
        <table class="pastel-grid">
          <thead>
            <tr>
              <th>REG NO</th><th>PROGRAM</th><th>FEES PAID</th><th>DATE</th>
              <th>mobile_no</th><th>whatsapp_number</th><th>father_mobile_no</th><th>Mother_mobile_no</th><th>class_recorded</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>{record.get('_regno_clean', '—')}</strong></td>
              <td>{program_val}</td>
              <td>{fee_display}</td>
              <td>{record.get('_date_clean', '—')}</td>
              <td>{phones.get('mobile_no')}</td><td>{phones.get('whatsapp_number')}</td>
              <td>{phones.get('father_mobile_no')}</td><td>{phones.get('mother_mobile_no')}</td><td>{phones.get('class_recorded_mobile_no')}</td>
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
        
    if search_type == "Registration Number":
        results = search_by_regno(df, search_query)
    else:
        raw_phone = search_query.strip()
        # Strictly enforced MD5 (32-character) hashing
        phone_hash = hashlib.md5(raw_phone.encode()).hexdigest()
        st.caption(f"🔒 **Generated Masked Number:** `{phone_hash}`")
        results = search_by_phone(df, phone_hash)

    if not results.empty:
        results = results[(results["_date_clean"] >= start_date) & (results["_date_clean"] <= end_date)]
        if selected_programs:
            results = results[results["_program_clean"].isin(selected_programs)]

    if results.empty:
        st.markdown(f'<div class="verdict-card miss"><h3>No results found</h3><p>Ensure the number is correct and falls within the selected 30-Day Date Range and Program.</p></div>', unsafe_allow_html=True)
    else:
        for _, row in results.iterrows():
            render_record_card(row.to_dict())
