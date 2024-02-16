import pandas as pd 

def fetch_and_prepare_data(exchange, symbol, timeframe, limit=2000):
    ohlcv_data = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    keys = ['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']
    ohlcv_dicts = [dict(zip(keys, data)) for data in ohlcv_data]
    df = pd.DataFrame(ohlcv_dicts)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    first_candle_date = df.index.min()
    last_candle_date = df.index.max()
    print(f'Backtest data: {exchange}-{symbol}-{timeframe}: {first_candle_date} - {last_candle_date} ')
    print(f'Count of OHLCV rows: {len(df.index)}')
    return df