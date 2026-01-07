# services/filter_resolver.py

from config import CATEGORY_DEFAULT_FILTERS

class FilterResolver:
    def __init__(self, chart_meta: dict):
        self.chart_meta = chart_meta
        self.category = chart_meta["category"]
        self.allowed_filters = chart_meta.get("allowed_filters")

    def resolve(self) -> list[str]:
        if self.allowed_filters is not None:
            return self.allowed_filters
        return CATEGORY_DEFAULT_FILTERS.get(self.category, [])
