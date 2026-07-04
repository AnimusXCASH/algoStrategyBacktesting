import numpy as np 
import matplotlib.pyplot as plt
import pandas as pd
from utils.dataManipulation import fetch_and_prepare_data
from scipy.signal import argrelextrema
import ccxt
from collections import deque
from matplotlib.lines import Line2D
from datetime import timedelta
import matplotlib.pyplot as plt

# https://www.youtube.com/watch?v=wzYL-L0Z6ZU

# Initialize the exchange
exchange = ccxt.bybit({
    'options': {
        'defaultType': 'future',  # Correct type for futures trading
        'defaultSubType': 'linear'  # Bybit USDT perpetual futures are linear contracts
    },
    'rateLimit': 1200,
    'enableRateLimit': True,
})


def calculus(df):
  df['ret'] = df.Close.pct_change()
  df=df.dropna()

  # 10 % lowest returns in this return series - threshold for lowest 10 %
  low_thresh = np.percentile(df.ret, 10)
  high_thresh = np.percentile(df.ret, 90) 

  df['signal'] = np.where(df.ret <= low_thresh, 1, np.where(df.ret >= high_thresh, -1, 0))
  df['next_d_ret'] = df.ret.shift(-1)
  low_ret_grp = df[df.signal == 1]['next_d_ret']
  low_ret_mean = low_ret_grp.mean()
  high_ret_grp = df[df.signal == -1]['next_d_ret']
  high_ret_mean = high_ret_grp.mean()

  (low_ret_grp + 1).cumprod().plot(label=f'low_ret @ {low_ret_mean}', legend=True)
  (high_ret_grp + 1).cumprod().plot(label=f'high_ret @ {high_ret_mean}', legend=True)

  # Add this to display the plot
  plt.show()
  return df



if __name__ == "__main__":
  symbol = "BTC/USDT:USDT"
  start_date = "2022-08-22T00:00:00Z"
  data = fetch_and_prepare_data(exchange, symbol, '1d', start_date=start_date, end_date=None)    
  df = calculus(data)
  print(df)
