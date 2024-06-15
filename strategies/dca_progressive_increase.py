import backtrader as bt

'''
DCA Script

('price_drop_percentage', 1),  DCA Level to drop for last entry
('initial_trade_size_percentage', 7),  # Initial trade size as a percentage of cash
('trade_size_multiplier_increment', 1.5),  # Increment for each subsequent order
('take_profit_percentage', 8),
('log', False),

Basaed on 100$ example:

Settings:
- Pirce drop percentage level based on the last purchased price
- Initial trade size percentage based on total amount available at the start of the round:
    - 7% from 100 => 7$ initial trade 

- Trade size multiplier increment for every additional purchase increase  based on last QUOTE value:
    - Increment is done with adding 1.5 % to current multiplier with the start of 1.0 (hardcoded)
    - Example of increment levels:
        1st: 1.0 (No Increment)
        2nd: 1.0 -> 1.015  (Increment of 1.5%)
        3rd: 1.015 -> 1.03 (Increment of 1.5% from previous 1.5%)
        4th: 1.03 -> 1.05 (Increment of 1.5% from previous 3%)

- Takeprofit based on percentage of average entry price

'''
class DCAStrategyProgressive(bt.Strategy):
    params = (
        ('price_drop_percentage', 1),
        ('initial_trade_size_percentage', 7),  # Initial trade size as a percentage of cash
        ('trade_size_multiplier_increment', 1.5),  # Increment for each subsequent order
        ('take_profit_percentage', 8),
        ('log', False),
    )

    def __init__(self):
        self.total_invested = 0
        self.total_units_purchased = 0
        self.average_entry_price = 0
        self.last_purchase_price = float('inf')
        self.last_trade_value = 0
        self.order_count = 0  # Track the number of orders
        self.current_multiplier = 1.0  # Initialize multiplier

    def next(self):
        current_high = self.data.high[0]
        current_low = self.data.low[0]

        target_price_drop = self.last_purchase_price * (1 - (self.params.price_drop_percentage / 100))
        if current_low <= target_price_drop:
            self.execute_buy(current_low)

        target_take_profit_price = self.average_entry_price * (1 + (self.params.take_profit_percentage / 100))
        if current_high >= target_take_profit_price and self.total_units_purchased > 0:
            self.execute_sell(current_high)

    def execute_buy(self, current_price):
        current_cash = self.broker.get_cash()
        if self.order_count == 0:
            amount_to_invest = current_cash * (self.params.initial_trade_size_percentage / 100)
        else:
            self.current_multiplier += (round(self.params.trade_size_multiplier_increment / 100,3))
            amount_to_invest = self.last_trade_value * self.current_multiplier


        units_to_buy = amount_to_invest / current_price
        if units_to_buy > 0 and amount_to_invest <= current_cash:
            self.buy(size=units_to_buy)
            self.total_invested += amount_to_invest
            self.total_units_purchased += units_to_buy
            self.average_entry_price = self.total_invested / self.total_units_purchased
            self.last_trade_value = amount_to_invest  # Update for the next buy calculation USDT
            self.last_purchase_price = current_price
            self.order_count += 1  # Increment order count for multiplier calculation
            self.log(f'BUY EXECUTED, Price: {current_price}, Cost: {amount_to_invest}, Units: {units_to_buy}, Total Invested: {self.total_invested}, Avg Price: {self.average_entry_price}')

    def execute_sell(self, current_price):
        self.sell(size=self.total_units_purchased)
        profit = (current_price * self.total_units_purchased) - self.total_invested
        self.log(f'SELL EXECUTED, Price: {current_price}, Profit: {profit}')
        # Reset variables post-sale
        self.total_units_purchased = 0
        self.total_invested = 0
        self.average_entry_price = 0
        self.last_purchase_price = float('inf')
        self.last_trade_value = 0
        self.order_count = 0  # Reset order count
        self.current_multiplier = 1.0  # Reset multiplier

    def log(self, txt, dt=None):
        if self.params.log:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()}, {txt}')

    def stop(self):
        # This method is called once at the end of the strategy's lifecycle
        print('Test has been finished')
