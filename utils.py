import re
import pandas as pd
from datetime import datetime
from typing import Any, Optional

def clean_currency(value: Any) -> float:
    """
    Robustly cleans currency values from strings or numbers.
    Removes currency symbols (₹), commas, and other non-numeric characters.
    """
    if pd.isna(value) or value == "" or value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    
    try:
        # Convert to string and clean
        clean_val = str(value).replace('₹', '').replace(',', '').strip()
        # Remove everything except digits and decimal point
        clean_val = re.sub(r"[^\d.]", "", clean_val)
        return float(clean_val) if clean_val else 0.0
    except (ValueError, TypeError):
        return 0.0

def format_date(value: Any) -> str:
    """Formats a date value into a YYYY-MM-DD string."""
    if pd.isna(value) or value is None:
        return "N/A"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, str):
        # Try to parse and re-format if it's already a date string
        try:
            return pd.to_datetime(value, dayfirst=True).strftime("%Y-%m-%d")
        except:
            return value
    return str(value)

def get_value_by_label(df: pd.DataFrame, label: str, col_offset: int = 1) -> float:
    """
    Searches for a label in the entire dataframe and returns the value 
    from a cell with the given column offset.
    """
    mask = df.apply(lambda row: row.astype(str).str.contains(label, case=False, na=False).any(), axis=1)
    if mask.any():
        row_idx = df[mask].index[0]
        row = df.loc[row_idx]
        # Find which column contains the label
        for col_idx, val in enumerate(row):
            if label.lower() in str(val).lower():
                target_col = col_idx + col_offset
                if target_col < len(row):
                    return clean_currency(row.iloc[target_col])
    return 0.0
