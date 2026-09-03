import datetime
import hashlib
import re

import pandas as pd
import streamlit as st

import rules

st.set_page_config(page_title="Registration Lookup", layout="wide",
                   initial_sidebar_state="collapsed")

PHONE_COLUMNS = ["mobile_no", "father_mobile_no", "mother_mobile_no",
                 "class_recorded_mobile_no", "whatsapp_number"]

ERROR_TOKENS = {"#ref!", "#n/a", "#error!", "#value!", "#name?", "loading..."}

BG_COLOR = "#F4F7FB"
CARD_BG = "#FFFFFF"
ACCENT = "#93C5FD"
TEXT_MAIN = "#334155"
BORDER = "#E2E8F0"


def clean_regno(value):
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"\.0+$", "", text)
    return re.sub(r"\D", "", text)


@st.cache_resource(show_spinner=False, ttl=900)
def load_live_data():
    cfg = dict(st.secrets.get("sheet", {}))
    url = cfg.get("csv_url")
    if not url:
        raise ValueError("csv_url missing from Secrets.")
    if "pubhtml" in url:
        raise ValueError("csv_url points to a web page. Republish as CSV and use the /pub?...&output=csv link.")

    df = pd.read_csv(url, dtype=str, keep_default_na=False)
    df.columns = [str(c).strip().casefold() for c in df.columns]

    if len(df) == 0:
        raise ValueError("The published sheet has no data rows. The IMPORTRANGE may still be loading.")

    head = df.head(200).astype(str).apply(lambda s: s.str.strip().str.lower())
    bad = int(head.isin(ERROR_TOKENS).sum().sum())
    if head.size and bad / head.size > 0.30:
        raise ValueError("The source sheet is returning formula errors (#REF! / Loading). "
                         "Open the sheet, confirm the IMPORTRANGE has access and has finished loading, then hit Retry.")

    reg_col = next((c for c in ["regno", "reg_no", "registration no", "reg no"] if c in df.columns), None)
    prog_col = next((c for c in ["all_program", "program", "program_name", "course"] if c in df.columns), None)
    fee_col = next((c for c in ["fees_paid", "fee_paid", "fees", "fee"] if c in df.columns), None)
    date_col = next((c for c in ["joining_date_timestamp", "joining_date", "date", "call date"] if c in df.columns), None)

    if reg_col is None:
        raise ValueError("regno column not found. Columns seen: " + str(list(df.columns)))

    df["_regno_clean"] = df[reg_col].map(clean_regno)
    df["_program_clean"] = df[prog_col].astype(str).str.strip() if prog_col else "Unknown"
    df["_fee_clean"] = df[fee_col].map(rules.parse_fee) if fee_col else None

    if date_col:
        raw = df[date_col].astype(str).str.strip()
        parsed = pd.to_datetime(raw, errors="coerce", format="%Y-%m-%d %H:%M:%S")
        if parsed.isna().any():
            parsed = parsed.fillna(pd.to_datetime(raw, errors="coerce", format="mixed", dayfirst=False))
        df["_date_clean"] = parsed.dt.date
    else:
        df["_date_clean"] = None

    for col in PHONE_COLUMNS:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.lower()

    df = df.reset_index(drop=True)

    phone_map = {}
    for col in [c for c in PHONE_COLUMNS if c in df.columns]:
        for pos, val in enumerate(df[col].to_numpy()):
            if val and val != "nan":
                phone_map.setdefault(val, set()).add(pos)

    regno_map = {}
    for pos, val in enumerate(df["_regno_clean"].to_numpy()):
        if val:
            regno_map.setdefault(val, []).append(pos)

    loaded_at = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
    return df, phone_map, regno_map, loaded_at


def search_by_regno(df, regno_map, regno):
    key = clean_regno(regno)
    positions = regno_map.get(key)
    if not positions:
        return df.iloc[0:0]
    return df.iloc[positions]


def search_by_phone(df, phone_map, phone_hash):
    positions = phone_map.get(str(phone_hash).strip().lower())
    if not positions:
        return df.iloc[0:0]
    return df.iloc[sorted(positions)]


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


