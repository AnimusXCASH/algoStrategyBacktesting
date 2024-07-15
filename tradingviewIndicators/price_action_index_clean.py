import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import ccxt
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.dataManipulation import fetch_and_prepare_data

import plotly.graph_objects as go
from plotly.subplots import make_subplots

pd.set_option('display.max_rows', 500)

# Colors
bearColor = (1.0, 0.0, 0.0, 1.0)  # red
bullColor = (0.0, 1.0, 0.0, 1.0)  # green
hiddenBullColor = (0.0, 0.5, 0.0, 0.8)  # dark green with 80% transparency
hiddenBearColor = (1.0, 0.0, 0.0, 0.8)  # red with 80% transparency
textColor = (1.0, 1.0, 1.0, 1.0)  # white
noneColor = (1.0, 1.0, 1.0, 0.0)  # fully transparent white

# Initialize the exchange
# exchange = ccxt.binance(
#     {
#         "options": {"defaultType": "swap", "defaultContractType": "perpetual"},
#         "rateLimit": 1200,
#         "enableRateLimit": True,
#     }
# )

exchange = ccxt.bybit({
    'options': {
        'defaultType': 'future',  
        'defaultSubType': 'linear' 
    },
    'rateLimit': 1200,
    'enableRateLimit': True,
})




# Utility functions
def crossover(series, threshold):
    return (series.shift(1) < threshold) & (series > threshold)

def crossunder(series, threshold):
    return (series.shift(1) > threshold) & (series < threshold)

def highest(source, length):
    return source.rolling(window=length).max()

def lowest(source, length):
    return source.rolling(window=length).min()

def pine_sma(src, length):
    return src.rolling(window=length).mean()

def stoch(close, high, low, length):
    highest_high = highest(high, length)
    lowest_low = lowest(low, length)
    stoch_k = 100 * (close - lowest_low) / (highest_high - lowest_low)
    return stoch_k

def pine_stdev(src, length):
    return src.rolling(window=length).std()

def pine_variance(src, length):
    return src.rolling(window=length).var()



# Dispersion methods
def f_dis0(src, length):
    return pine_stdev(src, length)

def f_dis1(src, length):
    return pine_variance(src, length)

def f_dis2(src, length):
    return pine_stdev(src, length) / pine_sma(src, length)

def f_dis3(src, length):
    return pine_sma(src, length) / pine_stdev(src, length)

def f_dis4(src, length):
    return (pine_sma(src, length) ** 2) / (pine_stdev(src, length) ** 2)

def f_dis5(src, length):
    return (pine_variance(src, length) ** 2) / pine_sma(src, length)

def f_dis6(src, length):
    return (pine_stdev(src, length) ** 2) / (pine_sma(src, length) ** 2)

def f_dis7(high, low, length):
    return highest(high, length) - lowest(low, length)


dispersion_methods = {
    'dis0': f_dis0,
    'dis1': f_dis1,
    'dis2': f_dis2,
    'dis3': f_dis3,
    'dis4': f_dis4,
    'dis5': f_dis5,
    'dis6': f_dis6,
    'dis7': f_dis7
}


def pai(df, src_col, dis_method, dis_len, length, smooth):
    dispersion_func = dispersion_methods[dis_method]
    if dis_method == 'dis7':
        _disp = dispersion_func(df['High'], df['Low'], dis_len)
    else:
        _disp = dispersion_func(df[src_col], dis_len)

    stoch_val = stoch(df['Close'], df['High'], df['Low'], length)
    P = (pine_sma(stoch_val, smooth) - 50) / 50
    V = stoch(_disp, _disp, _disp, length)
    return P * V

# def apply_color_conditions(df, straddle_area):
#     conditions = [
#         (df['PAI'] < straddle_area) & (df['PAI'] > -straddle_area),
#         (df['PAI'] > straddle_area),
#         (df['PAI'] < -straddle_area)
#     ]
#     choices = ['fuchsia', 'lime', 'red']
#     df['Color'] = np.select(conditions, choices, default='black')
#     return df

