"""
**Rules**

1) can only go long when price is above the 200 EMA and can only take shorts when price is below the 200 EMA

2) Can only take a position when price has pulled back into the 50 EMA

3) Can only go long if mf is positive and short only when mf is negative

4) Can only go long when wave trend is negative and only go short when wave trend is positive

entry on close via a wave trend cross stop below the swing low/ above the swing high, profit at 2x the stop
"""

import backtrader as bt
import pandas as pd
import ccxt
import datetime
import numpy as np
from strategies.dca_size_multiplier_tp import DCAStrategyCompound2
from strategies.dca_macd import DCAMacd
from prettytable import PrettyTable
from customStats.profitAndLoss import PNLPercentage
from customStats.totalTestLengthStats import TotalTestLengthStats
from utils.other import CCXTData
from utils.dataManipulation import fetch_and_prepare_data
import pandas_ta as ta
import plotly.graph_objects as go
import numpy as np
import matplotlib.pyplot as plt
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))



exchange = ccxt.binance(
    {
        "options": {"defaultType": "swap", "defaultContractType": "perpetual"},
        "rateLimit": 1200,
        "enableRateLimit": True,
    }
)


# Create the table with these keys as column headers
table = PrettyTable()


if __name__ == "__main__":

    symbol = "BTC/USDT"
    timeframe = "4h"
    start_date = "2024-03-01T00:00:00Z"  # None Or  '2023-01-01T00:00:00Z'  for start
    end_date = None  # None Or  '2023-01-01T00:00:00Z'  for end

    df = fetch_and_prepare_data(
        exchange, symbol, timeframe, start_date=start_date, end_date=end_date
    )


    df['tenkan_sen'] = (df['High'] + df['Low']) / 2
    df['kijun_sen'] = (df['High'].rolling(window=26).max() + df['Low'].rolling(window=26).min()) / 2
    df['senkou_span_a'] = (df["tenkan_sen"] + df['kijun_sen']) / 2
    df['senkou_span_b'] = (df['High'].rolling(window=52).max() + df['Low'].rolling(window=52).min()) / 2
    df['chikou_span']  = df["Close"].shift(periods=-26)
    df['cloud_top'] = (df['senkou_span_a'] + df['senkou_span_b']) /2
    df['cloud_bottom'] = (df['High'].rolling(window=52).max() + df['Low'].rolling(window=52).min()) / 2
    df['ema'] = df['Close'].ewm(span=14).mean()

    signal_conditions=[
        (df['Close'] > df['cloud_top']),
        (df['Close']) < df['cloud_top']
    ]

    signal_choices = [1, -1]

    df['signal'] = np.select(condlist=signal_conditions, choicelist=signal_choices, default=0) 
    df['sginal'] = df['signal'].shift(periods=1)


    conditions = [
        (df['signal'] == 1) & (df['signal'] != df['signal'].shift(periods=1)),
        (df['signal'] == -1) & (df['signal'] != df['signal'].shift(periods=1))
    ]

    choices = [1, -1]
    df['positions'] = np.select(condlist=conditions, choicelist=choices, default=np.nan)


    df = df.tail(20)
    plt.figure(figsize=(10,5))
    plt.plot(df.index, df['senkou_span_a'], label='Senkou span A')
    plt.plot(df.index, df['senkou_span_b'], label='Senkou span B')
    plt.plot(df.index, df['chikou_span'], label='Chikou Span')
    plt.plot(df.index, df['cloud_top'], label='Cloud Top')
    plt.plot(df.index, df['cloud_bottom'], label='Cloud Bottom')
    plt.plot(df.index, df['tenkan_sen'], label='Tenkan Sen')
    plt.plot(df.index, df['kijun_sen'], label='Kijun Sen')
    plt.plot(df.index, df['Close'], label='Close price', color='black')
    plt.plot(df.index, df['ema'], label='14 EMA')

    plt.scatter(x=df.index[df['positions'] == 1], y=df['Close'][df['positions'] == 1], color='green', label='Buy position', marker="^", s=100)
    plt.scatter(x=df.index[df['positions'] == -1], y=df['Close'][df['positions'] == -1], color='red', label='Sell position', marker="v", s=100)
    plt.fill_between(x=df.index, y1=df['Close'], y2=df['cloud_top'], where=(df['Close'] > df['cloud_top']), color='lightgreen', alpha=0.3, label='Buy')
    plt.fill_between(x=df.index, y1=df['Close'], y2=df['cloud_top'], where=(df['Close'] < df['cloud_top']), color='lightcoral', alpha=0.3, label='Sell')

    # Display the plot with a legend.
    plt.legend()
    plt.show()


    initial_capital = 100
    capital = initial_capital
    profit = 0
    # Access the first row by position using iloc instead of loc
    prev_signal = df.iloc[0]['signal']
    # Fix the typo from 'prves_close' to 'prev_close'
    prev_close = df.iloc[0]['Close']

    for i in range(len(df)):
        current_signal = df.iloc[i]['signal']
        if current_signal != prev_signal:
            if current_signal == 1:
                profit = capital * (df.iloc[i]['Close'] - prev_close) / prev_close
                capital += profit
            elif current_signal == -1:
                profit = capital * (prev_close - df.iloc[i]['Close']) / df.iloc[i]['Close']
                capital += profit

            prev_close = df.iloc[i]['Close']

        prev_signal = current_signal

    overall_profit = capital - initial_capital


    pl_percentage = (capital - initial_capital) / initial_capital * 100

    # Print the results
    print(f'Initial capital: {initial_capital} USD')
    print(f'Final capital: {capital} USD')
    print(f'Overall Profit: {overall_profit:.2f} USD')
    print(f'Percentage Profit Gain: {pl_percentage:.2f}%')