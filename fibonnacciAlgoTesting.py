import pandas as pd
import numpy as np
import ccxt
import ta
import matplotlib.pyplot as plt
import datetime

# Initialize Bybit with specified options
exchange = ccxt.bybit({
    'options': {
        'defaultType': 'future',  # Correct type for futures trading
        'defaultSubType': 'linear'  # Bybit USDT perpetual futures are linear contracts
    },
    'rateLimit': 1200,
    'enableRateLimit': True,
})

def fetch_data(symbol, timeframe, limit):
    """
    Fetch historical data from the exchange.
    """
    all_data = []
    batch_size = 1000
    fetch_limit = limit
    since = None

    while fetch_limit > 0:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=min(batch_size, fetch_limit), since=since)
            if not ohlcv:
                break
            all_data.extend(ohlcv)
            since = ohlcv[-1][0] + 1
            fetch_limit -= batch_size
        except Exception as e:
            print(f"Error fetching data: {e}")
            break

    data = pd.DataFrame(all_data, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
    data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
    return data

def identify_trend(data, short_window=20, long_window=50):
    """
    Identify market trend using moving averages.
    """
    data['MA_Short'] = data['Close'].rolling(window=short_window).mean()
    data['MA_Long'] = data['Close'].rolling(window=long_window).mean()
    data['Trend'] = np.where(data['MA_Short'] > data['MA_Long'], 'Up', 'Down')
    return data

def identify_swing_points(data, window=5):
    """
    Identify swing high and low points in the data.
    """
    data['Swing_High'] = data['High'][
        (data['High'].shift(1) < data['High']) & 
        (data['High'].shift(-1) < data['High']) & 
        (data['High'].rolling(window).max() == data['High'])
    ]
    
    data['Swing_Low'] = data['Low'][
        (data['Low'].shift(1) > data['Low']) & 
        (data['Low'].shift(-1) > data['Low']) & 
        (data['Low'].rolling(window).min() == data['Low'])
    ]
    
    return data

def calculate_fibonacci_levels(swing_high, swing_low):
    """
    Calculate Fibonacci retracement levels.
    """
    levels = {
        "106.8%": swing_high + 0.068 * (swing_high - swing_low),
        '100.0%': swing_high,
        '61.8%': swing_high - 0.618 * (swing_high - swing_low),
        '50.0%': swing_high - 0.5 * (swing_high - swing_low),
        '38.2%': swing_high - 0.382 * (swing_high - swing_low),
        '23.6%': swing_high - 0.236 * (swing_high - swing_low),
        '0.0%': swing_low
    }
    return levels

def generate_signals(data, fib_levels):
    """
    Generate buy and sell signals based on Fibonacci levels and trend.
    """
    signals = pd.DataFrame(index=data.index)
    signals['Buy'] = (
        (data['Close'] > fib_levels['38.2%']) & 
        (data['Close'].shift(1) <= fib_levels['38.2%']) & 
        (data['Trend'] == 'Up')
    ).astype(int)
    
    signals['Sell'] = (
        (data['Close'] < fib_levels['61.8%']) & 
        (data['Close'].shift(1) >= fib_levels['61.8%']) & 
        (data['Trend'] == 'Down')
    ).astype(int)
    
    return signals

def position_size(account_size, risk_per_trade, atr):
    """
    Calculate position size based on risk management.
    """
    return (account_size * risk_per_trade) / atr

def backtest_strategy(data, signals, initial_balance=10000, risk_per_trade=0.01):
    """
    Backtest the trading strategy based on generated signals.
    """
    balance = initial_balance
    position = 0
    balance_history = [balance]  # Initialize with the initial balance
    
    for i in range(1, len(data)):
        if signals['Buy'][i] == 1 and balance > 0:
            atr = data['ATR'][i]
            size = position_size(balance, risk_per_trade, atr)
            entry_price = data['Close'][i]
            position = size / entry_price
            balance -= position * entry_price
        
        if signals['Sell'][i] == 1 and position > 0:
            balance += position * data['Close'][i]
            position = 0
        
        balance_history.append(balance)
    
    return pd.Series(balance_history, index=data.index)

# Fetch historical data
data = fetch_data('BTC/USDT', '1h', 3000)  # Fetch more data

if data.empty:
    raise ValueError("Failed to fetch data or no data available.")

# Ensure we have enough data for calculations
if len(data) < 100:  # Adjusted to ensure sufficient data for rolling calculations
    raise ValueError("Not enough data to perform analysis. Please provide more historical data.")

# Calculate technical indicators
data['ATR'] = ta.volatility.AverageTrueRange(data['High'], data['Low'], data['Close'], window=14).average_true_range()

# Identify trend direction
data = identify_trend(data)

# Identify swing points
data = identify_swing_points(data)

# Ensure we have valid swing points
if data['Swing_High'].dropna().empty or data['Swing_Low'].dropna().empty:
    raise ValueError("Not enough swing points identified. Adjust window size or provide more data.")

# Calculate Fibonacci levels for the latest swing high and low
latest_swing_high = data['Swing_High'].dropna().iloc[-1]
latest_swing_low = data['Swing_Low'].dropna().iloc[-1]
fib_levels = calculate_fibonacci_levels(latest_swing_high, latest_swing_low)

# Generate signals
signals = generate_signals(data, fib_levels)

# Backtest the strategy
balance_history = backtest_strategy(data, signals)

# Plot the results
def plot_results(data, fib_levels, balance_history):
    """
    Plot the Fibonacci levels and backtest results.
    """
    plt.figure(figsize=(14, 7))
    plt.plot(data['Close'], label='Close Price', color='black')
    for level in fib_levels.values():
        plt.axhline(level, linestyle='--', color='red')
    plt.legend(['Close Price'] + list(fib_levels.keys()))
    plt.title('Fibonacci Retracement Strategy with Trend Identification')
    plt.show()

    plt.figure(figsize=(14, 7))
    plt.plot(balance_history, label='Account Balance')
    plt.title('Strategy Backtest Results')
    plt.legend()
    plt.show()

# Plot the results
plot_results(data, fib_levels, balance_history)
