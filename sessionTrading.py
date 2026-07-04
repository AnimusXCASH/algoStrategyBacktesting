import ccxt
import pandas as pd
import datetime
import time

pd.set_option('display.max_rows', None)  # Display all rows
pd.set_option('display.max_columns', None)  # Display all columns

# Set up the CCXT Bybit client
exchange = ccxt.bybit({
    'options': {'defaultType': 'future', 'defaultSubType': 'inverse'},
    'rateLimit': 1200,
    'enableRateLimit': True,
})


# Function to get OHLCV data for a specified symbol
def get_ohlcv(symbol, timeframe="1m", since=None):
    """Fetch OHLCV data for a given symbol."""
    try:
        ohlcv = exchange.fetch_ohlcv(symbol=symbol, timeframe=timeframe, since=since)
        df = pd.DataFrame(
            ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)  # Always UTC
        return df
    except Exception as e:
        print(f"Error fetching OHLCV data: {e}")
        return None


# Function to calculate the high and low of the session
def get_session_high_low(df):
    session_high = df["high"].max()
    session_low = df["low"].min()
    print(f"Session High: {session_high}, Session Low: {session_low}")
    return session_high, session_low


# Function to calculate Fibonacci levels
def calculate_fibonacci_levels(session_low, new_high):
    """Calculate Fibonacci levels based on the session low and the latest high."""
    fib_61_8 = session_low + (new_high - session_low) * 0.6180
    fib_38_2 = session_low + (new_high - session_low) * 0.3820
    fib_17_0 = session_low + (new_high - session_low) * 0.1700
    fib_minus_7_0 = session_low + (new_high - session_low) * -0.0700
    fib_levels = {
        "Fib 61.8%": fib_61_8,
        "Fib 38.2%": fib_38_2,
        "Fib 17.0%": fib_17_0,
        "Fib -7.0%": fib_minus_7_0,
        "New High": new_high,
        "Session Low": session_low,
    }
    return fib_levels


# Monitor for breakout after session close and find highest high
def monitor_breakout(symbol, session_high, session_low):
    """Monitor for breakout after session ends, then track higher highs."""
    print("Monitoring for breakout after session close...")

    breakout_detected = False
    current_high = session_high  # Start with the session high for comparison

    # Fetch all the candles since the session end to find any potential breakout
    now = datetime.datetime.now(datetime.timezone.utc)
    post_session_data = get_ohlcv(symbol, timeframe="1m", since=int(now.replace(hour=15, minute=0, second=0, microsecond=0).timestamp() * 1000))

    if post_session_data is None:
        print("Error fetching post-session data. Retrying in 1 minute...")
        time.sleep(60)
        return

    # Iterate through the post-session data to detect if a breakout has already occurred
    for index, row in post_session_data.iterrows():
        high = row['high']
        low = row['low']

        # Check if a breakout already occurred
        if not breakout_detected and high > session_high and low >= session_low:
            print(f"Breakout detected! Price has broken the session high of {session_high} at {row['timestamp']}")
            breakout_detected = True
            current_high = high

        # If breakout already occurred, track the highest high
        if breakout_detected and high > current_high:
            current_high = high
            print(f"New higher high after breakout detected at {row['timestamp']}. Highest high: {current_high}")
            fib_levels = calculate_fibonacci_levels(session_low, current_high)
            for level, value in fib_levels.items():
                print(f"{level}: {value}")

    # After processing historical candles, continue monitoring for new higher highs in real time
    if breakout_detected:
        print("Continuing to monitor for higher highs...")
    else:
        print("No breakout detected yet. Waiting for a breakout in real time...")

    # Start monitoring 1-minute candles in real time
    while True:
        now = datetime.datetime.now(datetime.timezone.utc)

        # Fetch the latest 1-minute candle
        df = get_ohlcv(symbol, timeframe="1m")
        if df is None:
            time.sleep(60)  # In case of API failure, sleep and retry
            continue
        
        latest_high = df.iloc[-1]["high"]
        latest_low = df.iloc[-1]["low"]
        print(f"Latest candle high: {latest_high}, low: {latest_low}")

        # If no breakout detected yet, monitor for a breakout in real time
        if not breakout_detected and latest_high > session_high and latest_low >= session_low:
            print(f"Real-time breakout detected! Price has broken the session high of {session_high}")
            breakout_detected = True
            current_high = latest_high
            fib_levels = calculate_fibonacci_levels(session_low, current_high)
            for level, value in fib_levels.items():
                print(f"{level}: {value}")

        # After breakout, monitor for new higher highs in real time
        if breakout_detected:
            if latest_high > current_high:
                current_high = latest_high
                fib_levels = calculate_fibonacci_levels(session_low, current_high)
                print("New higher high detected. Fibonacci levels updated:")
                for level, value in fib_levels.items():
                    print(f"{level}: {value}")
            else:
                print("No new higher high detected. Continuing to monitor...")

        # Sleep until the next candle (1 minute)
        time_left = 60 - now.second
        time.sleep(time_left)


# Main 24-hour monitoring loop
def start_24h_monitoring(symbol):
    """Start the continuous 24-hour monitoring process."""
    while True:
        now = datetime.datetime.now(datetime.timezone.utc)
        today = now.date()

        session_start_time = datetime.datetime(
            today.year, today.month, today.day, 12, 0, 0, tzinfo=datetime.timezone.utc
        )
        session_end_time = datetime.datetime(
            today.year, today.month, today.day, 15, 0, 0, tzinfo=datetime.timezone.utc
        )

        # Before 15:00 (session still open)
        if now < session_start_time:
            time_until_close = session_end_time - now
            hours, remainder = divmod(time_until_close.seconds, 3600)
            minutes = remainder // 60
            print(f"Waiting for session to start in {hours} hours, {minutes} minutes...")
            time.sleep(60)
            continue

        # After 15:00 but before 00:00 (session closed, start monitoring for breakout)
        elif session_end_time <= now < datetime.datetime(
            today.year, today.month, today.day, 23, 59, 59, tzinfo=datetime.timezone.utc
        ):
            print("Session has ended. Identifying session high and low...")
            ohlcv_data = get_ohlcv(symbol=symbol, since=int(session_start_time.timestamp() * 1000))
            if ohlcv_data is None:
                time.sleep(60)
                continue
            session_high, session_low = get_session_high_low(ohlcv_data)
            print(f"Session High: {session_high}, Session Low: {session_low}")
            monitor_breakout(symbol, session_high, session_low)

        # After 00:00 (new day)
        elif now >= datetime.datetime(
            today.year, today.month, today.day, 0, 0, 0, tzinfo=datetime.timezone.utc
        ):
            session_high, session_low = reset_for_new_day()


# Reset function for new day after 00:00
def reset_for_new_day():
    print("New day detected. Resetting session data...")
    session_high = float("-inf")
    session_low = float("inf")
    exit()
    return session_high, session_low


if __name__ == "__main__":
    symbol = "BTC/USDT:USDT"
    start_24h_monitoring(symbol)
