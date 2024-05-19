import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from utils.dataManipulation import fetch_and_prepare_data
import ccxt

exchange = ccxt.binance({
    'options': {'defaultType': 'swap',
                'defaultContractType': 'perpetual'},
    'rateLimit': 1200,
    'enableRateLimit': True,
})


def ema(series, length):
    return series.ewm(span=length, adjust=False).mean()

def rma(series, length):
    alpha = 1 / length
    return series.ewm(alpha=alpha, adjust=False).mean()

def rsi(df, length, source_column):
    delta = df[source_column].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = rma(gain, length)
    avg_loss = rma(loss, length)
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# def detect_divergence(df, source_column):
#     df['Bearish Divergence'] = False
#     df['Bullish Divergence'] = False

#     for i in range(2, len(df)):
#         # Bearish divergence
#         if df['RSI'][i-2] < df['RSI'][i] and df[source_column][i-2] > df[source_column][i]:
#             df.at[df.index[i], 'Bearish Divergence'] = True

#         # Bullish divergence
#         if df['RSI'][i-2] > df['RSI'][i] and df[source_column][i-2] < df[source_column][i]:
#             df.at[df.index[i], 'Bullish Divergence'] = True

#     return df
# def detect_divergence(df, source_column):
#     df['Bearish Divergence'] = False
#     df['Bullish Divergence'] = False

#     for i in range(2, len(df)):
#         # Bearish divergence
#         if df['RSI'][i-2] < df['RSI'][i] and df[source_column][i-2] > df[source_column][i]:
#             df.at[df.index[i], 'Bearish Divergence'] = True

#         # Bullish divergence
#         if df['RSI'][i-2] > df['RSI'][i] and df[source_column][i-2] < df[source_column][i]:
#             df.at[df.index[i], 'Bullish Divergence'] = True

#     return df


def detect_divergence(df, source_column):
    df['Bearish Divergence'] = False
    df['Bullish Divergence'] = False

    for i in range(2, len(df)):
        # Bearish divergence
        if df['RSI'][i-2] < df['RSI'][i] and df[source_column][i-2] > df[source_column][i]:
            df.at[df.index[i], 'Bearish Divergence'] = True

        # Bullish divergence
        if df['RSI'][i-2] > df['RSI'][i] and df[source_column][i-2] < df[source_column][i]:
            df.at[df.index[i], 'Bullish Divergence'] = True

    return df

def detect_shark_fin(df, rsi_column='RSI'):
    df['Shark Fin'] = False
    df['Inverse Shark Fin'] = False
    
    for i in range(2, len(df)):
        # Detecting Shark Fin Pattern
        if df[rsi_column].iloc[i-2] > 70 and df[rsi_column].iloc[i-1] > 70 and df[rsi_column].iloc[i] <= 70:
            df.at[df.index[i], 'Shark Fin'] = True
        
        # Detecting Inverse Shark Fin Pattern
        if df[rsi_column].iloc[i-2] < 30 and df[rsi_column].iloc[i-1] < 30 and df[rsi_column].iloc[i] >= 30:
            df.at[df.index[i], 'Inverse Shark Fin'] = True
            
    return df