def pivotlow(osc, lbL, lbR):
    pivots = []
    for i in range(lbL, len(osc) - lbR):
        if all(osc.iloc[i] < osc.iloc[i - j] for j in range(1, lbL + 1)) and all(osc.iloc[i] < osc.iloc[i + j] for j in range(1, lbR + 1)):
            pivots.append(osc.iloc[i])
        else:
            pivots.append(np.nan)
    pivots = [np.nan] * lbL + pivots + [np.nan] * lbR
    return pd.Series(pivots, index=osc.index)

def pivothigh(osc, lbL, lbR):
    pivots = []
    for i in range(lbL, len(osc) - lbR):
        if all(osc.iloc[i] > osc.iloc[i - j] for j in range(1, lbL + 1)) and all(osc.iloc[i] > osc.iloc[i + j] for j in range(1, lbR + 1)):
            pivots.append(osc.iloc[i])
        else:
            pivots.append(np.nan)
    pivots = [np.nan] * lbL + pivots + [np.nan] * lbR
    return pd.Series(pivots, index=osc.index)

def barssince(cond):
    cond_idx = np.where(cond[::-1])[0]
    return cond_idx[0] if cond_idx.size > 0 else len(cond)

def _inRange(cond, rangeLower, rangeUpper):
    bars = barssince(cond)
    return rangeLower <= bars <= rangeUpper

def in_range_series(series, rangeLower, rangeUpper):
    return series.rolling(window=rangeUpper).apply(lambda x: _inRange(x, rangeLower, rangeUpper), raw=True)



def calculate_additional_stuff(df):
    lbR = 2  # Pivot Lookback Right
    lbL = 2  # Pivot Lookback Left
    rangeUpper = 10  # Max of Lookback Range
    rangeLower = 2  # Min f Loookback Range
    plotBull = True  # Plot Bullish
    plotHiddenBull = False  # Plot Hidden Bullish
    plotBear = True  # Plot Bearish
    plotHiddenBear = False  # Plot Hidden Bearish
    df['pivot_low'] = pivotlow(df['PAI'], lbL, lbR)
    df['pivot_high'] = pivothigh(df['PAI'], lbL, lbR)

    df['plFound'] = ~df['pivot_low'].isna()
    df['phFound'] = ~df['pivot_high'].isna()

    df['oscHL'] = (df['PAI'].shift(lbR) > df['PAI'].shift(lbR).where(df['plFound'], other=np.nan).shift(1)) & in_range_series(df['plFound'].shift(1), rangeLower, rangeUpper)

    df['priceLL'] = df.apply(lambda row: row['Low'] < df['Low'].shift(lbR).iloc[df.index.get_loc(row.name)] if df.index.get_loc(row.name) > lbR else False, axis=1) & df['plFound']
    df['bullCond'] = plotBull & df['priceLL'] & df['oscHL'] & df['plFound']

    df['oscLL'] = (df['PAI'].shift(lbR) < df['PAI'].shift(lbR).where(df['plFound'], other=np.nan).shift(1)) & in_range_series(df['plFound'].shift(1), rangeLower, rangeUpper)
    df['priceHL'] = df.apply(lambda row: row['Low'] > df['Low'].shift(lbR).iloc[df.index.get_loc(row.name)] if df.index.get_loc(row.name) > lbR else False, axis=1) & df['plFound']
    df['hiddenBullCond'] = plotHiddenBull & df['priceHL'] & df['oscLL'] & df['plFound']

    df['oscLH'] = (df['PAI'].shift(lbR) < df['PAI'].shift(lbR).where(df['phFound'], other=np.nan).shift(1)) & in_range_series(df['phFound'].shift(1), rangeLower, rangeUpper)
    df['priceHH'] = df.apply(lambda row: row['High'] > df['High'].shift(lbR).iloc[df.index.get_loc(row.name)] if df.index.get_loc(row.name) > lbR else False, axis=1) & df['phFound']
    df['bearCond'] = plotBear & df['priceHH'] & df['oscLH'] & df['phFound']

    df['oscHH'] = (df['PAI'].shift(lbR) > df['PAI'].shift(lbR).where(df['phFound'], other=np.nan).shift(1)) & in_range_series(df['phFound'].shift(1), rangeLower, rangeUpper)
    df['priceLH'] = df.apply(lambda row: row['High'] < df['High'].shift(lbR).iloc[df.index.get_loc(row.name)] if df.index.get_loc(row.name) > lbR else False, axis=1) & df['phFound']
    df['hiddenBearCond'] = plotHiddenBear & df['priceLH'] & df['oscHH'] & df['phFound']
    return df



