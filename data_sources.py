import sqlite3
import pandas as pd
import streamlit as st
import re
import os

DB_FILE = "registrations.db"
PHONE_COLS = ["mobile_no", "father_mobile_no", "mother_mobile_no", "class_recorded_mobile_no", "whatsapp_number"]

def clean_regno(value):
    if pd.isna(value) or value is None: return ""
    text = str(value).strip()
    text = re.sub(r"\.0+$", "", text)
    return re.sub(r"\D", "", text)

# This caches the connection and prevents RAM bloat
@st.cache_resource(show_spinner=False)
def sync_sqlite_db(sync_key: str):
    cfg = dict(st.secrets.get("sheet", {}))
    url = cfg.get("csv_url")
    
    if not url:
        raise ValueError("Google Sheet CSV URL missing in Secrets.")
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS regs")
    conn.commit()
    
    # Download the CSV in small, memory-safe chunks
    for chunk in pd.read_csv(url, chunksize=25000, dtype=str, keep_default_na=False):
        chunk.columns = [str(c).strip().casefold() for c in chunk.columns]
        
        # Identify core columns dynamically
        reg_col = next((c for c in ["regno", "reg_no", "registration no", "reg no"] if c in chunk.columns), chunk.columns[0])
        chunk["_regno_clean"] = chunk[reg_col].apply(clean_regno)
        
        for p_col in PHONE_COLS:
            if p_col in chunk.columns:
                chunk[p_col] = chunk[p_col].str.strip().str.lower()
                
        # Format dates strictly for easy filtering
        date_col = next((c for c in ["joining_date", "date", "call date", "timestamp", "joining_date_timestamp"] if c in chunk.columns), None)
        if date_col:
            chunk["_date_clean"] = pd.to_datetime(chunk[date_col], errors="coerce", dayfirst=True).dt.strftime('%Y-%m-%d')
        else:
            chunk["_date_clean"] = ""
            
        chunk.to_sql("regs", conn, if_exists="append", index=False)
    
    # Create indexes so searches take milliseconds instead of seconds
    cursor.execute("CREATE INDEX idx_regno ON regs(_regno_clean)")
    for p_col in PHONE_COLS:
        try:
            cursor.execute(f"CREATE INDEX idx_{p_col} ON regs({p_col})")
        except:
            pass
            
    conn.close()
    return True

def search_regno(regno: str) -> pd.DataFrame:
    """Queries the hard drive database for a Reg No."""
    conn = sqlite3.connect(DB_FILE)
    clean_reg = clean_regno(regno)
    df = pd.read_sql("SELECT * FROM regs WHERE _regno_clean = ?", conn, params=(clean_reg,))
    conn.close()
    return df

def search_phone(phone_hash: str) -> pd.DataFrame:
    """Queries the hard drive database for a Phone Hash."""
    conn = sqlite3.connect(DB_FILE)
    
    # Dynamically build a query to check all phone columns
    df_cols = pd.read_sql("PRAGMA table_info(regs)", conn)
    valid_cols = [c for c in PHONE_COLS if c in df_cols['name'].tolist()]
    
    if not valid_cols:
        conn.close()
        return pd.DataFrame()
        
    query_parts = [f'"{col}" = ?' for col in valid_cols]
    query = "SELECT * FROM regs WHERE " + " OR ".join(query_parts)
    params = tuple([phone_hash] * len(valid_cols))
    
    df = pd.read_sql(query, conn, params=params)
    conn.close()
    return df

def get_unique_programs() -> list:
    """Instantly fetches dropdown options from the DB."""
    if not os.path.exists(DB_FILE):
        return []
    try:
        conn = sqlite3.connect(DB_FILE)
        df_cols = pd.read_sql("PRAGMA table_info(regs)", conn)
        cols = df_cols['name'].tolist()
        p_col = next((c for c in ["all_program", "program", "program_name", "course"] if c in cols), None)
        
        if p_col:
            progs = pd.read_sql(f'SELECT DISTINCT "{p_col}" FROM regs WHERE "{p_col}" IS NOT NULL AND "{p_col}" != ""', conn)
            conn.close()
            return sorted(progs.iloc[:, 0].tolist())
        conn.close()
    except Exception:
        pass
    return []
