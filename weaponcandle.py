import ccxt
import pandas as pd
import numpy as np
from itertools import product

# Initialize exchange (example: Binance, you can replace it with your preferred exchange)
exchange = ccxt.binance({
    'rateLimit': 1200,
    'enableRateLimit': True,
})

# Fetch OHLCV data
def fetch_ohlcv(symbol, timeframe='15m', limit=1000):
    bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

# Calculate RSI manually
def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    
    avg_gain = pd.Series(gain).rolling(window=period).mean()
    avg_loss = pd.Series(loss).rolling(window=period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

# Calculate EMA manually
def calculate_ema(df, period=9):
    return df['close'].ewm(span=period, adjust=False).mean()

# Calculate VWAP manually
def calculate_vwap(df):
    cumulative_vwap = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum()
    cumulative_volume = df['volume'].cumsum()
    vwap = cumulative_vwap / cumulative_volume
    return vwap

# Calculate MACD manually
def calculate_macd(df, fast_period=12, slow_period=26, signal_period=9):
    ema_fast = df['close'].ewm(span=fast_period, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow_period, adjust=False).mean()
    
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=signal_period, adjust=False).mean()
    
    return macd, signal

# Apply indicators with flexible periods
def apply_indicators(df, rsi_period=14, ema_period=9, macd_fast=12, macd_slow=26, macd_signal=9):
    df['RSI'] = calculate_rsi(df, period=rsi_period)
    df['EMA'] = calculate_ema(df, period=ema_period)
    df['VWAP'] = calculate_vwap(df)
    df['MACD'], df['MACD_signal'] = calculate_macd(df, fast_period=macd_fast, slow_period=macd_slow, signal_period=macd_signal)
    return df

# Identify weapon candle
def identify_weapon_candle(df):
    weapon_candles = []
    for i in range(1, len(df)):
        left_candle = df.iloc[i - 1]
        current_candle = df.iloc[i]

        # Left candle close and open below EMA
        if left_candle['close'] < left_candle['EMA'] and left_candle['open'] < left_candle['EMA']:
            # Current candle close above EMA and MACD histogram above zero
            if current_candle['close'] > current_candle['EMA'] and (current_candle['MACD'] - current_candle['MACD_signal']) > 0:
                weapon_candles.append(i)

    return weapon_candles

# Backtesting strategy with return of results
def backtest(df, weapon_candles):
    entry_price = None
    stop_loss = None
    target_price = None
    profit = 0
    loss = 0
    trades = 0

    for i in weapon_candles:
        current_candle = df.iloc[i]
        
        # Entry conditions
        if entry_price is None:
            entry_price = current_candle['high']
            stop_loss = current_candle['low']
            target_price = entry_price + (entry_price - stop_loss)
            trades += 1

        # Exit conditions
        if entry_price:
            if df.iloc[i]['low'] <= stop_loss:
                loss += 1
                entry_price = stop_loss = target_price = None
            elif df.iloc[i]['high'] >= target_price:
                profit += 1
                entry_price = stop_loss = target_price = None
            elif (df.iloc[i]['MACD'] - df.iloc[i]['MACD_signal']) <= 0:
                if df.iloc[i]['close'] > entry_price:
                    profit += 1
                else:
                    loss += 1
                entry_price = stop_loss = target_price = None

    # Return results (profit, loss, win rate)
    if trades > 0:
        win_rate = (profit / trades) * 100
        return profit, loss, win_rate
    else:
        return 0, 0, 0

# Function to optimize parameters
def optimize_parameters(symbol, df, param_grid):
    results = []
    
    for params in param_grid:
        rsi_period, ema_period, macd_fast, macd_slow, macd_signal = params
        df_with_indicators = apply_indicators(df.copy(), rsi_period, ema_period, macd_fast, macd_slow, macd_signal)
        weapon_candles = identify_weapon_candle(df_with_indicators)
        profit, loss, win_rate = backtest(df_with_indicators, weapon_candles)
        results.append({
            'rsi_period': rsi_period,
            'ema_period': ema_period,
            'macd_fast': macd_fast,
            'macd_slow': macd_slow,
            'macd_signal': macd_signal,
            'profit': profit,
            'loss': loss,
            'win_rate': win_rate
        })
    
    # Sort results by profit and return top 5
    results = sorted(results, key=lambda x: x['profit'], reverse=True)
    return results[:5]

# Generate parameter combinations (grid search)
def generate_param_grid():
    rsi_periods = np.arange(3, 50, 1)  # Min 7, Max 28, Step 3
    ema_periods = np.arange(3, 50, 1)  # Min 5, Max 21, Step 2
    macd_fast_periods = np.arange(3, 50, 1)  # Min 5, Max 20, Step 3
    macd_slow_periods = np.arange(3, 50, 1)  # Min 20, Max 40, Step 5
    macd_signal_periods = np.arange(3, 50, 1)  # Min 5, Max 15, Step 2
    
    param_grid = product(rsi_periods, ema_periods, macd_fast_periods, macd_slow_periods, macd_signal_periods)
    return list(param_grid)

# Main execution with optimization
symbol = 'BTC/USDT'  # Example symbol (change to your desired asset)
df = fetch_ohlcv(symbol)

# Generate the grid of parameters to test
param_grid = generate_param_grid()

# Optimize the parameters
top_results = optimize_parameters(symbol, df, param_grid)

# Display top 5 results
for result in top_results:
    print(result)
