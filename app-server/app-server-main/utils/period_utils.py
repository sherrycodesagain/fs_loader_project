import pandas as pd
from datetime import datetime, timedelta
import re
import pandas as pd
from datetime import datetime
from collections import OrderedDict
from calendar import monthrange

def get_fiscal_year(date, fiscal_month, fiscal_day):
    fiscal_end = safe_date(date.year, fiscal_month, fiscal_day)
    return date.year if date <= fiscal_end else date.year + 1

def get_filtered_period_data(df, fiscal_year_end, current_date=None):
    fiscal_month = fiscal_year_end.month
    fiscal_day = fiscal_year_end.day

    df['Date'] = pd.to_datetime(df['Date'])
    df['Month'] = df['Date'].dt.to_period('M').dt.to_timestamp()
    df['Fiscal Year'] = df['Date'].apply(lambda d: f"F{get_fiscal_year(d, fiscal_month, fiscal_day)}")

    full_fiscal_years = df.groupby('Fiscal Year')['Month'].nunique() == 12
    fiscal_years = full_fiscal_years[full_fiscal_years].index.tolist()
    df_full = df[df['Fiscal Year'].isin(fiscal_years)]

    result = {"full_fiscal_years": df_full}

    if current_date:
        fiscal_year = get_fiscal_year(current_date, fiscal_month, fiscal_day)

        ltm_start = current_date - pd.DateOffset(years=1) + pd.Timedelta(days=1)
        df_ltm = df[(df['Date'] >= ltm_start) & (df['Date'] <= current_date)].copy()
        df_ltm['Label'] = f"LTM {current_date.strftime('%b %Y')}"
        result['ltm'] = df_ltm


        ytd_start = datetime(fiscal_year - 1, fiscal_month, fiscal_day) + timedelta(days=1)
        df_ytd = df[(df['Date'] >= ytd_start) & (df['Date'] <= current_date)].copy()
        result['ytd'] = df_ytd

    return result

def calculate_period_ranges(df, label, fiscal_year_end):
    print(f"\n Calculating period range for label: '{label}'")
    fiscal_month = fiscal_year_end.month
    fiscal_day = fiscal_year_end.day
    try:
        start = pd.to_datetime(label, format="%B %Y")
        end = (start + pd.offsets.MonthEnd(0)).normalize()
        print(f" Matched Monthly: {start.date()} to {end.date()}")
        return {"periodRange": {"start": start, "end": end}}
    except Exception as e:
        print(f" Monthly match failed: {e}")

    match = re.match(r"Q([1-4]) (\d{4})", label)
    if match:
        q, year = int(match[1]), int(match[2])
        month = (q - 1) * 3 + 1
        start = pd.Timestamp(year=year, month=month, day=1)
        end = start + pd.offsets.QuarterEnd(0)
        print(f" Matched Quarterly: {start.date()} to {end.date()}")
        return {"periodRange": {"start": start, "end": end}}

    if label.startswith("F") and label[1:].isdigit():
        fiscal_year = int(label[1:])
        fy_end = pd.Timestamp(year=fiscal_year, month=fiscal_month, day=fiscal_day)
        start = (fy_end - pd.offsets.YearEnd(1)) + pd.Timedelta(days=1)
        end = fy_end
        print(f" Matched Annual: {start.date()} to {end.date()}")
        return {"periodRange": {"start": start, "end": end}}

    match = re.match(r"LTM (\w+ \d{4})", label)
    if match:
        try:
            end = pd.to_datetime(match.group(1))
            start = end - pd.DateOffset(years=1)
            print(f" Matched LTM: {start.date()} to {end.date()}")
            return {"periodRange": {"start": start, "end": end}}
        except Exception as e:
            print(f" LTM match failed: {e}")

    match = re.match(r"YTD F(\d{4})", label)
    if match:
        fiscal_year = int(match.group(1))
        fy_end = pd.Timestamp(year=fiscal_year, month=fiscal_month, day=fiscal_day)
        start = (fy_end - pd.offsets.YearEnd(1)) + pd.Timedelta(days=1)
        end = fy_end
        print(f" Matched YTD: {start.date()} to {end.date()}")
        return {"periodRange": {"start": start, "end": end}}

    print(" No period match found.")
    return {"periodRange": {"start": None, "end": None}}


def parse_date(date_str, fallback):
    try:
        if date_str:
            return pd.to_datetime(date_str)
    except Exception:
        pass
    return pd.to_datetime(fallback)

def sort_month_keys(period_dict):
    def parse_date_key(key):
        return pd.to_datetime(key, format="%B %Y", errors='coerce')
    return OrderedDict(
        sorted(period_dict.items(), key=lambda item: parse_date_key(item[0]))
    )


def fiscal_year_label(date, fiscal_month, fiscal_day):
    return f"F{get_fiscal_year(date, fiscal_month, fiscal_day)}"

def safe_date(year, month, day):
        last_day = monthrange(year, month)[1]
        return datetime(year, month, min(day, last_day))


def normalize_location(name):
    return name.strip()

def get_ltm_range(end_date):
    start = end_date - pd.DateOffset(months=12) + pd.DateOffset(days=1)
    end = end_date
    return start.normalize(), end.normalize()

def generate_periods_column(df, current_date, fiscal_year_end):
    fiscal_month = fiscal_year_end.month
    fiscal_day = fiscal_year_end.day

    def compute_periods(date):
        periods = []

        # Fiscal year
        fy = get_fiscal_year(date, fiscal_month, fiscal_day)
        periods.append({"period_type": "Fiscal Year", "period_label": f"F{fy}"})

        # YTD
        fy_start = datetime(fy - 1, fiscal_month, fiscal_day) + timedelta(days=1)
        if fy_start <= date <= current_date:
            periods.append({"period_type": "YTD", "period_label": f"YTD F{fy}"})

        # LTM
        ltm_start = current_date - pd.DateOffset(months=12) + pd.Timedelta(days=1)
        if ltm_start <= date <= current_date:
            ltm_label = f"LTM {current_date.strftime('%b %Y')}"
            periods.append({"period_type": "LTM", "period_label": ltm_label})

        return periods

    df['periods'] = df['Date'].apply(compute_periods)
    return df
