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
from plotly.subplots import make_subplots
from utils.timeFunctions import is_ny_trading_hours
from indicatorsRewritePine.ema import add_multiple_emas

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

def find_latest_bullish_alignment_point(df):
    for i in range(len(df) - 1, 0, -1):  # Start from the latest data point and move backwards
        if df['EMA_20'].iloc[i] > df['EMA_50'].iloc[i] > df['EMA_200'].iloc[i]:
            # Check that the previous data point was not bullishly aligned
            if not (df['EMA_20'].iloc[i-1] > df['EMA_50'].iloc[i-1] and df['EMA_50'].iloc[i-1] > df['EMA_200'].iloc[i-1]):
                return i
    return None

def find_latest_bearish_alignment_point(df):
    for i in range(len(df) - 1, 0, -1):  # Start from the latest data point and move backwards
        if df['EMA_20'].iloc[i] < df['EMA_50'].iloc[i] < df['EMA_200'].iloc[i]:
            # Check that the previous data point was not bearishly aligned
            if not (df['EMA_20'].iloc[i-1] < df['EMA_50'].iloc[i-1] and df['EMA_50'].iloc[i-1] < df['EMA_200'].iloc[i-1]):
                return i
    return None

def find_swing_low(df, alignment_index, window=10):
    for i in range(alignment_index - 1, window - 1, -1):
        is_swing_low = True
        for j in range(1, window + 1):
            if df['Low'].iloc[i] >= df['Low'].iloc[i - j] or df['Low'].iloc[i] >= df['Low'].iloc[i + j]:
                is_swing_low = False
                break
        if is_swing_low:
            return i, df['Low'].iloc[i]
    return None, None

def find_swing_high(df, alignment_index, window=10):
    for i in range(alignment_index + 1, len(df) - window):
        is_swing_high = True
        for j in range(1, window + 1):
            if df['High'].iloc[i] <= df['High'].iloc[i - j] or df['High'].iloc[i] <= df['High'].iloc[i + j]:
                is_swing_high = False
                break
        if is_swing_high:
            return i, df['High'].iloc[i]
    return None, None

def find_previous_swing_high(df, alignment_index, window=10):
    for i in range(alignment_index - 1, window - 1, -1):
        is_swing_high = True
        for j in range(1, window + 1):
            if df['High'].iloc[i] <= df['High'].iloc[i - j] or df['High'].iloc[i] <= df['High'].iloc[i + j]:
                is_swing_high = False
                break
        if is_swing_high:
            return i, df['High'].iloc[i]
    return None, None

def find_previous_swing_low(df, alignment_index, window=10):
    for i in range(alignment_index - 1, window - 1, -1):
        is_swing_low = True
        for j in range(1, window + 1):
            if df['Low'].iloc[i] >= df['Low'].iloc[i - j] or df['Low'].iloc[i] >= df['Low'].iloc[i + j]:
                is_swing_low = False
                break
        if is_swing_low:
            return i, df['Low'].iloc[i]
    return None, None

