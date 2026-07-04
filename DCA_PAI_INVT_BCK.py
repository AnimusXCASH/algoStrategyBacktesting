import backtrader as bt
import pandas as pd
import ccxt
import datetime
import numpy as np

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pandas as pd

from strategies.dca_size_multiplier_tp import DCAStrategyCompound2
from strategies.dca_macd import DCAMacd
from prettytable import PrettyTable
from customStats.profitAndLoss import PNLPercentage
from customStats.totalTestLengthStats import TotalTestLengthStats
from utils.other import CCXTData
from utils.dataManipulation import fetch_and_prepare_data


exchange = ccxt.binance({
    'options': {'defaultType': 'swap',
                'defaultContractType': 'perpetual'},
    'rateLimit': 1200,
    'enableRateLimit': True,
})


class RSI_EMA(bt.Indicator):
    lines = ('rsi', 'rsi_ema')
    params = (('length', 14),)

    def __init__(self):
        self.addminperiod(self.params.length + 1)
        
        delta = self.data.close - self.data.close(-1)
        gain = bt.If(delta > 0, delta, 0.0)
        loss = bt.If(delta < 0, -delta, 0.0)
        avg_gain = bt.indicators.EMA(gain, period=self.params.length)
        avg_loss = bt.indicators.EMA(loss, period=self.params.length)
        rs = avg_gain / avg_loss
        self.lines.rsi = 100 - (100 / (1 + rs))
        self.lines.rsi_ema = bt.indicators.EMA(self.lines.rsi, period=self.params.length)

class InevitradeProStrategy(bt.Strategy):
    params = (('rsi_length', 14),)

    def __init__(self):
        self.rsi_ema = RSI_EMA(self.data, length=self.params.rsi_length)
        self.previous_rsi = self.rsi_ema.rsi(-1)
        self.previous_rsi_ema = self.rsi_ema.rsi_ema(-1)

    def next(self):
        if self.rsi_ema.rsi[0] > self.rsi_ema.rsi_ema[0] and self.previous_rsi <= self.previous_rsi_ema:
            self.buy()
        elif self.rsi_ema.rsi[0] < self.rsi_ema.rsi_ema[0] and self.previous_rsi >= self.previous_rsi_ema:
            self.sell()



if __name__ == "__main__":

    '''
    Symbol settings 
    start_date = None Or  '2024-06-14T00:00:00Z'  for start
    end_date = None Or  '2024-02-024T00:00:00Z'  for start

    - if start adn end None it will take latest N candles returned fom exchange max in single api call 

    '''
    symbol = "BTC/USDT"
    timeframe = '4h'
    start_date = '2024-01-01T00:00:00Z'  # None Or  '2023-01-01T00:00:00Z'  for start
    end_date = None     # None Or  '2023-01-01T00:00:00Z'  for end

                                                   
    df = fetch_and_prepare_data(exchange, symbol, timeframe, start_date=start_date, end_date=end_date)


    data = CCXTData(dataname=df)
    

    # Initiate framework 
    cerebro = bt.Cerebro()
    cerebro.adddata(data)
    


    cerebro.broker.set_cash(1000)
    cerebro.broker.setcommission(commission=.002)


    # STRATEGIES
    cerebro.addstrategy(InevitradeProStrategy)

    cerebro.run()
    cerebro.plot(style='candlestick')