def plot_rsi(df, rsi_length, source_column):
    df['RSI'] = rsi(df, rsi_length, source_column)
    df['RSI_EMA'] = ema(df['RSI'], rsi_length)
    df['previous_RSI'] = df['RSI'].shift(1)
    df['previous_RSI_EMA'] = df['RSI_EMA'].shift(1)

    df['flip_color'] = np.where(
        (df['RSI'] > df['RSI_EMA']) & (df['previous_RSI'] <= df['previous_RSI_EMA']),
        'green', np.where(
            (df['RSI'] < df['RSI_EMA']) & (df['previous_RSI'] >= df['previous_RSI_EMA']),
            'red', 'none'
        )
    )

    df = detect_divergence(df, source_column)
    df = detect_shark_fin(df)

    # Debug: Print to verify the Divergence and Shark Fin columns
    print(df[['RSI', 'RSI_EMA', 'Bearish Divergence', 'Bullish Divergence', 'Shark Fin', 'Inverse Shark Fin']])

    df = df.tail(120)
    plt.figure(figsize=(14, 7))
    plt.plot(df.index, df['RSI'], label='RSI', color='blue')
    plt.plot(df.index, df['RSI_EMA'], label='RSI EMA', color='orange')
    
    overbought = 70
    oversold = 30
    extended_overbought = 75
    extended_oversold = 25
    
    plt.fill_between(df.index, overbought, df['RSI'], where=(df['RSI'] >= overbought), color='green', alpha=0.3, label='Overbought')
    plt.fill_between(df.index, oversold, df['RSI'], where=(df['RSI'] <= oversold), color='red', alpha=0.3, label='Oversold')
    plt.fill_between(df.index, extended_overbought, df['RSI'], where=(df['RSI'] >= extended_overbought), color='darkgreen', alpha=0.3, label='Extended Overbought')
    plt.fill_between(df.index, extended_oversold, df['RSI'], where=(df['RSI'] <= extended_oversold), color='darkred', alpha=0.3, label='Extended Oversold')

    current_color = None
    start_index = 0

    for i in range(1, len(df)):
        if df['flip_color'].iloc[i] == 'green' and current_color != 'green':
            if current_color == 'red':
                plt.fill_between(df.index[start_index:i], df['RSI'].iloc[start_index:i], df['RSI_EMA'].iloc[start_index:i], color='red', alpha=0.3)
            start_index = i
            current_color = 'green'
        elif df['flip_color'].iloc[i] == 'red' and current_color != 'red':
            if current_color == 'green':
                plt.fill_between(df.index[start_index:i], df['RSI'].iloc[start_index:i], df['RSI_EMA'].iloc[start_index:i], color='green', alpha=0.3)
            start_index = i
            current_color = 'red'

    if current_color == 'green':
        plt.fill_between(df.index[start_index:], df['RSI'].iloc[start_index:], df['RSI_EMA'].iloc[start_index:], color='green', alpha=0.3)
    elif current_color == 'red':
        plt.fill_between(df.index[start_index:], df['RSI'].iloc[start_index:], df['RSI_EMA'].iloc[start_index:], color='red', alpha=0.3)

    # Plot divergence signals
    bullish_divergence = df[df['Bullish Divergence']]
    bearish_divergence = df[df['Bearish Divergence']]
    shark_fin = df[df['Shark Fin']]
    inverse_shark_fin = df[df['Inverse Shark Fin']]

    # Added debug prints to check the presence of divergence points
    print(f"Bullish Divergence points: {bullish_divergence.index}")
    print(f"Bearish Divergence points: {bearish_divergence.index}")
    print(f"Shark Fin points: {shark_fin.index}")
    print(f"Inverse Shark Fin points: {inverse_shark_fin.index}")

    plt.scatter(bullish_divergence.index, bullish_divergence['RSI'] - 20, marker='^', color='lime', label='Bullish Divergence', alpha=1)
    plt.scatter(bearish_divergence.index, bearish_divergence['RSI'] + 20, marker='v', color='magenta', label='Bearish Divergence', alpha=1)  # Adjusted position
    plt.scatter(shark_fin.index, shark_fin['RSI'] + 10, marker='s', color='blue', label='Shark Fin', alpha=1)
    plt.scatter(inverse_shark_fin.index, inverse_shark_fin['RSI'] - 10, marker='d', color='cyan', label='Inverse Shark Fin', alpha=1)

    plt.axhline(50, linestyle='--', linewidth=1, color='grey', label='Baseline')
    plt.axhline(overbought, linestyle='--', linewidth=1, color='green')
    plt.axhline(oversold, linestyle='--', linewidth=1, color='red')
    plt.axhline(extended_overbought, linestyle='--', linewidth=1, color='darkgreen')
    plt.axhline(extended_oversold, linestyle='--', linewidth=1, color='darkred')
    
    plt.title('RSI and RSI EMA with Cloud Flip')
    plt.legend()
    plt.show()

# Load data and plot
symbol = "BTC/USDT"
timeframe = '4h'
start_date = '2024-01-05T00:00:00Z'  # None Or  '2023-01-01T00:00:00Z'  for start
end_date = None     # None Or  '2023-01-01T00:00:00Z'  for end

df = fetch_and_prepare_data(exchange, symbol, timeframe, start_date=start_date, end_date=end_date)

plot_rsi(df, rsi_length=14, source_column='Close')
