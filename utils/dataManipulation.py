import pandas as pd 
from tqdm import tqdm  


def fetch_and_prepare_data(exchange, symbol, timeframe, start_date=None, end_date=None, limit=2000):
    if start_date is None and end_date is None:
        ohlcv_data = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    else:
        data = []
        start_ts = exchange.parse8601(start_date) if start_date else None
        end_ts = exchange.parse8601(end_date) if end_date else exchange.milliseconds()

        if start_ts is None:
            start_ts = end_ts - (limit * exchange.parse_timeframe(timeframe) * 1000)

        total_iterations = (end_ts - start_ts) / (limit * exchange.parse_timeframe(timeframe) * 1000)
        
        pbar = tqdm(total=total_iterations,
            desc='Fetching Data',
            ascii=False,
            ncols=100, 
            bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]',
            colour='green')  

        while start_ts < end_ts:
            chunk = exchange.fetch_ohlcv(symbol, timeframe, since=start_ts, limit=limit)
            if not chunk:
                break
            start_ts = chunk[-1][0] + exchange.parse_timeframe(timeframe) * 1000  # Increment start_ts to fetch the next chunk
            data += chunk
            pbar.update(1) 
        pbar.close()
        ohlcv_data = data  

    keys = ['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']
    ohlcv_dicts = [dict(zip(keys, item)) for item in ohlcv_data]
    df = pd.DataFrame(ohlcv_dicts)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    first_candle_date = df.index.min()
    last_candle_date = df.index.max()
    print(f'Backtest data: {exchange}-{symbol}-{timeframe}: {first_candle_date} - {last_candle_date}')
    print(f'Count of OHLCV rows: {len(df.index)}')
    return df

