import re
import pandas as pd
import streamlit as st
import rules

PHONE_COLUMNS = ["mobile_no", "father_mobile_no", "mother_mobile_no", "class_recorded_mobile_no", "whatsapp_number"]


def clean_regno(value) -> str:
    if pd.isna(value) or value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"\.0+$", "", text)
    return re.sub(r"\D", "", text)


@st.cache_data(show_spinner=False, max_entries=1)
def load_live_data(sync_key: str) -> pd.DataFrame:
    cfg = dict(st.secrets.get("sheet", {}))
    url = cfg.get("csv_url")
    if not url:
        raise ValueError("CSV URL missing.")
    if "pubhtml" in url:
        raise ValueError("csv_url points to a web page (pubhtml). Use the /pub?...&output=csv link.")

    # No on_bad_lines='skip' - we want to SEE errors, not silently drop rows
    df = pd.read_csv(url, dtype=str, keep_default_na=False)
    df.columns = [str(c).strip().casefold() for c in df.columns]

    # Map core columns
    reg_col = next((c for c in ["regno", "reg_no", "registration no", "reg no"] if c in df.columns), None)
    prog_col = next((c for c in ["all_program", "program", "program_name", "course"] if c in df.columns), None)
    fee_col = next((c for c in ["fees_paid", "fee_paid", "fees", "fee"] if c in df.columns), None)
    date_col = next((c for c in ["joining_date_timestamp", "joining_date", "date", "call date"] if c in df.columns), None)

    if reg_col is None:
        raise ValueError(f"regno column not found. Columns seen: {list(df.columns)}")

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
        df["_date_clean"] = pd.NaT

    for col in PHONE_COLUMNS:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.lower()

    # Plain integer
