import backtrader as bt
from dateutil.relativedelta import relativedelta

class TotalTestLengthStats(bt.Analyzer):
    def __init__(self):
        self.first_next = True

    def next(self):
        if self.first_next:
            self.start_date = self.strategy.datetime.datetime(0)
            self.first_next = False

    def stop(self):
        self.end_date = self.strategy.datetime.datetime(0)
        self.calculate_duration()

    def calculate_duration(self):
        duration = relativedelta(self.end_date, self.start_date)

        self.total_days = (self.end_date - self.start_date).days
        self.total_weeks = self.total_days / 7
        self.total_months = duration.months + (duration.years * 12)
        self.total_quarters = self.total_months / 3
        self.total_years = duration.years

    def get_analysis(self):
        return {
            'total_days': self.total_days,
            'total_weeks': round(self.total_weeks, 2),
            'total_months': self.total_months,
            'total_quarters': round(self.total_quarters, 2),
            'total_years': self.total_years,
        }