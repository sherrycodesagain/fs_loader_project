from services.charts.base_chart import BaseChart
from cache.memory_store import memory_store
from services.chart_registry import register_chart
import pandas as pd


@register_chart(
    "net_income_waterfall",
    category="financials",
    supports_periods=False,
    supports_period_type=True,
    supports_top_n=False
)
class FSWaterfallChart(BaseChart):

    def _adjust_taxes_for_overlap(self, taxes_end, end_period, start_period):
        fiscal_year_end = memory_store[self.dataset_id].get("fiscal_year_end")

        # Parse period endings
        if end_period.startswith("LTM") and start_period.startswith("F") and fiscal_year_end:
            fiscal_year_end = pd.to_datetime(fiscal_year_end)

            # Try to parse end month from label: "LTM Dec 2023" -> "2023-12-31"
            try:
                ltm_end = pd.to_datetime(end_period.replace("LTM ", "") + " 01")
                ltm_end = ltm_end + pd.offsets.MonthEnd(0)  # get last day of month
            except Exception as e:
                print(f"⚠️ Could not parse LTM end date from: {end_period} → {e}")
                return taxes_end  # fallback to unadjusted

            # If LTM covers full fiscal year → skip overlap adjustment
            if ltm_end >= fiscal_year_end:
                print("\n🔧 Tax Adjustment Skipped (LTM fully includes fiscal year)")
                print(f"  ➤ Fiscal year end: {fiscal_year_end.date()}, LTM end: {ltm_end.date()}")
                return taxes_end

            # Else: proceed with adjustment
            overlap_mask = (
                (self.df["top_level_grouping"] == "Income taxes") &
                (self.df["ltm"] == end_period) &
                (self.df["date"] <= fiscal_year_end)
            )
            overlap_amount = self.df.loc[overlap_mask, "ending_balance"].sum()
            adjusted = taxes_end - overlap_amount

            print("\n🔧 Tax Adjustment Debug")
            print(f"  ➤ Fiscal year end: {fiscal_year_end.date()}")
            print(f"  ➤ LTM end: {ltm_end.date()}")
            print(f"  ➤ Overlap to subtract: {overlap_amount}")
            print(f"  ➤ Adjusted taxes: {adjusted}")
            return adjusted

        # No adjustment case
        print("\n🔧 Tax Adjustment Skipped (non-LTM or no FY end)")
        return taxes_end



    def get_chart_data(self) -> dict:
        df = self.df.copy()
        df = self.apply_filters(df)
        print("\n🔍 Available period labels in filtered df:")
        print(df["period_label"].value_counts())


        if "period_label" not in df.columns:
            df["period_label"] = df.apply(
                lambda row: row["ytd"] or row["ltm"] or row["fiscal_year"],
                axis=1
            )

        waterfall_map = memory_store[self.dataset_id].get("waterfall_periods", {})
        if self.selected_period not in waterfall_map:
            raise ValueError(f"Invalid waterfall period: '{self.selected_period}'")
        
        start_label, end_label = waterfall_map[self.selected_period]

        def get_group_total(group_name, period_value, use_fs_grouping=False):
            col = "fs_grouping" if use_fs_grouping else "top_level_grouping"
            period_col = resolve_period_column(period_value)
            mask = (df[period_col] == period_value) & (df[col] == group_name)
            return df.loc[mask, "ending_balance"].sum()

        def resolve_period_column(period: str) -> str:
            if period.startswith("LTM"):
                return "ltm"
            if period.startswith("F"):
                return "fiscal_year"
            raise ValueError(f"Unsupported period format: {period}")

        def compute_metrics(period):
            sales = get_group_total("Sales", period)
            cogs = get_group_total("Cost of sales", period)
            opex = get_group_total("Operating expenses", period)
            other_income = get_group_total("Other income/expenses", period)
            taxes = get_group_total("Income taxes", period)
            interest = get_group_total("Interest expense", period, use_fs_grouping=True)
            depreciation = get_group_total("Depreciation", period, use_fs_grouping=True)
            amortization = get_group_total("Amortization", period, use_fs_grouping=True)

            gross_margin = sales - cogs
            net_income = sales - cogs - opex - other_income - taxes
            ebit = net_income + interest + taxes
            ebitda = ebit + depreciation + amortization

            gm_pct = gross_margin / sales if sales and pd.notna(sales) else 0
            print(f"\n🧾 Gross Margin Debug ({period})")
            print(f"  ➤ Sales: {sales}")
            print(f"  ➤ COGS: {cogs}")
            print(f"  ➤ Gross Margin: {gross_margin}")
            print(f"  ➤ Gross Margin %: {gm_pct:.4f}")


            return {
                "sales": sales,
                "gross_margin": gross_margin,
                "gross_margin_pct": gm_pct,
                "opex": opex,
                "other_income": other_income,
                "taxes": taxes,
                "net_income": net_income
            }

        print(f"▶ Using start period: {start_label}, end period: {end_label}")
        print("▶ Available periods in df:", df["period_label"].unique())

        start = compute_metrics(start_label)
        end = compute_metrics(end_label)

        end["taxes"] = self._adjust_taxes_for_overlap(end["taxes"], end_label, start_label)

        change_sales = (end["sales"] - start["sales"]) * start["gross_margin_pct"]
        print("\n📊 Change in Sales Debug:")
        print(f"  ➤ Start sales: {start['sales']}")
        print(f"  ➤ End sales: {end['sales']}")
        print(f"  ➤ Start gross margin %: {start['gross_margin_pct']:.4f}")
        print(f"  ➤ Change in sales: {end['sales'] - start['sales']}")
        print(f"  ➤ Contribution to net income: {(end['sales'] - start['sales']) * start['gross_margin_pct']:.2f}")

        change_gm_pct = (end["gross_margin_pct"] - start["gross_margin_pct"]) * end["sales"]

        print("\n📊 Change in Gross Margin % Debug:")
        print(f"  ➤ Start GM %: {start['gross_margin_pct']:.4f}")
        print(f"  ➤ End GM %: {end['gross_margin_pct']:.4f}")
        print(f"  ➤ End sales: {end['sales']}")
        print(f"  ➤ Change in GM %: {end['gross_margin_pct'] - start['gross_margin_pct']:.4f}")
        print(f"  ➤ Contribution to net income: {change_gm_pct:.2f}")

        change_opex = -(end["opex"] - start["opex"])
        change_other = -(end["other_income"] - start["other_income"])
        print("\n📊 Tax Change Debug:")
        print(f"  ➤ Start taxes: {start['taxes']}")
        print(f"  ➤ End taxes (after adjustment): {end['taxes']}")
        print(f"  ➤ Change in taxes: {end['taxes'] - start['taxes']}")
        print(f"  ➤ Waterfall value: {- (end['taxes'] - start['taxes'])}")

        change_tax = -(end["taxes"] - start["taxes"])

        labels = [
            f"Net income, {start_label}",
            "Change in sales",
            "Change in gross profit %",
            "Change in operating expenses",
            "Change in other income/expenses",
            "Change in income taxes",
            f"Net income, {end_label}"
        ]

        values = [
            round(start["net_income"], 2),
            round(change_sales, 2),
            round(change_gm_pct, 2),
            round(change_opex, 2),
            round(change_other, 2),
            round(change_tax, 2),
            round(end["net_income"], 2)
        ]

        floating_pairs = []
        running_total = 0

        for i, v in enumerate(values):
            if i == 0:                        # opening absolute bar
                floating_pairs.append([0, v])
                running_total = v
            elif i == len(values) - 1:        # closing absolute bar
                floating_pairs.append([0, v])
            else:                             # delta bars
                start = running_total
                end   = running_total + v
                floating_pairs.append([start, end])
                running_total = end
        base   = []
        change = []

        for i, (lo, hi) in enumerate(floating_pairs):
            if i == 0 or i == len(floating_pairs) - 1: 
                base.append(0)
                change.append(hi)                        
            else:                               
                base.append(lo)                         
                change.append(hi - lo)                  


        # Determine color for each bar
        waterfall_colors = []
        for i, delta in enumerate(change):
            if i == 0 or i == len(change) - 1:
                waterfall_colors.append("#888")  # Neutral color for Start and End bars
            else:
                waterfall_colors.append("green" if delta >= 0 else "red")

        datasets = [
            {
                "label": "",
                "data": base,
                "backgroundColor": "rgba(0,0,0,0)", 
                "stack": "stack1"
            },
            {
                "label": "Net Income Waterfall",
                "data": change,
                "backgroundColor": waterfall_colors,
                "stack": "stack1"
            }
        ]

        return self.build_response(labels, datasets)