st.markdown("""
<style>
  .stApp { background-color: BGC; color: TXT; font-family: 'Segoe UI', sans-serif; }
  .header-box { background-color: CRD; padding: 1.5rem; border-radius: 12px; border-top: 6px solid ACC; text-align: center; margin-bottom: 1rem; box-shadow: 0 4px 6px rgba(0,0,0,0.02); }
  .header-box h1 { color: TXT; font-size: 1.6rem; font-weight: 700; margin: 0; }
  .control-panel { background-color: CRD; padding: 1.5rem; border-radius: 12px; border: 1px solid BRD; max-width: 800px; margin: 0 auto; box-shadow: 0 4px 6px rgba(0,0,0,0.02); }
  .verdict-card { background-color: CRD; padding: 1.5rem; border-radius: 12px; border-left: 6px solid; margin-top: 1.5rem; box-shadow: 0 4px 6px rgba(0,0,0,0.02); }
  .verdict-card.warn { border-color: #FCD34D; }
  .verdict-card.ok { border-color: #86EFAC; }
  .verdict-card.neutral { border-color: #CBD5E1; }
  .verdict-card.miss { border-color: #FCA5A5; }
  .pastel-table-wrapper { overflow-x: auto; margin-top: 1rem; border-radius: 8px; border: 1px solid BRD; }
  table.pastel-grid { width: 100%; border-collapse: collapse; font-size: 0.9rem; background: CRD; text-align: center; }
  table.pastel-grid th { background: #E0E7FF; color: TXT; font-weight: 700; padding: 0.8rem; border-bottom: 2px solid #C7D2FE; font-size: 0.8rem; text-transform: uppercase; }
  table.pastel-grid td { padding: 0.8rem; border-bottom: 1px solid BRD; border-right: 1px solid BRD; white-space: nowrap; }
  table.pastel-grid td:last-child { border-right: none; }
  div[data-testid="stRadio"] > div { flex-direction: row; gap: 2rem; padding-bottom: 1rem; }
</style>
""".replace("BGC", BG_COLOR).replace("CRD", CARD_BG).replace("ACC", ACCENT)
   .replace("TXT", TEXT_MAIN).replace("BRD", BORDER), unsafe_allow_html=True)

st.markdown('<div class="header-box"><h1>Registration Lookup and Fee Verification</h1></div>',
            unsafe_allow_html=True)

try:
    df, phone_map, regno_map, loaded_at = load_live_data()
except Exception as exc:
    st.error("Data unavailable: " + str(exc))
    if st.button("Retry"):
        st.cache_resource.clear()
        st.rerun()
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
selected_programs = st.multiselect("Program Name", options=programs,
                                   placeholder="Filter by program...")

st.markdown("<hr style='margin: 1.2rem 0; border: none; border-top: 1px solid #E2E8F0;'>",
            unsafe_allow_html=True)

search_type = st.radio("Search Method", ["Registration Number", "Mobile Number"],
                       label_visibility="collapsed")
search_query = st.text_input("Search", placeholder="Enter Reg No or 10-digit Mobile...",
                             label_visibility="collapsed")

st.markdown('</div>', unsafe_allow_html=True)

foot1, foot2 = st.columns([4, 1])
with foot1:
    st.caption("{:,} records loaded. Last synced {} IST.".format(len(df), loaded_at.strftime("%d %b %Y, %I:%M %p")))
with foot2:
    if st.button("Refresh data"):
        st.cache_resource.clear()
        st.rerun()


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
              <th>mobile_no</th><th>whatsapp_number</th><th>father_mobile_no</th>
              <th>mother_mobile_no</th><th>class_recorded</th>
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
        results = search_by_regno(df, regno_map, search_query)
    else:
        phone_hash = hashlib.md5(search_query.strip().encode()).hexdigest()
        st.caption("Generated Masked Number: " + phone_hash)
        results = search_by_phone(df, phone_map, phone_hash)

    raw_hits = len(results)

    if not results.empty:
        d = results["_date_clean"]
        results = results[d.isna() | ((d >= start_date) & (d <= end_date))]
        if selected_programs:
            results = results[results["_program_clean"].isin(selected_programs)]

    with st.expander("Diagnostics"):
        st.write("Rows loaded:", len(df))
        st.write("Columns detected:", list(df.columns))
        st.write("Earliest date:", str(valid_dates.min()) if not valid_dates.empty else "NONE")
        st.write("Latest date:", str(valid_dates.max()) if not valid_dates.empty else "NONE")
        st.write("Rows with unreadable dates:", int(df["_date_clean"].isna().sum()))
        st.write("Matches before filters:", raw_hits)
        st.write("Matches after filters:", len(results))

    if results.empty:
        st.markdown('<div class="verdict-card miss"><h3>No results found</h3>'
                    '<p>Check the number, the date range and the program filter.</p></div>',
                    unsafe_allow_html=True)
    else:
        for _, row in results.iterrows():
            render_record_card(row.to_dict())
