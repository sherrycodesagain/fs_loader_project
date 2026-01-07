from abc import ABC, abstractmethod
from typing import Dict, Any
import pandas as pd
from cache.memory_store import memory_store
from config import COMPANY_NAME, CURRENCY, DENOMINATION, DEFAULT_FISCAL_YEAR_END, CURRENT_DATE_INPUT
from datetime import datetime

class BaseChart(ABC):
    def __init__(self, dataset_id: str, period_type: str, selected_period: str, filters: Dict[str, Any], **kwargs):
        self.dataset_id = dataset_id
        self.period_type = period_type
        self.selected_period = selected_period
        self.filters = filters
        self.active_time_filter_type = kwargs.get("active_time_filter_type")
        self.df = self._get_dataset()
        self.extra = kwargs
        
    def _get_dataset(self) -> pd.DataFrame:
        if self.dataset_id not in memory_store:
            raise ValueError(f"Dataset '{self.dataset_id}' not loaded.")
        return memory_store[self.dataset_id]["enriched_df"].copy()

    @abstractmethod
    def get_chart_data(self) -> Dict[str, Any]:
        """Main method to be implemented by all child charts."""
        pass
    
    def apply_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        for key, values in self.filters.items():
            if key in df.columns:
                df = df[df[key].isin(values)]
            else:
                pass
        return df
    
    def get_updated_filters(self, df: pd.DataFrame, limit_to_keys: list[str] = None) -> dict:
        """Returns available filter options based on already filtered DataFrame.

        If `limit_to_keys` is provided, only those columns will be returned (e.g., for Top N visible entries).
        """
        updated_filters = {}

        target_keys = limit_to_keys if limit_to_keys is not None else self.filters.keys()

        for column in target_keys:
            if column in df.columns:
                updated_filters[column] = sorted(df[column].dropna().unique().tolist())

        return updated_filters


    def apply_period_filter(self, df: pd.DataFrame) -> tuple[pd.DataFrame, str]:
        if self.period_type == "Monthly":
            group_col = "month"
            if self.selected_period.startswith("F"):
                df = df[df["fiscal_year"] == self.selected_period]
            elif self.selected_period.startswith("YTD"):
                df = df[df["ytd"] == self.selected_period]
            elif self.selected_period.startswith("LTM"):
                df = df[df["ltm"] == self.selected_period]

        elif self.period_type == "Quarterly":
            if self.selected_period.startswith("YTD"):
                df = df[df["quarter_ytd"].str.endswith(self.selected_period)]
                group_col = "quarter_ytd"
            elif self.selected_period.startswith("LTM"):
                df = df[df["quarter_ltm"].str.endswith(self.selected_period)]
                group_col = "quarter_ltm"
            else:
                df = df[df["fiscal_quarter"].str.endswith(self.selected_period)]
                group_col = "fiscal_quarter"
            

        elif self.period_type == "Annual":
            if "period_label" not in df.columns:
                df["period_label"] = df.apply(
                    lambda row: row["ytd"] or row["ltm"] or row["fiscal_year"], axis=1
                )
            group_col = "period_label"

        else:
            raise ValueError(f"Invalid period_type: {self.period_type}")

        return df, group_col
        

    def get_groupings(self, grouping_type: str) -> dict:
        if grouping_type not in self.df.columns:
            raise ValueError(f"Invalid grouping type: {grouping_type}")

        df = self.df[[grouping_type, "type"]].dropna().drop_duplicates()

        grouped = (
            df.groupby("type")[grouping_type]
            .apply(lambda x: sorted(x.dropna().unique()))
            .to_dict()
        )

        return {
            "grouping_type": grouping_type,
            "values": grouped
        }
    
    


    def build_response(self, labels, datasets) -> Dict[str, Any]:
        
        """Standardized response format for chart data."""
        current_date = datetime.strptime(CURRENT_DATE_INPUT, "%Y-%m-%d").date()

        return {
            "labels": labels,
            "datasets": datasets,
            "currency": CURRENCY,
            "denomination": DENOMINATION,
            "company": COMPANY_NAME,
            "fiscal_year_end": DEFAULT_FISCAL_YEAR_END,
             "current_date": current_date.isoformat()
        }