def plot_ohlcv_with_emas(df, symbol):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                        row_heights=[0.8, 0.2])

    # Candlestick chart for OHLCV data
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                                 name='OHLC'), row=1, col=1)

    # Plotting EMAs
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA_20'], mode='lines', name='EMA 20', line=dict(color='blue')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA_50'], mode='lines', name='EMA 50', line=dict(color='red')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['EMA_200'], mode='lines', name='EMA 200', line=dict(color='green')), row=1, col=1)

    # Volume bar chart on the second chart
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker=dict(color='purple')), row=2, col=1)

    # Marking the latest bullish alignment point
    bullish_alignment_index = find_latest_bullish_alignment_point(df)
    if bullish_alignment_index is not None:
        bullish_alignment_date = df.index[bullish_alignment_index]
        bullish_alignment_price = df['Close'].iloc[bullish_alignment_index]
        fig.add_trace(go.Scatter(x=[bullish_alignment_date], y=[bullish_alignment_price],
                                 mode='markers', marker=dict(color='black', size=10), name='Latest Bullish Alignment'), row=1, col=1)
        print(f"Latest bullish alignment marker added at index {bullish_alignment_index}, Date: {bullish_alignment_date}, Price: {bullish_alignment_price}")

        # Find and plot the swing low
        swing_low_index, swing_low_price = find_swing_low(df, bullish_alignment_index)
        if swing_low_index is not None:
            swing_low_date = df.index[swing_low_index]
            fig.add_trace(go.Scatter(x=[swing_low_date], y=[swing_low_price],
                                     mode='markers', marker=dict(color='red', size=10), name='Swing Low'), row=1, col=1)
            print(f"Swing low marker added at index {swing_low_index}, Date: {swing_low_date}, Price: {swing_low_price}")
        
        # Find and plot the swing high
        swing_high_index, swing_high_price = find_swing_high(df, bullish_alignment_index)
        if swing_high_index is not None:
            swing_high_date = df.index[swing_high_index]
            fig.add_trace(go.Scatter(x=[swing_high_date], y=[swing_high_price],
                                     mode='markers', marker=dict(color='green', size=10), name='Swing High'), row=1, col=1)
            print(f"Swing high marker added at index {swing_high_index}, Date: {swing_high_date}, Price: {swing_high_price}")

    else:
        print(Fore.RED + f'No bullish alignment latest found')

    # Marking the latest bearish alignment point
    bearish_alignment_index = find_latest_bearish_alignment_point(df)
    if bearish_alignment_index is not None:
        bearish_alignment_date = df.index[bearish_alignment_index]
        bearish_alignment_price = df['Close'].iloc[bearish_alignment_index]
        fig.add_trace(go.Scatter(x=[bearish_alignment_date], y=[bearish_alignment_price],
                                 mode='markers', marker=dict(color='orange', size=10), name='Latest Bearish Alignment'), row=1, col=1)
        print(f"Latest bearish alignment marker added at index {bearish_alignment_index}, Date: {bearish_alignment_date}, Price: {bearish_alignment_price}")

        # Find and plot the previous swing high
        previous_swing_high_index, previous_swing_high_price = find_previous_swing_high(df, bearish_alignment_index)
        if previous_swing_high_index is not None:
            previous_swing_high_date = df.index[previous_swing_high_index]
            fig.add_trace(go.Scatter(x=[previous_swing_high_date], y=[previous_swing_high_price],
                                     mode='markers', marker=dict(color='yellow', size=10), name='Previous Swing High'), row=1, col=1)
            print(f"Previous swing high marker added at index {previous_swing_high_index}, Date: {previous_swing_high_date}, Price: {previous_swing_high_price}")

        # Find and plot the next swing low
        swing_low_index, swing_low_price = find_swing_low(df, bearish_alignment_index)
        if swing_low_index is not None:
            swing_low_date = df.index[swing_low_index]
            fig.add_trace(go.Scatter(x=[swing_low_date], y=[swing_low_price],
                                     mode='markers', marker=dict(color='blue', size=10), name='Swing Low After Bearish Alignment'), row=1, col=1)
            print(f"Swing low marker added at index {swing_low_index}, Date: {swing_low_date}, Price: {swing_low_price}")
    else:
        print(Fore.RED + f'No bearish alignment latest found')

    # Layout
    fig.update_layout(
        title=f'{symbol} OHLCV with EMAs',
        xaxis_title='Date',
        yaxis_title='Price',
        height=800,
        showlegend=True,
        plot_bgcolor='black',
        paper_bgcolor='black',
        font=dict(color='white'),
        xaxis=dict(showgrid=False, rangeslider=dict(visible=True)),
        yaxis=dict(showgrid=False, fixedrange=False),
        xaxis2=dict(showgrid=True, gridcolor='gray'),
        yaxis2=dict(showgrid=True, gridcolor='gray'),
    )

    config = {'scrollZoom': True}  # Enable scroll zoom

    fig.show(config=config)

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

# Parameters
symbol = "AVAX/USDT"
start_date = "2024-06-01T00:00:00Z"
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
df_5m = df_5m.tail(300)  # Focus on the last 100 rows for clarity
alignment_5m = check_ema_alignment(df_5m)
print(f"EMA Lineup for 5m: {alignment_5m}")

# Plot the major timeframe (5 minutes)
plot_ohlcv_with_emas(df_5m, symbol)