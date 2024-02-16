import backtrader as bt

class PNLPercentage(bt.Analyzer):
    
    def start(self):
        self.initial_value = self.strategy.broker.getvalue()  
        self.final_value = None  # Final portfolio value will be set at the end of the strategy

    def stop(self):
        self.final_value = self.strategy.broker.getvalue()  # Final portfolio value
        self.pnl_percentage = ((self.final_value - self.initial_value) / self.initial_value) * 100

    def get_analysis(self):
        return {'pnl_percentage': self.pnl_percentage}
