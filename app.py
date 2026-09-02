import datetime
import pytz
import hashlib
import re
import pandas as pd
import streamlit as st
import rules

st.set_page_config(page_title="Registration Lookup", layout="wide", initial_sidebar_state="collapsed")

PHONE_COLUMNS = ["mobile_no", "father_mobile_no", "mother_mobile_no", "class_recorded_mobile_no", "whatsapp_number"]

BG_COLOR = "#F4F7FB"
CARD_BG = "#FFFFFF"
ACCENT = "#93C5FD"
TEXT_MAIN = "#334155"
BORDER = "#E2E8F0"


def clean_regno(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"\.0+$", "", text)
    return re.sub(r"\D", "", text)


@st.cache_data(show_spinner=False, max_entries=1)
def load_live_data(sync_key: str) -> pd.DataFrame:
    cfg = dict(st.secrets.get("sheet", {}))
    url = cfg.get("csv_url")
    if not url:
        raise ValueError("CSV URL missing in Secrets.")
    if "pubhtml" in url:
        raise ValueError("csv_url points to a web page (pubhtml). Use the /pub?...&output=csv link.")

    df = pd.read_csv(url, dtype=str, keep_default_na=False)
    df.columns = [str(c).strip().casefold() for c in df.columns]

    reg_col = next((c for c in ["regno", "reg_no", "registration no", "reg no"] if c in df.columns), None)
    prog_col = next((c for c in ["all_program", "program", "program_name", "course"] if c in df.columns), None)
    fee_col = next((c for c in ["fees_paid", "fee_paid", "fees", "fee"] if c in df.columns), None)
    date_col = next((c for c in ["joining_date_timestamp", "joining_date", "date", "call date"] if c in df.columns), None)

    if reg_col is None:
        raise ValueError("regno column not found. Columns seen: " + str(list(df.columns)))

    df["_regno_clean"] = df[reg_col].apply(clean_regno)
    df["_program_clean"] = df[prog_col].astype(str).str.strip() if prog_col else "Unknown"
    df["_fee_clean"] = df[fee_col].apply(rules.parse_fee) if fee_col else None

    if date_col:
        raw = df[date_col].astype(str).str.strip()
        parsed = pd.to_datetime(raw, errors="coerce", format="%Y-%m-%d %H:%M:%S")
        if parsed.isna().any():
            fallback = pd.to_datetime(raw, errors="coerce", format="mixed", dayfirst=False)
            parsed = parsed.fillna(fallback)
        df["_date_clean"] = parsed.dt.date
    else:
        df["_date_clean"] = None

    for col in PHONE_COLUMNS:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.lower()

    return df.reset_index(drop=True)


def search_by_regno(df, regno):
    key = clean_regno(regno)
    if not key:
        return pd.DataFrame()
    return df[df["_regno_clean"] == key]


def search_by_phone(df, phone_hash):
    target = str(phone_hash).strip().lower()
    valid_cols = [c for c in PHONE_COLUMNS if c in df.columns]
    if not valid_cols:
        return pd.DataFrame()
    mask = pd.Series(False, index=df.index)
    for col in valid_cols:
        mask = mask | (df[col] == target)
    return df[mask]


def mask_mobile(val):
    if val is None or not str(val).strip():
        return "-"
    s = str(val).strip()
    if len(s) == 32 and re.fullmatch(r"[a-fA-F0-9]{32}", s):
        return "[Secured Hash]"
    cleaned = re.sub(r"\D", "", s)
    if len(cleaned) >= 10:
        return cleaned[:2] + "xxxx" + cleaned[-4:]
    return s


