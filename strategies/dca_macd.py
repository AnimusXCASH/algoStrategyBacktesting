import backtrader as bt

class DCAMacd(bt.Strategy):
    params = (
        ('initial_trade_size_percentage', 3),  # Percentage of total cash to use for each trade
        ('trade_size_multiplier', 3),
        ('take_profit_percentage', 2),
        ('macd_fast_period', 12),
        ('macd_slow_period', 20),  # Adjusted as per the new strategy setup
        ('macd_signal_period', 9),
        ('level', 0),
        ('log', True),
    )

    def __init__(self):

        self.macd = bt.indicators.MACD(self.data.close,
                                       period_me1=self.params.macd_fast_period,
                                       period_me2=self.params.macd_slow_period,
                                       period_signal=self.params.macd_signal_period)

        self.total_invested = 0
        self.total_units_purchased = 0
        self.average_entry_price = 0
        self.last_trade_value = 0
        
        # To keep track of whether we are in the market
        self.in_market = False

    def next(self):

        current_price = self.data.close[0]  # Get current price
        current_high = self.data.high[0]

        if self.macd.macd[0] > self.macd.signal[0] and self.macd.macd[-1] <= self.macd.signal[-1] and self.macd.macd[0] < self.params.level:
            self.execute_buy(current_price)


        # Check the take profit line
        target_take_profit_price = self.average_entry_price * (1 + (self.params.take_profit_percentage / 100))

        if current_high >= target_take_profit_price and self.total_units_purchased > 0:
            self.execute_sell(current_high)


            # positions = self.getposition(self.data).size
            # if positions > 0:
            #     self.sell(size=positions)
            #     self.in_market = False
            #     self.log('SELL EXECUTED, Price: {}'.format(current_price))

    def execute_buy(self, current_price):
        # Check if we start from scratch
        if self.last_trade_value == 0:
            current_cash = self.broker.get_cash() # get available cash from broker
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
        else:
            self.log('BUY SKIPPED, INSUFFICIENT CASH, Price: {}, Cash: {}'.format(current_price, current_cash))

    def execute_sell(self, current_price):
        positions = self.getposition(self.data).size
        if self.total_units_purchased > 0:
            self.sell(size=positions)
            profit = (current_price * positions) - self.total_invested

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