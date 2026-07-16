import json
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
from datetime import datetime

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HISTORY_HEADERS = [
    "serial", "name", "mobile", "amount", "purpose", "payment",
    "cheque_number", "credit_date", "issue_date", "pdf_file",
    "user", "status", "cancelled_by", "cancelled_at", "cancel_reason"
]

DONOR_HEADERS = ["NAME", "Mobile Number"]


@st.cache_resource
def get_gsheet_client():
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def get_sheet(tab_name: str):
    client = get_gsheet_client()
    sheet_url = st.secrets["gsheet_url"]
    spreadsheet = client.open_by_url(sheet_url)
    return spreadsheet.worksheet(tab_name)


# ── HISTORY ──────────────────────────────────────────────────

def load_history() -> list:
    try:
        ws = get_sheet("History")
        rows = ws.get_all_records()
        history = []
        for row in rows:
            record = dict(row)
            history.append(record)
        return history
    except Exception as e:
        import traceback
        st.error(f"Error loading history: {e}")
        st.code(traceback.format_exc())
        return []


def save_history(record: dict):
    try:
        ws = get_sheet("History")
        # Ensure headers exist
        existing = ws.get_all_values()
        if not existing:
            ws.append_row(HISTORY_HEADERS)
        # Build row in correct order
        row = [str(record.get(h, "")) for h in HISTORY_HEADERS]
        ws.append_row(row)
    except Exception as e:
        st.error(f"Error saving history: {e}")


def cancel_receipt(serial: str, cancelled_by: str, reason: str):
    try:
        ws = get_sheet("History")
        records = ws.get_all_values()
        if not records:
            return
        headers = records[0]
        serial_col = headers.index("serial") + 1
        status_col = headers.index("status") + 1
        cancelled_by_col = headers.index("cancelled_by") + 1
        cancelled_at_col = headers.index("cancelled_at") + 1
        cancel_reason_col = headers.index("cancel_reason") + 1

        for i, row in enumerate(records[1:], start=2):
            if len(row) > serial_col - 1 and row[serial_col - 1] == serial:
                ws.update_cell(i, status_col, "CANCELLED")
                ws.update_cell(i, cancelled_by_col, cancelled_by)
                ws.update_cell(i, cancelled_at_col, datetime.now().isoformat())
                ws.update_cell(i, cancel_reason_col, reason)
                break
    except Exception as e:
        st.error(f"Error cancelling receipt: {e}")


# ── SERIAL COUNTER ────────────────────────────────────────────

def get_serial(issue_date) -> str:
    try:
        if issue_date.month >= 4:
            fy = issue_date.year
        else:
            fy = issue_date.year - 1

        ws = get_sheet("Counter")
        stored_year = ws.cell(1, 1).value
        stored_count = ws.cell(1, 2).value

        try:
            stored_year = int(stored_year)
            stored_count = int(stored_count)
        except:
            stored_year = fy
            stored_count = 0

        if stored_year != fy:
            stored_count = 0

        new_count = stored_count + 1
        ws.update_cell(1, 1, fy)
        ws.update_cell(1, 2, new_count)

        return f"{new_count:03d}/{fy}"
    except Exception as e:
        st.error(f"Error getting serial: {e}")
        return "ERR/0000"


def reset_serial_counter(year: int, count: int = 0):
    try:
        ws = get_sheet("Counter")
        ws.update_cell(1, 1, year)
        ws.update_cell(1, 2, count)
    except Exception as e:
        st.error(f"Error resetting counter: {e}")


# ── DONORS ────────────────────────────────────────────────────

def load_donors_from_sheets() -> list:
    try:
        ws = get_sheet("Donors")
        rows = ws.get_all_records()
        return rows
    except Exception as e:
        import traceback
        st.error(f"Error loading donors: {e}")
        st.code(traceback.format_exc())
        return []


def save_donor_to_sheets(name: str, mobile: str):
    try:
        ws = get_sheet("Donors")
        existing = ws.get_all_values()
        if not existing:
            ws.append_row(DONOR_HEADERS)
        ws.append_row([name, mobile])
    except Exception as e:
        st.error(f"Error saving donor: {e}")


def update_donor_in_sheets(old_name: str, old_mobile: str, new_name: str, new_mobile: str):
    try:
        ws = get_sheet("Donors")
        records = ws.get_all_values()
        for i, row in enumerate(records[1:], start=2):
            if len(row) >= 2 and row[0] == old_name and row[1] == old_mobile:
                ws.update_cell(i, 1, new_name)
                ws.update_cell(i, 2, new_mobile)
                break
    except Exception as e:
        st.error(f"Error updating donor: {e}")


# ── LEGACY STUB (keeps import in app.py working) ──────────────
def log_to_sheets(record: dict):
    save_history(record)
