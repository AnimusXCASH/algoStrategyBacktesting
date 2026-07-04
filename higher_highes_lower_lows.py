import numpy as np 
import matplotlib.pyplot as plt
import pandas as pd
from utils.dataManipulation import fetch_and_prepare_data
from scipy.signal import argrelextrema
import ccxt
from collections import deque
from matplotlib.lines import Line2D
from datetime import timedelta

# Initialize the exchange
exchange = ccxt.bybit({
    'options': {
        'defaultType': 'future',  # Correct type for futures trading
        'defaultSubType': 'linear'  # Bybit USDT perpetual futures are linear contracts
    },
    'rateLimit': 1200,
    'enableRateLimit': True,
})

def draw_chart(data):
    close = data['Close'].values
    dates = data.index
    colors = plt.rcParams['axes.prop_cycle'].by_key()['color']

    order = 5
    K = 2

    hh = get_higher_highs(close, order, K)
    hl = get_higher_lows(close, order, K)
    ll = get_lower_lows(close, order, K)
    lh = get_lower_highs(close, order, K)

    plt.figure(figsize=(15, 8))
    plt.plot(data['Close'])
    _ = [plt.plot(dates[i], close[i], c=colors[1]) for i in hh]
    _ = [plt.plot(dates[i], close[i], c=colors[2]) for i in hl]
    _ = [plt.plot(dates[i], close[i], c=colors[3]) for i in ll]
    _ = [plt.plot(dates[i], close[i], c=colors[4]) for i in lh]

    _ = [plt.scatter(dates[i[-1]], close[i[-1]], 
                     c=colors[1], marker='^', s=100) for i in hh]
    _ = [plt.scatter(dates[i[-1]], close[i[-1]], 
                     c=colors[2], marker='^', s=100) for i in hl]
    _ = [plt.scatter(dates[i[-1]], close[i[-1]], 
                     c=colors[3], marker='v', s=100) for i in ll]
    _ = [plt.scatter(dates[i[-1]], close[i[-1]],
                     c=colors[4], marker='v', s=100) for i in lh]

    plt.xlabel('Date')
    plt.ylabel('Price ($)')
    plt.title(f'Potential Divergence Points for Closing Price')
    legend_elements = [
        Line2D([0], [0], color=colors[0], label='Close'),
        Line2D([0], [0], color=colors[1], label='Higher Highs'),
        Line2D([0], [0], color='w',  marker='^',
              markersize=10,
              markerfacecolor=colors[1],
              label='Higher High Confirmation'),
        Line2D([0], [0], color=colors[2], label='Higher Lows'),
        Line2D([0], [0], color='w',  marker='^',
              markersize=10,
              markerfacecolor=colors[2],
              label='Higher Lows Confirmation'),
        Line2D([0], [0], color=colors[3], label='Lower Lows'),
        Line2D([0], [0], color='w',  marker='v',
              markersize=10,
              markerfacecolor=colors[3],
              label='Lower Lows Confirmation'),
        Line2D([0], [0], color=colors[4], label='Lower Highs'),
        Line2D([0], [0], color='w',  marker='v',
              markersize=10,
              markerfacecolor=colors[4],
              label='Lower Highs Confirmation')
    ]
    plt.legend(handles=legend_elements)
    plt.show()


def calc_local_max_min(data):
  data['local_max'] = data['Close'][(data['Close'].shift(1) < data['Close']) & (data['Close'].shift(-1) < data['Close'])]
  data['local_min'] = data['Close'][(data['Close'].shift(1) > data['Close']) & (data['Close'].shift(-1) > data['Close'])]
  return data


def get_higher_lows(data:np.array, order=5, K=2):
  """
  Finds consecutive higher lows in price pattern.
  Must not be exceeded within the number of periods indicated by the width 
  parameter for the value to be confirmed.
  K determines how many consecutive lows need to be higher.
  
  """

  low_idx = argrelextrema(data, np.less, order=order)[0]
  lows = data[low_idx]
    # Ensure consecutive lows are higher than previous lows
  extrema = []
  ex_deque = deque(maxlen=K)
  for i, idx in enumerate(low_idx):
    if i == 0:
      ex_deque.append(idx)
      continue
    if lows[i] < lows[i-1]:
      ex_deque.clear()

    ex_deque.append(idx)
    if len(ex_deque) == K:
      extrema.append(ex_deque.copy())

  return extrema

def get_lower_highs(data: np.array, order=5, K=2):

  '''
  Finds consecutive lower highs in price pattern.
  Must not be exceeded within the number of periods indicated by the width 
  parameter for the value to be confirmed.
  K determines how many consecutive highs need to be lower.
  '''
  # Get highs
  high_idx = argrelextrema(data, np.greater, order=order)[0]
  highs = data[high_idx]
  # Ensure consecutive highs are lower than previous highs
  extrema = []
  ex_deque = deque(maxlen=K)
  for i, idx in enumerate(high_idx):
    if i == 0:
      ex_deque.append(idx)
      continue
    if highs[i] > highs[i-1]:
      ex_deque.clear()

    ex_deque.append(idx)
    if len(ex_deque) == K:
      extrema.append(ex_deque.copy())

  return extrema

def get_higher_highs(data: np.array, order=5, K=2):
  '''
  Finds consecutive higher highs in price pattern.
  Must not be exceeded within the number of periods indicated by the width 
  parameter for the value to be confirmed.
  K determines how many consecutive highs need to be higher.
  '''
  # Get highs
  high_idx = argrelextrema(data, np.greater, order=5)[0]
  highs = data[high_idx]
  # Ensure consecutive highs are higher than previous highs
  extrema = []
  ex_deque = deque(maxlen=K)
  for i, idx in enumerate(high_idx):
    if i == 0:
      ex_deque.append(idx)
      continue
    if highs[i] < highs[i-1]:
      ex_deque.clear()

    ex_deque.append(idx)
    if len(ex_deque) == K:
      extrema.append(ex_deque.copy())

  return extrema

def get_lower_lows(data: np.array, order=5, K=2):
  '''
  Finds consecutive lower lows in price pattern.
  Must not be exceeded within the number of periods indicated by the width 
  parameter for the value to be confirmed.
  K determines how many consecutive lows need to be lower.
  '''
  # Get lows
  low_idx = argrelextrema(data, np.less, order=order)[0]
  lows = data[low_idx]
  # Ensure consecutive lows are lower than previous lows
  extrema = []
  ex_deque = deque(maxlen=K)
  for i, idx in enumerate(low_idx):
    if i == 0:
      ex_deque.append(idx)
      continue
    if lows[i] > lows[i-1]:
      ex_deque.clear()

    ex_deque.append(idx)
    if len(ex_deque) == K:
      extrema.append(ex_deque.copy())

  return extrema

if __name__ == "__main__":
  symbol = "ADA/USDT"
  start_date = "2024-06-22T00:00:00Z"
  data = fetch_and_prepare_data(exchange, symbol, '5m', start_date=start_date, end_date=None)    
  data = calc_local_max_min(data)
  draw_chart(data)
  print(data)

  # https://raposa.trade/blog/higher-highs-lower-lows-and-calculating-price-trends-in-python/