def get_ist_sync_key():
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.datetime.now(ist)
    if now.hour < 11:
        return (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    return now.strftime("%Y-%m-%d")


st.markdown(f"""
<style>
  .stApp {{ background-color: {BG_COLOR}; color: {TEXT_MAIN}; font-family: 'Segoe UI', sans-serif; }}
  .header-box {{ background-color: {CARD_BG}; padding: 1.5rem; border-radius: 12px; border-top: 6px solid {ACCENT}; text-align: center; margin-bottom: 2rem; box-shadow: 0 4px 6px rgba(0,0,0,0.02); }}
  .header-box h1 {{ color: {TEXT_MAIN}; font-size: 1.6rem; font-weight: 700; margin: 0; }}
  .control-panel {{ background-color: {CARD_BG}; padding: 1.5rem; border-radius: 12px; border: 1px solid {BORDER}; max-width: 800px; margin: 0 auto; box-shadow: 0 4px 6px rgba(0,0,0,0.02); }}
  .verdict-card {{ background-color: {CARD_BG}; padding: 1.5rem; border-radius: 12px; border-left: 6px solid; margin-top: 1.5rem; box-shadow: 0 4px 6px rgba(0,0,0,0.02); }}
  .verdict-card.warn {{ border-color: #FCD34D; }}
  .verdict-card.ok {{ border-color: #86EFAC; }}
  .verdict-card.neutral {{ border-color: #CBD5E1; }}
  .verdict-card.miss {{ border-color: #FCA5A5; }}
  .pastel-table-wrapper {{ overflow-x: auto; margin-top: 1rem; border-radius: 8px; border: 1px solid {BORDER}; }}
  table.pastel-grid {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; background: {CARD_BG}; text-align: center; }}
  table.pastel-grid th {{ background: #E0E7FF; color: {TEXT_MAIN}; font-weight: 700; padding: 0.8rem; border-bottom: 2px solid #C7D2FE; font-size: 0.8rem; text-transform: uppercase; }}
  table.pastel-grid td {{ padding: 0.8rem; border-bottom: 1px solid {BORDER}; border-right: 1px solid {BORDER}; white-space: nowrap; }}
  table.pastel-grid td:last-child {{ border-right: none; }}
  div[data-testid="stRadio"] > div {{ flex-direction: row; gap: 2rem; padding-bottom: 1rem; }}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="header-box"><h1>Registration Lookup and Fee Verification</h1></div>', unsafe_allow_html=True)

with st.spinner("Loading 30-Day Database..."):
    try:
        df = load_live_data(get_ist_sync_key())
    except Exception as exc:
        st.error("System Offline: " + str(exc))
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

programs = sorted(df["_program_clean"].dropna().astype(str).unique())
selected_programs = st.multiselect("Program Name", options=programs, placeholder="Filter by program...")

st.markdown("<hr style='margin: 1.2rem 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)

search_type = st.radio("Search Method", ["Registration Number", "Mobile Number"], label_visibility="collapsed")
search_query = st.text_input("Search", placeholder="Enter Reg No or 10-digit Mobile...", label_visibility="collapsed")

st.markdown('</div>', unsafe_allow_html=True)


def render_record_card(record):
    program_val = record.get("_program_clean", "-")
    fee_val = record.get("_fee_clean", None)
    verdict = rules.evaluate(program_val, fee_val)
    fee_display = "Rs {:,.2f}".format(fee_val) if pd.notna(fee_val) else "-"
    phones = {col: mask_mobile(record.get(col, "-")) for col in PHONE_COLUMNS}

    html = """
    <div class="verdict-card {tone}">
      <h3>{headline}</h3>
      <p>{detail}</p>
      <div class="pastel-table-wrapper">
        <table class="pastel-grid">
          <thead>
            <tr>
              <th>REG NO</th><th>PROGRAM</th><th>FEES PAID</th><th>DATE</th>
              <th>mobile_no</th><th>whatsapp_number</th><th>father_mobile_no</th><th>mother_mobile_no</th><th>class_recorded</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>{regno}</strong></td>
              <td>{program}</td>
              <td>{fee}</td>
              <td>{date}</td>
              <td>{m1}</td><td>{m2}</td><td>{m3}</td><td>{m4}</td><td>{m5}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    """.format(
        tone=verdict.tone,
        headline=verdict.headline,
        detail=verdict.detail,
        regno=record.get("_regno_clean", "-"),
        program=program_val,
        fee=fee_display,
        date=record.get("_date_clean", "-"),
        m1=phones.get("mobile_no"),
        m2=phones.get("whatsapp_number"),
        m3=phones.get("father_mobile_no"),
        m4=phones.get("mother_mobile_no"),
        m5=phones.get("class_recorded_mobile_no"),
    )
    st.markdown(html, unsafe_allow_html=True)


if search_query.strip():
    if (end_date - start_date).days < 0:
        st.error("Start Date cannot be after End Date.")
        st.stop()

    if search_type == "Registration Number":
        results = search_by_regno(df, search_query)
    else:
        phone_hash = hashlib.md5(search_query.strip().encode()).hexdigest()
        st.caption("Generated Masked Number: " + phone_hash)
        results = search_by_phone(df, phone_hash)

    raw_hits = len(results)

    if not results.empty:
        d = results["_date_clean"]
        in_range = d.isna() | ((d >= start_date) & (d <= end_date))
        results = results[in_range]
        if selected_programs:
            results = results[results["_program_clean"].isin(selected_programs)]

    with st.expander("Diagnostics"):
        st.write("Rows loaded from sheet:", len(df))
        st.write("Columns detected:", list(df.columns))
        st.write("Earliest date:", str(valid_dates.min()) if not valid_dates.empty else "NONE")
        st.write("Latest date:", str(valid_dates.max()) if not valid_dates.empty else "NONE")
        st.write("Rows with unreadable dates:", int(df["_date_clean"].isna().sum()))
        st.write("Matches BEFORE filters:", raw_hits)
        st.write("Matches AFTER filters:", len(results))

    if results.empty:
        st.markdown('<div class="verdict-card miss"><h3>No results found</h3><p>Ensure the number is correct and falls within the selected date range and program.</p></div>', unsafe_allow_html=True)
    else:
        for _, row in results.iterrows():
            render_record_card(row.to_dict())
