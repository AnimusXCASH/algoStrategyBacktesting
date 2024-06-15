"""
Market cypher B:
- Wave trend 
- Moneyflow RSI

"""

from customIndicators.waveTrendMC import WaveTrendMc
from customIndicators.moneyFlowRSIMC import MoneyFlowRSI

import backtrader as bt


# Strategy class with parameters
class DCAMarketCypherB(bt.Strategy):
    params = (
        ('initial_trade_size_percentage', 7),
        ('trade_size_multiplier', 3),
        ("wt_n1", 9),
        ("wt_n2", 12),
        ("mfrsi_period", 60),
        ("mfrsi_multi", 150),
        ("mfrsi_posy", 2.5),
        ("take_profit_percentage", 2),
        ("log",False)
    )


    def __init__(self):
        
        # Custom indicators
        self.wave_trend = WaveTrendMc(self.data, n1=self.p.wt_n1, n2=self.p.wt_n2)
        self.money_flow_rsi = MoneyFlowRSI(self.data, period=self.p.mfrsi_period, multi=self.p.mfrsi_multi, posy=self.p.mfrsi_posy)
        self.total_invested = 0
        self.total_units_purchased = 0
        self.average_entry_price = 0
        self.last_purchase_price = float('inf')
        self.last_trade_value = 0  # Store the value of the last trade
        self.order_count = 0  # Track the number of orders
        self.current_multiplier = 1.0  # Initialize multiplier
        self.log = self.p.log

    def notify_order(self, order):
        if self.log:
          if order.status in [order.Submitted, order.Accepted]:
              self.log('ORDER SUBMITTED/ACCEPTED', dt=order.created.dt)
          elif order.status in [order.Completed]:
              if order.isbuy():
                  self.log(f'BUY EXECUTED, Price: {order.executed.price}, Cost: {order.executed.value}, Comm: {order.executed.comm}', dt=order.created.dt)
              elif order.issell():
                  self.log(f'SELL EXECUTED, Price: {order.executed.price}, Cost: {order.executed.value}, Comm: {order.executed.comm}', dt=order.created.dt)
          elif order.status in [order.Canceled, order.Margin, order.Rejected]:
              self.log('Order Canceled/Margin/Rejected', dt=order.created.dt)


    def log(self, txt, dt=None):
        ''' Logging function for this strategy '''

        if dt is None:
            dt = self.datas[0].datetime.date(0)
        if isinstance(dt, float):
            dt = bt.num2date(dt)

        print(f'{dt.isoformat()}, {txt}')

    def next(self):
        current_high = self.data.high[0]
        current_low = self.data.low[0]


        current_wt1 = self.wave_trend.wt1[0]
        previous_wt1 = self.wave_trend.wt1[-1]
        second_previous_wt1 = self.wave_trend.wt1[-2]  # Added for additional confirmation
        current_wt2 = self.wave_trend.wt2[0]
        previous_wt2 = self.wave_trend.wt2[-1]

        current_mfi = self.money_flow_rsi.mfrsi[0]

        # Conditions for the oscillator turning up or down
        oscillator_turning_up = previous_wt1 > second_previous_wt1 and current_wt1 > previous_wt1
        # oscillator_turning_down = previous_wt1 < second_previous_wt1 and current_wt1 < previous_wt1

        # Oversold condition for buy signal
        is_oversold = current_wt1 < self.wave_trend.lines.oversold[0] and current_wt2 < self.wave_trend.lines.oversold[0]
        
        # Overbought condition for sell signal
        # is_overbought = current_wt1 > self.wave_trend.lines.overbought[0] and current_wt2 > self.wave_trend.lines.overbought[0]

        # Enhanced condition checks for better confirmation of turns
        # Buy signal: Ensure wt1 and wt2 are in oversold and wt1 starts turning up with confirmation
        if is_oversold and oscillator_turning_up:
            self.execute_buy()

        # # Sell signal or exit: Ensure wt1 and wt2 are in overbought and wt1 starts turning down with confirmation
        # elif is_overbought and oscillator_turning_down:
        #     self.execute_sell()


        # Average anetry based on TP % from average entry price
        target_take_profit_price = self.average_entry_price * (1 + (self.params.take_profit_percentage / 100))
        if current_high >= target_take_profit_price and self.total_units_purchased > 0:
            self.execute_sell()



    def execute_buy(self):
        current_price = self.data.close[0]
        current_cash = self.broker.get_cash()

        if self.order_count == 0:
            amount_to_invest = current_cash * (self.params.initial_trade_size_percentage / 100)
        else:
            amount_to_invest = self.last_trade_value * (self.params.trade_size_multiplier/100)

        units_to_buy = amount_to_invest / current_price


        if units_to_buy > 0 and amount_to_invest <= current_cash:
            self.buy(size=units_to_buy)
            self.total_invested += amount_to_invest
            self.total_units_purchased += units_to_buy
            self.average_entry_price = self.total_invested / self.total_units_purchased
            self.last_trade_value = amount_to_invest  
            self.last_purchase_price = current_price
            # self.log(f'BUY EXECUTED, Price: {current_price}, Cost: {amount_to_invest}, Units: {units_to_buy}, Total Invested: {self.total_invested}, Avg Price: {self.average_entry_price}')

    
    def execute_sell(self):
        current_price = self.data.close[0]
        if self.total_units_purchased > 0:
            self.sell(size=self.total_units_purchased)
            profit = (current_price * self.total_units_purchased) - self.total_invested

            # self.log(f'SELL EXECUTED, Price: {current_price}, Profit: {profit}')

            # Reset tracking variables post-sale
            self.total_units_purchased = 0
            self.total_invested = 0
            self.average_entry_price = 0
            self.last_purchase_price = float('inf')
            self.last_trade_value = 0
            self.order_count = 0  # Reset order count
            self.current_multiplier = 1.0  # Reset multiplier


    # def next(self):
    #     current_wt1 = self.wave_trend.wt1[0]
    #     previous_wt1 = self.wave_trend.wt1[-1]
    #     current_wt2 = self.wave_trend.wt2[0]
    #     previous_wt2 = self.wave_trend.wt2[-1]

    #     # Conditions for the oscillator turning up or down
    #     oscillator_turning_up = current_wt1 > previous_wt1
    #     oscillator_turning_down = current_wt1 < previous_wt1

    #     # Oversold condition for buy signal
    #     is_oversold = current_wt1 < self.wave_trend.lines.oversold[0] and current_wt2 < self.wave_trend.lines.oversold[0]

    #     # Overbought condition for sell signal
    #     is_overbought = current_wt1 > self.wave_trend.lines.overbought[0] and current_wt2 > self.wave_trend.lines.overbought[0]

    #     # Buy signal: wt1 and wt2 in oversold and wt1 starts turning up
    #     if is_oversold and oscillator_turning_up:
    #         if not self.position:  # If not already in the market
    #             self.buy()

    #     # Sell signal or exit: wt1 and wt2 in overbought and wt1 starts turning down
    #     elif is_overbought and oscillator_turning_down:
    #         if self.position:  # If currently in the market
    #             self.close()  # Close the position

                

    ###########BASIC WITH WAVE TREND CROSS ONLY 
    # def next(self):
    #     current_wt1 = self.wave_trend.wt1[0]
    #     previous_wt1 = self.wave_trend.wt1[-1]
    #     current_wt2 = self.wave_trend.wt2[0]
    #     previous_wt2 = self.wave_trend.wt2[-1]


    #     print(f'Current wt1: {current_wt1}, Current wt2: {current_wt2}')

    #     # Detect crossover: wt1 crosses above wt2 for a buy signal
    #     if previous_wt1 <= previous_wt2 and current_wt1 > current_wt2:
    #         if not self.position:  # If not already in the market
    #             self.buy()

    #     # Detect crossunder: wt1 crosses below wt2 for a sell signal
    #     elif previous_wt1 >= previous_wt2 and current_wt1 < current_wt2:
    #         if self.position:  # If currently in the market
    #             self.close()  # Close the position
