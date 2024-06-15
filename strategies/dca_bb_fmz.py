import backtrader as bt
from datetime import datetime

# https://medium.com/@FMZQuant/high-frequency-trading-strategy-combining-bollinger-bands-and-dca-83bbc6d94a39
class DCABbFMZ(bt.Strategy):
    params = (
        ("period", 20),
        ("devfactor", 2),
        ("size", 100),
        ("num_positions", 5),
        ("consec_candles", 2),
        ("log", True),
    )

    def __init__(self):
        self.boll = bt.indicators.BollingerBands(
            period=self.params.period, devfactor=self.params.devfactor
        )
        self.order = None  # To keep track of pending orders
        self.counter = 0

    def next(self):
        if self.order:
            return  # Waiting for an order to complete

        # Current market conditions
        current_price = self.data.close[0]
        lower_band = self.boll.lines.bot[0]
        upper_band = self.boll.lines.top[0]
        position_size = self.getposition()
        print(f'Position size: {position_size}')
        cash = self.broker.get_cash()

        # Check for consecutive closes below the lower band
        if current_price < lower_band:
            self.counter += 1
            self.log(f'Price {current_price} below lower band {lower_band}. Consecutive lower band undercuts: {self.counter}')
        else:
            if self.counter > 0:
                self.log(f'Reset consecutive count from {self.counter} to 0. Price {current_price} is now {current_price-lower_band:.2f} above lower band.')
            self.counter = 0
        
        # Buy conditions based on consecutive candles parameter
        if self.counter >= self.params.consec_candles:
            if position_size < self.params.size * self.params.num_positions:
                if cash > current_price * self.params.size:
                    self.log('Buying...')
                    self.order = self.buy(size=self.params.size)
                else:
                    self.log(f'Insufficient cash to buy: Available ${cash}, Required ${current_price * self.params.size}')
        
        # Check for price above the upper band to exit all positions
        if current_price > upper_band:
            if position_size > 0:
                self.log(f'Selling... Current price {current_price} is above upper band {upper_band}')
                self.order = self.close()

    def log(self, txt, dt=None):
        """ Logging function for this strategy """
        dt = dt or self.datas[0].datetime.date(0)
        print(f"{dt.isoformat()}, {txt}")