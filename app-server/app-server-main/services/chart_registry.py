from collections import defaultdict
from config import CATEGORY_DEFAULT_FILTERS


CHART_REGISTRY = defaultdict(dict) 

def register_chart(name: str, *, supports_periods=True, supports_top_n=False, category: str, supports_period_type=True,  allowed_filters: list[str] | None = None):
    if not name or not category:
        raise ValueError("Both 'name' and 'category' must be non-empty strings")

    def decorator(cls):
        filters = allowed_filters if allowed_filters is not None else CATEGORY_DEFAULT_FILTERS.get(category, [])
        CHART_REGISTRY[category][name] = {
            "class": cls,
            "supports_periods": supports_periods, #annual/quarter/monthly
            "supports_period_type": supports_period_type, #Year_dropdown
            "supports_top_n": supports_top_n,
            "category": category,
            "allowed_filters": filters
        }
        return cls
    return decorator


def find_chart(chart_name: str):
    for category_charts in CHART_REGISTRY.values():
        if chart_name in category_charts:
            return category_charts[chart_name]
    return None
