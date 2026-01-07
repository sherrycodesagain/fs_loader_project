import pandas as pd
from datetime import datetime, timedelta
from utils.period_utils import get_fiscal_year
from cache.memory_store import memory_store
from config import (
    COMPANY_NAME,
    CURRENCY,
    DENOMINATION,
    CURRENT_DATE_INPUT,
    DEFAULT_FISCAL_YEAR_END
)


class ARAPDataFrameLoader:
    def __init__(self, excel_path: str, dataset_id: str, data_type: str = "AR"):
        assert data_type in ["AR", "AP"], "data_type must be either 'AR' or 'AP'"
        self.excel_path = excel_path
        self.dataset_id = dataset_id
        self.data_type = data_type
        self.df = None
        self.current_date = pd.to_datetime(CURRENT_DATE_INPUT)
        self.fiscal_year_end = pd.to_datetime(DEFAULT_FISCAL_YEAR_END)
        self.fiscal_month = self.fiscal_year_end.month
        self.fiscal_day = self.fiscal_year_end.day

    def load_and_store(self):
        self.df = pd.read_excel(self.excel_path)
        self._clean_and_transform()
        self._melt_aging()
        self._tag_periods()
        self._exclude_incomplete_fiscal_years()
        self._finalize()

        period_ranges = self._build_period_ranges()

        memory_store[self.dataset_id] = {
            "enriched_df": self.df,
            "filters": self._extract_filter_metadata(),
            "chart_cache": {},
            "period_ranges": self._build_period_ranges(),
            "valid_fiscal_years": self.valid_fys,
            "valid_ltm":self.valid_ltm_labels
        }

    def _build_period_ranges(self):
        period_ranges = {}
        valid_period_labels = set(self.valid_fys + self.valid_ltm_labels)

        for label in valid_period_labels:
            label = str(label)
            if not label.strip():
                continue
            try:
                range_info = self._calculate_period_range(label)

                months = self.df[self.df["period_label"] == label]["month"].dropna().unique().tolist()
                range_info["months"] = sorted(months)

                period_ranges[label] = range_info
            except Exception as e:
                print(f"⚠️ Failed to parse period '{label}': {e}")
                continue

        return period_ranges

    
    def _exclude_incomplete_fiscal_years(self):
        # Prepare month & year fields just in case
        self.df["month"] = self.df["date"].dt.strftime("%B %Y")
        self.df["month_num"] = self.df["date"].dt.month
        self.df["year"] = self.df["date"].dt.year

        # 1. Fiscal Year logic
        fy_end_month = self.fiscal_month  # e.g., 3 (March)
        fy_month_check = self.df[self.df["month_num"] == fy_end_month]
        valid_fys = fy_month_check["fiscal_year"].dropna().unique().tolist()

        # 2. LTM logic
        current_month_label = self.current_date.strftime("%B %Y")  # e.g., "December 2023"
        ltm_month_check = self.df[self.df["month"] == current_month_label]
        valid_ltm_labels = ltm_month_check["ltm"].dropna().unique().tolist()

        # 3. Filter the DataFrame to keep:
        # - Valid fiscal years
        # - Valid LTM
        # - Any YTD (no validation required)
        self.df = self.df[
            (self.df["fiscal_year"].isin(valid_fys)) |
            (self.df["ltm"].isin(valid_ltm_labels)) |
            (self.df["ytd"].astype(str).str.strip().astype(bool))
        ]

        # Save valid period labels if you want to use them elsewhere
        self.valid_fys = valid_fys
        self.valid_ltm_labels = valid_ltm_labels

    def get_complete_periods_with_months(self):
        """Returns only those period_labels that have 12 full months of data."""
        if self.df is None or "period_label" not in self.df.columns or "month" not in self.df.columns:
            print("❌ DataFrame is not ready or missing necessary columns.")
            return {}

        # Group by period_label and collect unique months
        period_to_months = self.df.groupby("period_label")["month"].unique().to_dict()

        complete_periods = {}
        for period, months in period_to_months.items():
            if len(months) >= 12:
                complete_periods[period] = list(months)
            else:
                print(f"⚠️ Skipping incomplete period: {period} — Only {len(months)} months")
        print(complete_periods)
        return complete_periods

    def _calculate_period_range(self, label):
        try:
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
            fy_end = pd.Timestamp(year=fy, month=self.fiscal_month, day=self.fiscal_day)
            start = fy_end - pd.DateOffset(years=1) + pd.Timedelta(days=1)
            return {"start": start, "end": fy_end}

        normalized_label = label.strip().lower()

        match = re.match(r"ltm (\w+ \d{4})", normalized_label)
        if match:
            end = pd.to_datetime(match.group(1))
            start = end - pd.DateOffset(years=1) + pd.Timedelta(days=1)
            return {"start": start, "end": end}

        match = re.match(r"ytd f(\d{4})", normalized_label)
        if match:
            fy = int(match.group(1))
            fy_end = pd.Timestamp(year=fy, month=self.fiscal_month, day=self.fiscal_day)
            start = fy_end - pd.DateOffset(years=1) + pd.Timedelta(days=1)
            return {"start": start, "end": fy_end}

        return {"start": None, "end": None}


    def _clean_and_transform(self):
        self.df.columns = self.df.columns.str.strip().str.lower()

        id_column = "customer" if self.data_type == "AR" else "vendor"

        self.df = self.df.rename(columns={
            id_column: "customer"
        })

        if "date" not in self.df.columns:
            raise ValueError("Missing 'date' column in Excel file")

        self.df["date"] = pd.to_datetime(self.df["date"], errors="coerce")
        self.df = self.df[self.df["date"].notna()]
        self.df["is_original_row"] = True


    def _melt_aging(self):
        known_id_columns = {"customer", "currency", "date"}
        internal_columns = {"is_original_row", "fiscal_year", "ytd", "ltm", "fiscal_quarter", "quarter_ytd", "quarter_ltm", "period_label", "company", "denomination", "dataset_id", "data_type"}

        potential_aging = [
            col for col in self.df.columns
            if col not in known_id_columns
            and col not in internal_columns
            and pd.api.types.is_numeric_dtype(self.df[col])
        ]

        if not potential_aging:
            raise ValueError("❌ No aging columns found dynamically.")

        self.df = self.df.melt(
            id_vars=["customer", "currency", "date"],
            value_vars=potential_aging,
            var_name="aging_group",
            value_name="amount"
        )

        self.df = self.df[self.df["amount"].notna()]
        self.df["amount"] = self.df["amount"].astype(float)


    def _tag_periods(self):
        self.df["month"] = self.df["date"].dt.strftime("%B %Y")
        self.df["fiscal_year"] = self.df["date"].apply(
            lambda d: f"F{get_fiscal_year(d, self.fiscal_month, self.fiscal_day)}"
        )
    
        self.df["ytd"] = self.df["date"].apply(self._assign_ytd)
        self.df["ltm"] = self.df["date"].apply(self._assign_ltm)
        self.df["fiscal_quarter"] = self.df["date"].apply(self._get_fiscal_quarter)
        self.df["quarter_ytd"] = self.df.apply(lambda row: self._get_quarter_period(row["date"], row["ytd"]), axis=1)
        self.df["quarter_ltm"] = self.df.apply(lambda row: self._get_quarter_period(row["date"], row["ltm"]), axis=1)

        # Exclude incomplete fiscal years before assigning period_label
        #self._exclude_incomplete_fiscal_years()

        def determine_period_label(row):
            if row["ytd"]:
                return row["ytd"]
            if row["ltm"]:
                return row["ltm"]
            if row["fiscal_year"]:
                return row["fiscal_year"]
            return ""

        self.df["period_label"] = self.df.apply(determine_period_label, axis=1)

    def _assign_ytd(self, date):
        current_fy = get_fiscal_year(self.current_date, self.fiscal_month, self.fiscal_day)
        fiscal_start = datetime(current_fy - 1, self.fiscal_month, self.fiscal_day) + timedelta(days=1)
        if fiscal_start <= date <= self.current_date:
            return f"YTD F{current_fy}"
        return ""

    def _assign_ltm(self, date):
        ltm_start = self.current_date - pd.DateOffset(years=1) + timedelta(days=1)

        # ✅ Add this debug only once (not for every row)
        if not hasattr(self, "_ltm_window_printed"):
            self._ltm_window_printed = True  # so it only prints once
        if ltm_start <= date <= self.current_date:
            return f"LTM {self.current_date.strftime('%b %Y')}"
        return ""

    def _get_fiscal_quarter(self, date):
        offset = (date.month - self.fiscal_month + 12) % 12
        quarter = (offset // 3) + 1
        fiscal_year = get_fiscal_year(date, self.fiscal_month, self.fiscal_day)
        return f"Q{quarter} F{fiscal_year}"

    def _get_quarter_period(self, date, period):
        if not isinstance(period, str) or not period.strip():
            return ""

        def relative_quarter(d, start):
            offset = (d.year - start.year) * 12 + (d.month - start.month)
            return f"Q{(offset // 3) + 1}" if 0 <= offset <= 11 else ""

        if period.startswith("ltm"):
            start = self.current_date - pd.DateOffset(years=1) + timedelta(days=1)
            return f"{relative_quarter(date, start)} {period}".strip()

        if period.startswith("ytd"):
            fy = get_fiscal_year(self.current_date, self.fiscal_month, self.fiscal_day)
            start = datetime(fy - 1, self.fiscal_month, self.fiscal_day) + timedelta(days=1)
            return f"{relative_quarter(date, start)} {period}".strip()

        return ""

    def _finalize(self):
        self.df.columns = self.df.columns.str.strip().str.lower().str.replace(" ", "_")
        self.df.fillna("", inplace=True)
        for col in ["amount", "currency", "customer"]:
            if col in self.df.columns:
                self.df[col] = self.df[col].apply(lambda x: str(x).strip() if isinstance(x, str) else x)
        self.df["company"] = COMPANY_NAME
        self.df["denomination"] = DENOMINATION
        self.df["dataset_id"] = self.dataset_id
        self.df["data_type"] = self.data_type
    def _extract_filter_metadata(self):
        filters = {}
        for field in [
            "customer", "currency", "aging_group", "month", "fiscal_year",
            "ytd", "ltm", "fiscal_quarter", "quarter_ytd", "quarter_ltm"
        ]:
            if field in self.df.columns:
                filters[field] = sorted([p for p in self.df[field].dropna().unique().tolist() if str(p).strip()])
        return filters
