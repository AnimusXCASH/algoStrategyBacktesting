"""
Trend indicator which has following indicators:

3x EMA 20,50,200 length 
Calculated on timeframes 5, 15, 1H and 4H
Also showcasing the allginment

"""

import ccxt
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pandas as pd
import numpy as np
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from utils.dataManipulation import fetch_and_prepare_data
from datetime import datetime, time, timezone
import pytz
from colorama import Fore, init

init(autoreset=True)

# Initialize the exchange
exchange = ccxt.bybit({
    'options': {
        'defaultType': 'future',  # Correct type for futures trading
        'defaultSubType': 'linear'  # Bybit USDT perpetual futures are linear contracts
    },
    'rateLimit': 1200,
    'enableRateLimit': True,
})


def calculate_ema_pine(df, column, length):
    alpha = 2 / (length + 1)
    close_prices = df[column].values
    ema = np.zeros_like(close_prices)
    ema[0] = close_prices[0]
    for i in range(1, len(close_prices)):
        ema[i] = alpha * close_prices[i] + (1 - alpha) * ema[i - 1]
    return ema

def add_multiple_emas(df, column, lengths):
    for length in lengths:
        ema_column_name = f'EMA_{length}'
        df[ema_column_name] = calculate_ema_pine(df, column, length)
    return df

def check_ema_alignment(df):
    latest_data = df.iloc[-1]
    ema_20 = latest_data['EMA_20']
    ema_50 = latest_data['EMA_50']
    ema_200 = latest_data['EMA_200']
    
    if ema_20 > ema_50 > ema_200:
        return Fore.LIGHTGREEN_EX + "BULLISH"
    elif ema_20 < ema_50 < ema_200:
        return Fore.LIGHTRED_EX + "BEARISH"
    else:
        return Fore.LIGHTYELLOW_EX + "NOT ALIGNED"
    
def plot_ohlcv_with_emas(df, symbol):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                        row_heights=[0.7, 0.3])

    # Candlestick chart for OHLCV data
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                                 name='OHLC'), row=1, col=1)

    # Plotting EMAs
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA_20'], mode='lines', name='EMA 20', line=dict(color='blue')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA_50'], mode='lines', name='EMA 50', line=dict(color='red')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA_200'], mode='lines', name='EMA 200', line=dict(color='green')), row=1, col=1)

    # Volume bar chart
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker=dict(color='purple')), row=2, col=1)

    # Layout
    fig.update_layout(title=f'{symbol} OHLCV with EMAs', xaxis_title='Date', yaxis_title='Price',
                      xaxis2_title='Date', yaxis2_title='Volume',
                      height=800, showlegend=True)

    fig.show()

def resample_data(df, timeframes):
    resampled_dfs = {}
    for timeframe in timeframes:
        resampled_df = df.resample(timeframe).agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()
        resampled_dfs[timeframe] = resampled_df
    return resampled_dfs

def analyze_timeframes(exchange, symbol, timeframes, start_date, ema_lengths):
    df_5m = fetch_and_prepare_data(exchange, symbol, '5m', start_date=start_date, end_date=None)
    resampled_dfs = resample_data(df_5m, timeframes)
    results = {}
    for timeframe, df in resampled_dfs.items():
        df = add_multiple_emas(df, 'Close', ema_lengths)
        alignment = check_ema_alignment(df)
        results[timeframe] = alignment
        print(f"EMA Lineup for {timeframe}: {alignment}")
    return results, df_5m

def is_ny_trading_hours():
    ny_tz = pytz.timezone('America/New_York')
    utc_now = datetime.now(timezone.utc)
    ny_now = utc_now.astimezone(ny_tz)
    start_time = ny_tz.localize(datetime.combine(ny_now.date(), time(7, 00)))
    end_time = ny_tz.localize(datetime.combine(ny_now.date(), time(11, 0)))
    print(f"Current New York Time: {ny_now.strftime('%Y-%m-%d %H:%M:%S')}")
    if start_time <= ny_now <= end_time:
        return True
    return False



# Parameters
symbol = "AVAX/USDT"
start_date = "2024-05-01T00:00:00Z"
ema_lengths = [20, 50, 200]  # EMA periods
timeframes = ["15min", "1h", "4h"]  # Timeframes to analyze (using pandas resample rule codes)

# Check if we are in the New York trading hours
if is_ny_trading_hours():
    print(Fore.LIGHTRED_EX + "We are currently within the New York trading hours.")
else:
    print(Fore.LIGHTRED_EX + "We are currently outside the New York trading hours.")

# Analyze all timeframes
results, df_5m = analyze_timeframes(exchange, symbol, timeframes, start_date, ema_lengths)

# Check and print alignment for the 5-minute timeframe
df_5m = add_multiple_emas(df_5m, 'Close', ema_lengths)
alignment_5m = check_ema_alignment(df_5m)
print(f"EMA Lineup for 5m: {alignment_5m}")

# Plot the major timeframe (5 minutes)
plot_ohlcv_with_emas(df_5m.tail(100), symbol)
