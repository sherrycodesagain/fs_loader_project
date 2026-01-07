from services.charts.base_chart import BaseChart
from services.chart_registry import register_chart

@register_chart(
    "sales_by_location",
    category="sales",
    supports_periods=False,       # ✅ No Monthly/Quarterly breakdown
    supports_top_n=False,
    supports_period_type=True     # ✅ Supports fiscal year / YTD / LTM (via `selected_period`)
)
class SalesByLocationChart(BaseChart):
    def get_chart_data(self):
        df = self.df
        df = self.apply_filters(df)

        if not self.selected_period:
            raise ValueError("Missing required 'selected_period' for this chart.")

        # ✅ Apply selected_period filters ONLY — not dates/quarters/years
        if self.selected_period:
            if self.selected_period.startswith("F"):
                df = df[df["fiscal_year"] == self.selected_period]
            elif self.selected_period.startswith("YTD"):
                df = df[df["ytd"] == self.selected_period]
            elif self.selected_period.startswith("LTM"):
                df = df[df["ltm"] == self.selected_period]

        # ✅ Clean location data
        df["location"] = df["location"].fillna("Unknown")
        df["location"] = df["location"].apply(self._clean_location)

        # ✅ Group and sort
        grouped = df.groupby("location")["amount"].sum().reset_index()
        grouped = grouped.sort_values("amount", ascending=False)

        labels = grouped["location"].tolist()
        values = grouped["amount"].round(2).tolist()

        return self.build_response(labels=labels, datasets=[{
            "label": f"Sales ({self.selected_period})" if self.selected_period else "Sales",
            "data": values
        }])

    def _clean_location(self, loc):
        parts = [p.strip() for p in loc.split(",")]
        if len(parts) == 3:
            return f"{parts[1]}, {parts[2]}"
        return parts[-1] if parts else "Unknown"
