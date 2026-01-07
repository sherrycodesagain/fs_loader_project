import pandas as pd

class PeriodResolver:
    def __init__(
        self,
        df: pd.DataFrame,
        period_type: str,
        selected_period: str,
        selected_months=None,
        selected_quarters=None,
        selected_years=None,
        memory_store=None
    ):
        self.df = df
        self.period_type = period_type
        self.selected_period = selected_period
        self.selected_months = selected_months or []
        self.selected_quarters = selected_quarters or []
        self.selected_years = selected_years or []
        self.memory_store = memory_store or {}

        # ✅ Check if no time filters were sent
        has_months = bool(self.selected_months)
        has_quarters = bool(self.selected_quarters)
        has_years = bool(self.selected_years)

        no_time_filters_sent = not (has_months or has_quarters or has_years)

        if no_time_filters_sent:
            print("🛡️ No time filters provided — defaulting to all periods for type:", self.period_type)

            if self.period_type == "Monthly":
                self.selected_months = sorted(self.df["month"].dropna().unique().tolist())

            elif self.period_type == "Quarterly":
                self.selected_quarters = sorted(self.df["fiscal_quarter"].dropna().unique().tolist())

            elif self.period_type == "Yearly":
                self.selected_years = sorted(self.df["fiscal_year"].dropna().unique().tolist())


    def resolve_label_periods(self, available_periods: list[str]) -> list[str]:
        """
        Filters the available_periods list down to those that match the months_to_keep.
        This is what determines which x-axis labels are shown.
        """
        months_to_keep = self.resolve_months()

        if self.period_type == "Monthly":
            return sorted(
                [m for m in available_periods if m in months_to_keep],
                key=lambda x: pd.to_datetime(x)
            )

        elif self.period_type == "Quarterly":
            visible_quarters = self.resolve_quarters_from_months(months_to_keep)
            return sorted(
                [q for q in available_periods if q in visible_quarters],
                key=self.quarter_sort_key
            )

        elif self.period_type == "Yearly":
            # Filter df based on visible months
            filtered_df = self.df[self.df["month"].isin(months_to_keep)]

            # Collect valid fiscal years, YTDs, and LTMs from that filtered set
            visible_years = set(filtered_df["fiscal_year"].unique())
            visible_ytd = set(filtered_df["ytd"].unique()) - {""}
            visible_ltm = set(filtered_df["ltm"].unique()) - {""}

            # Only include those labels that are still valid
            return sorted([
                p for p in available_periods if p in visible_years or p in visible_ytd or p in visible_ltm
            ])


        return []

    def resolve_months(self):

        all_months = set(self.df["month"].unique())
        month_sets = []

        active_type = self.memory_store.get("active_time_filter_type", "dates") 

        if active_type == "dates" and self.selected_months:
            month_sets.append(set(self.selected_months))

        if active_type == "quarters" and self.selected_quarters:
            quarter_months = self.df[self.df["fiscal_quarter"].isin(self.selected_quarters)]["month"].unique()
            month_sets.append(set(quarter_months))

        if active_type == "years" and self.selected_years:
            year_months = self.df[self.df["fiscal_year"].isin(self.selected_years)]["month"].unique()
            month_sets.append(set(year_months))

        if not month_sets:
            return all_months

        months_to_keep = set.union(*month_sets)
        # 👇 Only infer if using months directly
        if active_type == "dates" and not self.selected_years:
            inferred_years = self.df[self.df["month"].isin(self.selected_months)]["fiscal_year"].unique()
            print(f"🧠 Inferred fiscal years from months: {inferred_years}")
            self.selected_years = list(inferred_years)

        return months_to_keep

    def resolve_quarters_from_months(self, months: set):
        """
        Given a set of months, return quarters they belong to.
        """
        return set(
            self.df[self.df["month"].isin(months)]["fiscal_quarter"].unique()
        )

    def resolve_years_from_months(self, months: set):
        """
        Given a set of months, return years they belong to.
        """
        return set(
            self.df[self.df["month"].isin(months)]["fiscal_year"].unique()
        )

    def get_labels(self, period_type: str, months_to_keep: set):
        """
        Based on period type, return labels to be shown on the x-axis
        """
        if period_type == "Monthly":
            return sorted(months_to_keep, key=lambda x: pd.to_datetime(x))

        elif period_type == "Quarterly":
            quarters = self.resolve_quarters_from_months(months_to_keep)
            return sorted(quarters, key=lambda x: self.quarter_sort_key(x))

        elif period_type == "Yearly":
            years = self.resolve_years_from_months(months_to_keep)
            return sorted(years)

        return []

    @staticmethod
    def quarter_sort_key(q):
        """
        Sort key for fiscal quarters like 'Q2 F2022'
        """
        parts = q.split()
        qnum = int(parts[0][1])  # Q2 -> 2
        year = int(parts[1][1:])  # F2022 -> 2022
        return (year, qnum)
