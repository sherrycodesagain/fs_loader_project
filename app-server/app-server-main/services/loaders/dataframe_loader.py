import pandas as pd
from datetime import datetime, timedelta
from utils.period_utils import get_fiscal_year, safe_date
from cache.memory_store import memory_store
from config import (
    COMPANY_NAME,
    CURRENCY,
    DENOMINATION,
    CURRENT_DATE_INPUT,
    DEFAULT_FISCAL_YEAR_END
)

class DataFrameLoader:
    def __init__(self, excel_path: str, dataset_id: str):
        self.excel_path = excel_path
        self.dataset_id = dataset_id
        self.df = None
        self.current_date = pd.to_datetime(CURRENT_DATE_INPUT)
        self.fiscal_year_end = pd.to_datetime(DEFAULT_FISCAL_YEAR_END)
        self.fiscal_month = self.fiscal_year_end.month
        self.fiscal_day = self.fiscal_year_end.day
        self.fiscal_month_start = (self.fiscal_month % 12) + 1

    def load_and_store(self):
        self.df = pd.read_excel(self.excel_path)
        self._clean_and_transform()
        self._tag_periods()
        self._finalize()
        self._exclude_incomplete_fiscal_years()
        
        def determine_period_label(row):
            if row["ytd"]:
                return row["ytd"]
            if row["ltm"]:
                return row["ltm"]
            if row["fiscal_year"] in self.valid_fys:
                return row["fiscal_year"]
            return ""

        self.df["period_label"] = self.df.apply(determine_period_label, axis=1)

        grouped = (
            self.df
            .dropna(subset=["period_label"])   # ignore rows with no label
            .groupby("period_label")["month"]
            .unique()
            .to_dict()
        )

        month_to_quarter = {}
        for _, row in self.df.iterrows():
            month = row.get("month")
            quarter = row.get("fiscal_quarter")
            if isinstance(month, str) and isinstance(quarter, str):
                month_to_quarter[month] = quarter
  
        memory_store[self.dataset_id] = {
            "enriched_df": self.df,
            "filters": self._extract_filter_metadata(),
            "chart_cache": {},
            "period_ranges": self._build_period_ranges(),
            "valid_fiscal_years": self.valid_fys,
            "month_to_quarter": month_to_quarter
        }

    def _exclude_incomplete_fiscal_years(self):
        grouped = (
            self.df[self.df["fiscal_year"].str.match(r"^F\d{4}$", na=False)]
            .groupby("fiscal_year")["month"]
            .agg(lambda months: sorted(set(months)))
            .reset_index(name="months_in_fy")
        )
        grouped["month_count"] = grouped["months_in_fy"].apply(len)

        valid_fys = grouped.query("month_count == 12")["fiscal_year"].tolist()

        self.df = self.df[
            self.df["fiscal_year"].isin(valid_fys) |
            self.df["ytd"].str.strip().astype(bool)
        ]
        self.valid_fys = valid_fys


    def _clean_and_transform(self):
        rename_map = {
            "Original Currency (CAD)": "currency",
            "Customer": "customer",
            "Location": "location",
            "Account Name": "product",
            "Amount": "amount",
            "Date": "date",
            "Quantity": "quantity",
            "Price": "price"
        }

        self.df.rename(columns=rename_map, inplace=True)
       
        self.df['date'] = pd.to_datetime(self.df['date'])
        self.df['month'] = self.df['date'].dt.strftime("%B %Y")
        self.df['fiscal_year'] = self.df['date'].apply(
            lambda d: f"F{get_fiscal_year(d, self.fiscal_month, self.fiscal_day)}"
        )
        self.df['IsOriginalRow'] = True

    def _tag_periods(self):
        self.df['ytd'] = self.df['date'].apply(self._assign_ytd)
        self.df['ltm'] = self.df['date'].apply(self._assign_ltm)
        self.df['fiscal_quarter'] = self.df['date'].apply(self._get_fiscal_quarter)
        self.df['quarter_ytd'] = self.df.apply(lambda row: self._get_quarter_period(row['date'], row['ytd']), axis=1)
        self.df['quarter_ltm'] = self.df.apply(lambda row: self._get_quarter_period(row['date'], row['ltm']), axis=1)
        

    def _finalize(self):
        self.df = self.df.rename(columns=lambda col: col.strip())
        self.df = self.df.fillna({
            col: "" if self.df[col].dtype == 'object' else 0
            for col in self.df.columns
        })

        for col in ["amount", "currency", "customer", "location", "product"]:
            if col in self.df.columns:
                self.df[col] = self.df[col].apply(lambda x: str(x).strip() if isinstance(x, str) else x)
        self.df["company"] = COMPANY_NAME
        self.df["denomination"] = DENOMINATION
        self.df["dataset_id"] = self.dataset_id

        if "aging_group" in self.df.columns:
            aging_debug = self.df.groupby("aging_group")["amount"].sum().round(2)
            for group, total in aging_debug.items():
                print(f" - {group}: {total}")


    def _assign_ytd(self, date):
        current_fy = get_fiscal_year(self.current_date, self.fiscal_month, self.fiscal_day)
        fiscal_start = safe_date(current_fy - 1, self.fiscal_month, self.fiscal_day) + timedelta(days=1)
        if fiscal_start <= date <= self.current_date:
            return f"YTD F{current_fy}"
        return ""

    def _assign_ltm(self, date):
        ltm_start = self.current_date - pd.DateOffset(years=1) + timedelta(days=1)
        if ltm_start <= date <= self.current_date:
            return f"LTM {self.current_date.strftime('%b %Y')}"
        return ""

    def _get_fiscal_quarter(self, date):
        offset = (date.month - self.fiscal_month_start + 12) % 12
        quarter = (offset // 3) + 1
        fiscal_year = get_fiscal_year(date, self.fiscal_month, self.fiscal_day)
        return f"Q{quarter} F{fiscal_year}"

    def _get_quarter_period(self, date, period):
        if not isinstance(period, str) or not period:
            return ""

        def relative_quarter(d, start):
            offset = (d.year - start.year) * 12 + (d.month - start.month)
            return f"Q{(offset // 3) + 1}" if 0 <= offset <= 11 else ""

        if period.startswith("LTM"):
            start = self.current_date - pd.DateOffset(years=1) + timedelta(days=1)
            return f"{relative_quarter(date, start)} {period}".strip()

        if period.startswith("YTD"):
            fy = get_fiscal_year(self.current_date, self.fiscal_month, self.fiscal_day)
            start = safe_date(fy - 1, self.fiscal_month, self.fiscal_day) + timedelta(days=1)
            return f"{relative_quarter(date, start)} {period}".strip()

        return ""

    def _extract_filter_metadata(self):
        filters = {}
        for field in [
            "customer", "location", "currency", "product",
            "month", "fiscal_year", "ytd", "ltm",
            "fiscal_quarter", "quarter_ytd", "quarter_ltm", "period_label"
        ]:
            if field in self.df.columns:
                filters[field] = sorted([
                    p for p in self.df[field].dropna().unique().tolist() if str(p).strip()
                ])
        return filters


    def _build_period_ranges(self):
        period_ranges = {}

        def extract_range(label, date_mask):
            months = (
                self.df[date_mask]["month"]
                .dropna()
                .unique()
                .tolist()
            )
            dates = self.df[date_mask]["date"]
            if not dates.empty:
                return {
                    "start": dates.min().normalize(),
                    "end": dates.max().normalize(),
                    "months": sorted(months, key=lambda x: pd.to_datetime(x))
                }
            return None

        # Fiscal Years — only for valid FYs
        for fy in self.valid_fys:
            date_mask = self.df["fiscal_year"] == fy
            range_info = extract_range(fy, date_mask)
            if range_info:
                period_ranges[fy] = range_info

        # YTDs
        for ytd_label in self.df["ytd"].dropna().unique():
            if not ytd_label.strip():
                continue
            date_mask = self.df["ytd"] == ytd_label
            range_info = extract_range(ytd_label, date_mask)
            if range_info:
                period_ranges[ytd_label] = range_info

        # LTMs
        for ltm_label in self.df["ltm"].dropna().unique():
            if not ltm_label.strip():
                continue
            date_mask = self.df["ltm"] == ltm_label
            range_info = extract_range(ltm_label, date_mask)
            if range_info:
                period_ranges[ltm_label] = range_info

        return period_ranges




    def _calculate_period_range(self, label):
        fiscal_month = self.fiscal_month
        fiscal_day = self.fiscal_day

        try:
            # Monthly period, e.g., "March 2023"
            start = pd.to_datetime(label, format="%B %Y")
            end = (start + pd.offsets.MonthEnd(0)).normalize()
            return {"start": start, "end": end}
        except:
            pass

        import re
        match = re.match(r"Q([1-4]) (\d{4})", label)
        if match:
            q, year = int(match[1]), int(match[2])
            month = (q - 1) * 3 + 1
            start = pd.Timestamp(year=year, month=month, day=1)
            end = start + pd.offsets.QuarterEnd(0)
            return {"start": start, "end": end}

        if label.startswith("F") and label[1:].isdigit():
            fy = int(label[1:])
            fy_end = safe_date(fy, fiscal_month, fiscal_day)
            start = (fy_end - pd.offsets.YearEnd(1)) + pd.Timedelta(days=1)
            end = fy_end
            return {"start": start, "end": end}

        match = re.match(r"LTM (\w+ \d{4})", label)
        if match:
            end = pd.to_datetime(match.group(1))
            start = end - pd.DateOffset(years=1) + timedelta(days=1)
            return {"start": start, "end": end}

        match = re.match(r"YTD F(\d{4})", label)
        if match:
            fy = int(match.group(1))
            fy_end = safe_date(fy, fiscal_month, fiscal_day)
            start = (fy_end - pd.offsets.YearEnd(1)) + pd.Timedelta(days=1)
            end = fy_end
            return {"start": start, "end": end}

        return {"start": None, "end": None}
