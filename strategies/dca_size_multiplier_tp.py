"""
DCA Script

- Pirce drop percentage level based on the last purchased price
- Initial trade size percentage based on total amount available 
- Trade size multiplier for every additional purchase increase  based on last trade value in quote
- Takeprofit based on percentage of average entry price

"""
import backtrader as bt


class DCAStrategyCompound2(bt.Strategy):
    params = (
        ('price_drop_percentage', 1),
        ('initial_trade_size_percentage', 7),  # Initial trade size as a percentage of cash
        ('trade_size_multiplier', 3),  # Multiplier for subsequent trades
        ('take_profit_percentage', 8),
        ('log', False),
    )

    def __init__(self):
        self.total_invested = 0
        self.total_units_purchased = 0
        self.average_entry_price = 0
        self.last_purchase_price = float('inf')
        self.last_trade_value = 0  # Store the value of the last trade

    def next(self):
        current_high = self.data.high[0]
        current_low = self.data.low[0]

        # price drop check
        target_price_drop = self.last_purchase_price * (1 - (self.params.price_drop_percentage / 100))
        if current_low <= target_price_drop:
            self.execute_buy(current_low)

        # Check take profit line
        target_take_profit_price = self.average_entry_price * (1 + (self.params.take_profit_percentage / 100))

        if current_high >= target_take_profit_price and self.total_units_purchased > 0:
            self.execute_sell(current_high)

    def execute_buy(self, current_price):
        if self.last_trade_value == 0:  # If it's the first trade or after a reset
            current_cash = self.broker.get_cash()
            amount_to_invest = current_cash * (self.params.initial_trade_size_percentage / 100)
        else:
            amount_to_invest = self.last_trade_value * self.params.trade_size_multiplier

        units_to_buy = amount_to_invest / current_price

        if units_to_buy > 0:
            self.buy(size=units_to_buy)

            self.total_invested += amount_to_invest
            self.total_units_purchased += units_to_buy
            self.average_entry_price = self.total_invested / self.total_units_purchased
            self.last_trade_value = amount_to_invest  # Update the last trade value for the next buy calculation

            self.last_purchase_price = current_price
            self.log(f'BUY EXECUTED, Price: {current_price}, Cost: {amount_to_invest}, Units: {units_to_buy}, Total Invested: {self.total_invested}, Avg Price: {self.average_entry_price}')

    def execute_sell(self, current_price):
        if self.total_units_purchased > 0:
            self.sell(size=self.total_units_purchased)

            profit = (current_price * self.total_units_purchased) - self.total_invested

            self.log(f'SELL EXECUTED, Price: {current_price}, Profit: {profit}')

            # Reset tracking variables post-sale
            self.total_units_purchased = 0
            self.total_invested = 0
            self.average_entry_price = 0
            self.last_purchase_price = float('inf')
            self.last_trade_value = 0  # Reset for the next cycle

    def log(self, txt, dt=None):
        ''' Logging function for this strategy '''
        if self.params.log:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()}, {txt}')