def plot_pai(df, straddle_area, overbought_area=(80, 100), oversold_area=(-80, -100)):


    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True, gridspec_kw={'height_ratios': [2, 1]})

    # Plot the PAI 
    for i in range(1, len(df)):
        ax1.plot(df.index[i-1:i+1], df['PAI'].iloc[i-1:i+1], color='black')

    # Plot horizontal lines for straddle area
    ax1.axhline(y=straddle_area, color='fuchsia', linestyle='--', linewidth=1)
    ax1.axhline(y=-straddle_area, color='fuchsia', linestyle='--', linewidth=1)
    ax1.fill_between(df.index, straddle_area, -straddle_area, where=(df['PAI'] < straddle_area) & (df['PAI'] > -straddle_area), color='fuchsia', alpha=0.3)

    # Plot overbought area
    p_ob1, p_ob2 = overbought_area
    ax1.axhline(y=p_ob1, color='gray', linestyle='--', linewidth=1)
    ax1.axhline(y=p_ob2, color='gray', linestyle='--', linewidth=1)
    ax1.fill_between(df.index, p_ob1, p_ob2, where=df['PAI'] > p_ob1, color='red', alpha=0.3)

    # Plot oversold area
    p_os1, p_os2 = oversold_area
    ax1.axhline(y=p_os1, color='gray', linestyle='--', linewidth=1)
    ax1.axhline(y=p_os2, color='gray', linestyle='--', linewidth=1)
    ax1.fill_between(df.index, p_os1, p_os2, where=(df['PAI'] < p_os1), color='lime', alpha=0.3)

    # Plot pivot lows
    ax1.scatter(df.index, df['pivot_low'], marker='v', color='blue', label='Pivot Low')

    # Plot pivot highs
    ax1.scatter(df.index, df['pivot_high'], marker='^', color='orange', label='Pivot High')

    # Plot bullish conditions
    bullish_indices = df[df['bullCond']].index
    ax1.scatter(bullish_indices, df['PAI'][bullish_indices], marker='o', color=bullColor, s=100, edgecolor='black', label='Bullish Condition')

    # Add alerts as annotations or markers
    for i in df.index:
        if df['cond_bear_bottom'].loc[i]:
            ax1.annotate('Buy Signal', (i, df['PAI'].loc[i]), textcoords="offset points", xytext=(0,-10), ha='center', color='blue', arrowprops=dict(arrowstyle="->", color='green'))

        if df['cond_bull_top'].loc[i]:
            ax1.annotate('Sell Signal', (i, df['PAI'].loc[i]), textcoords="offset points", xytext=(0,10), ha='center', color='blue', arrowprops=dict(arrowstyle="->", color='red'))

    ax1.set_title('Price Action Index')
    ax1.set_ylabel('PAI')
    ax1.legend()

    # Plot close line on ax2
    ax2.plot(df.index, df['Close'], color='blue', label='Close')
    ax2.set_ylabel('Close')
    ax2.legend(loc='upper right')

    plt.xlabel('Time')
    plt.show()




def calculate_price_action_index_data(df: pd.DataFrame, src: 'str' = "Close", dispersion_method: str= "dis0", dispersion_length:int = 20, length:int = 20, smooth:int = 3, straddle_area:float = 5.0 ):
    if dispersion_method not in dispersion_methods:
        raise ValueError(f"Invalid dispersion method: {dispersion_method}. Allowed methods are: {', '.join(dispersion_methods.keys())}")
    
    # get the Price action index
    df['PAI'] = pai(df, src_col = src, dis_method=dispersion_method, dis_len=dispersion_length, length=length, smooth=smooth)
    return df 
    # # df = apply_color_conditions(df, straddle_area) 
    # df = calculate_additional_stuff(df)
    # # df['cond_bull_top'] = crossunder(df['PAI'], 80)
    # # df['cond_bear_bottom'] = crossover(df['PAI'], -60)
   



