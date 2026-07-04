import asyncio
import json
import pandas as pd
import numpy as np
import websockets
import aiohttp

# Get top 50 coins by market cap from Binance
async def get_top_50_symbols():
    url = "https://api.binance.com/api/v3/ticker/24hr"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            sorted_data = sorted(data, key=lambda x: float(x['quoteVolume']), reverse=True)
                
            top_50 = sorted_data[:50]
            return [item['symbol'].lower() for item in top_50 if item['symbol'].endswith('USDT')]

# Function to create a WebSocket URL for a symbol and interval
def create_ws_url(symbol, interval):
    return f'wss://stream.binance.com:9443/ws/{symbol}@kline_{interval}'

# Initialize an empty dictionary to store DataFrames for each symbol
df_dict = {}

async def check_fair_value_gap(symbol, interval):
    ws_url = create_ws_url(symbol, interval)
    async with websockets.connect(ws_url) as websocket:
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            kline = data['k']
            is_candle_closed = kline['x']
            timestamp = kline['t']
            open_price = float(kline['o'])
            high_price = float(kline['h'])
            low_price = float(kline['l'])
            close_price = float(kline['c'])
            volume = float(kline['v'])

            if is_candle_closed:
                new_row = {
                    'timestamp': timestamp,
                    'open': open_price,
                    'high': high_price,
                    'low': low_price,
                    'close': close_price,
                    'volume': volume
                }
                
                if symbol not in df_dict:
                    df_dict[symbol] = pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                
                df_dict[symbol].loc[len(df_dict[symbol])] = new_row

                if len(df_dict[symbol]) > 3:
                    # Check for a fair value gap
                    previous_candle = df_dict[symbol].iloc[-3]
                    current_candle = df_dict[symbol].iloc[-1]
                    if previous_candle['high'] < current_candle['low']:
                        human_readable_time = pd.to_datetime(current_candle['timestamp'], unit='ms').strftime('%Y-%m-%d %H:%M:%S')
                        print(f"Fair Value Gap detected for {symbol.upper()} at {human_readable_time} UTC")
                    else:
                        print("No FVG found")
async def main():
    interval = '1m'  # The timeframe
    top_50_symbols = await get_top_50_symbols()
    print(top_50_symbols)
    tasks = []
    for symbol in top_50_symbols:
        print(f'creating socket for {symbol}')
        task = asyncio.create_task(check_fair_value_gap(symbol, interval))
        tasks.append(task)
    
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
