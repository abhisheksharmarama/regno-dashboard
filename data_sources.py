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

    # THE FIX: Added on_bad_lines='skip' to bypass stray commas in user data
    df = pd.read_csv(
        url, 
        dtype=str, 
        keep_default_na=False, 
        on_bad_lines='skip',
        engine='python' # Uses the more forgiving Python parser
    )
    
    df.columns = [str(c).strip().casefold() for c in df.columns]

    # Map core columns
    reg_col = next((c for c in ["regno", "reg_no", "registration no", "reg no"] if c in df.columns), df.columns[0])
    prog_col = next((c for c in ["all_program", "program", "program_name", "course"] if c in df.columns), None)
    fee_col = next((c for c in ["fees_paid", "fee_paid", "fees", "fee"] if c in df.columns), None)
    date_col = next((c for c in ["joining_date_timestamp", "joining_date", "date", "call date"] if c in df.columns), None)
    
    # Process data in-place for max speed
    df["_regno_clean"] = df[reg_col].apply(clean_regno)
    df["_program_clean"] = df[prog_col].astype("category") if prog_col else "Unknown"
    df["_fee_clean"] = df[fee_col].apply(rules.parse_fee) if fee_col else 0.0

    if date_col:
        df["_date_clean"] = pd.to_datetime(df[date_col], errors="coerce").dt.date
    else:
        df["_date_clean"] = pd.NaT

    for col in PHONE_COLUMNS:
        if col in df.columns:
            df[col] = df[col].str.strip().str.lower()

    return df.set_index("_regno_clean", drop=False)

def search_by_regno(df: pd.DataFrame, regno: str):
    key = clean_regno(regno)
    if not key or key not in df.index:
        return pd.DataFrame()
    res = df.loc[[key]]
    return res

def search_by_phone(df: pd.DataFrame, phone_hash: str) -> pd.DataFrame:
    valid_cols = [c for c in PHONE_COLUMNS if c in df.columns]
    if not valid_cols:
        return pd.DataFrame()
    
    mask = pd.Series(False, index=df.index)
    for col in valid_cols:
        mask = mask | (df[col] == phone_hash)
    return df[mask]
