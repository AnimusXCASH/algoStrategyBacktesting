"""
Market cypher B:
- Wave trend 
- Moneyflow RSI

"""

from customIndicators.waveTrendMC import WaveTrendMc
from customIndicators.moneyFlowRSIMC import MoneyFlowRSI

import backtrader as bt





# Strategy class with parameters
class MarketCypherB(bt.Strategy):
    params = (
        ("ema_period_short", 50),
        ("ema_period_long", 200),
        ("wt_n1", 9),
        ("wt_n2", 12),
        ("mfrsi_period", 60),
        ("mfrsi_multi", 150),
        ("mfrsi_posy", 2.5),
    )


    def __init__(self):
        self.wave_trend = WaveTrendMc(
            self.data, n1=self.p.wt_n1, n2=self.p.wt_n2
        )
        self.money_flow_rsi = MoneyFlowRSI(
            self.data,
            period=self.p.mfrsi_period,
            multi=self.p.mfrsi_multi,
            posy=self.p.mfrsi_posy,
        )

        
        self.ma50 = bt.indicators.EMA(self.data.close, period=self.p.ema_period_short)
        self.ma200 = bt.indicators.EMA(self.data.close, period=self.p.ema_period_long)


    def notify_order(self, order):
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
        # If no datetime provided, use the current datetime from the data
        if dt is None:
            dt = self.datas[0].datetime.date(0)

        # Convert the float timestamp to a datetime object if necessary
        if isinstance(dt, float):
            dt = bt.num2date(dt)

        print(f'{dt.isoformat()}, {txt}')

    def next(self):
        current_wt1 = self.wave_trend.wt1[0]
        previous_wt1 = self.wave_trend.wt1[-1]
        second_previous_wt1 = self.wave_trend.wt1[-2]  # Added for additional confirmation
        current_wt2 = self.wave_trend.wt2[0]
        previous_wt2 = self.wave_trend.wt2[-1]

        current_mfi = self.money_flow_rsi.mfrsi[0]

        # Conditions for the oscillator turning up or down
        oscillator_turning_up = previous_wt1 > second_previous_wt1 and current_wt1 > previous_wt1
        oscillator_turning_down = previous_wt1 < second_previous_wt1 and current_wt1 < previous_wt1

        # Oversold condition for buy signal
        is_oversold = current_wt1 < self.wave_trend.lines.oversold[0] and current_wt2 < self.wave_trend.lines.oversold[0]
        
        # Overbought condition for sell signal
        is_overbought = current_wt1 > self.wave_trend.lines.overbought[0] and current_wt2 > self.wave_trend.lines.overbought[0]

        # Enhanced condition checks for better confirmation of turns
        # Buy signal: Ensure wt1 and wt2 are in oversold and wt1 starts turning up with confirmation
        if is_oversold and oscillator_turning_up and (current_mfi < 0):
            if not self.position:  # If not already in the market
                self.buy()

        # Sell signal or exit: Ensure wt1 and wt2 are in overbought and wt1 starts turning down with confirmation
        elif is_overbought and oscillator_turning_down:
            if self.position:  # If currently in the market
                self.close()  # Close the position


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
