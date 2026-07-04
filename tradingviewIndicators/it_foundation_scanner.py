import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, time, timezone
import pytz
from colorama import Fore, init
from tabulate import tabulate
import time as t

# Initialize the exchange
exchange = ccxt.bybit({
    'options': {
        'defaultType': 'future',
        'defaultSubType': 'linear'
    },
    'rateLimit': 1200,
    'enableRateLimit': True,
})

init(autoreset=True)

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
        return "BULLISH"
    elif ema_20 < ema_50 < ema_200:
        return "BEARISH"
    else:
        return "NOT ALIGNED"

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

def analyze_timeframes(df, timeframes, ema_lengths):
    resampled_dfs = resample_data(df, timeframes)
    results = {}
    for timeframe, df in resampled_dfs.items():
        df = add_multiple_emas(df, 'Close', ema_lengths)
        alignment = check_ema_alignment(df)
        results[timeframe] = alignment
    return results

def fetch_all_tradable_pairs(exchange, count=50):
    # Load the markets
    markets = exchange.load_markets()

    # Filter markets to include only USDT perpetual futures
    usdt_perpetual_markets = [market for market in markets.values() if market['linear'] and market['quoteId'] == "USDT" and "100" not in market['symbol']]

    # Fetch tickers to get volume information
    tickers = exchange.fetch_tickers()

    # Filter tickers to include only those that match the USDT perpetual markets
    usdt_perpetual_tickers = {symbol: tickers[symbol] for symbol in tickers if symbol in [market['symbol'] for market in usdt_perpetual_markets]}

    # Sort tickers by volume from highest to lowest
    sorted_tickers = sorted(usdt_perpetual_tickers.values(), key=lambda x: x['quoteVolume'], reverse=True)

    # Get the top 'count' symbols by volume
    top_symbols = [ticker['symbol'] for ticker in sorted_tickers[:count]]
    
    return top_symbols

def fetch_and_prepare_data(exchange, symbol, timeframe, start_date):
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=exchange.parse8601(start_date))
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df

def is_ny_trading_hours():
    ny_tz = pytz.timezone('America/New_York')
    utc_now = datetime.now(timezone.utc)
    ny_now = utc_now.astimezone(ny_tz)
    start_time = ny_tz.localize(datetime.combine(ny_now.date(), time(7, 00)))
    end_time = ny_tz.localize(datetime.combine(ny_now.date(), time(11, 0)))
    if start_time <= ny_now <= end_time:
        return True
    return False

def colorize_alignment(alignment):
    if alignment == "BULLISH":
        return Fore.LIGHTGREEN_EX + alignment + Fore.RESET
    elif alignment == "BEARISH":
        return Fore.LIGHTRED_EX + alignment + Fore.RESET
    else:
        return Fore.LIGHTYELLOW_EX + alignment + Fore.RESET

if __name__ == "__main__":
    # Parameters
    start_date = "2024-05-01T00:00:00Z"
    ema_lengths = [20, 50, 200]
    timeframes = ["15min", "1h", "4h"]

    # Fetch all tradable pairs
    pairs = fetch_all_tradable_pairs(exchange, count=10)

    # Check if we are in the New York trading hours
    if is_ny_trading_hours():
        print(Fore.LIGHTRED_EX + "We are currently within the New York trading hours.")
    else:
        print(Fore.LIGHTRED_EX + "We are currently outside the New York trading hours.")

    # Analyze each pair and collect results
    results = []
    start_time = t.time()
    for pair in pairs:
        try:
            df_5m = fetch_and_prepare_data(exchange, pair, '5m', start_date=start_date)
            timeframes_analysis = analyze_timeframes(df_5m, timeframes, ema_lengths)

            # Check and add alignment for the 5-minute timeframe
            df_5m = add_multiple_emas(df_5m, 'Close', ema_lengths)
            alignment_5m = check_ema_alignment(df_5m)
            timeframes_analysis['5m'] = alignment_5m
            
            colored_analysis = [pair] + [colorize_alignment(timeframes_analysis[tf]) for tf in ['5m', '15min', '1h', '4h']]
            results.append(colored_analysis)
        except Exception as e:
            print(f"Error processing pair {pair}: {e}")

    # End timing
    end_time = t.time()
    elapsed_time = end_time - start_time

    # Print results as a table
    table_headers = ['Pair', '5m', '15min', '1h', '4h']
    print(tabulate(results, headers=table_headers, tablefmt='pretty'))

    # Print the elapsed time
    print(f"Total execution time: {elapsed_time} seconds")
