import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import sys
import plotly.graph_objects as go
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


from utils.dataManipulation import fetch_and_prepare_data

import ccxt

exchange = ccxt.binance({
    'options': {'defaultType': 'swap',
                'defaultContractType': 'perpetual'},
    'rateLimit': 1200,
    'enableRateLimit': True,
})


def rma(series, length):
    alpha = 1 / length
    return series.ewm(alpha=alpha, adjust=False).mean()



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


def rsi(df, length, source_column):
    delta = df[source_column].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = rma(gain, length)
    avg_loss = rma(loss, length)
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def ema(series, length):
    return series.ewm(span=length, adjust=False).mean()

def calculate_inevitrade_pro_indicator(df, rsi_length, source_column):

    df['RSI'] = rsi(df, rsi_length, source_column)
    df['RSI_EMA'] = ema(df['RSI'], rsi_length)
    df['previous_RSI'] = df['RSI'].shift(1)
    df['previous_RSI_EMA'] = df['RSI_EMA'].shift(1)

    return df


def ema(series, length):
    return series.ewm(span=length, adjust=False).mean()
    
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

def plot_inevitrade_pro_indicator(df, source_column):
    df['flip_color'] = np.where(
        (df['RSI'] > df['RSI_EMA']) & (df['previous_RSI'] <= df['previous_RSI_EMA']),
        'green', np.where(
            (df['RSI'] < df['RSI_EMA']) & (df['previous_RSI'] >= df['previous_RSI_EMA']),
            'red', 'none'
        )
    )

    df = detect_divergence(df, source_column)
    df = detect_shark_fin(df)

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


def plotly_inevi(df, source_column):
    df['flip_color'] = np.where(
        (df['RSI'] > df['RSI_EMA']) & (df['previous_RSI'] <= df['previous_RSI_EMA']),
        'green', np.where(
            (df['RSI'] < df['RSI_EMA']) & (df['previous_RSI'] >= df['previous_RSI_EMA']),
            'red', 'none'
        )
    )

    df = detect_divergence(df, source_column)
    df = detect_shark_fin(df)

    fig = go.Figure()

    # Plot RSI
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], mode='lines', name='RSI', line=dict(color='blue')))
    
    # Plot RSI EMA
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI_EMA'], mode='lines', name='RSI EMA', line=dict(color='orange')))
    
    overbought = 70
    oversold = 30
    extended_overbought = 75
    extended_oversold = 25

    # Fill overbought and oversold areas
    fig.add_trace(go.Scatter(x=df.index, y=[overbought] * len(df), fill=None, mode='lines', line=dict(color='green', width=0)))
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], fill='tonexty', mode='lines', line=dict(color='green', width=0), name='Overbought', opacity=0.3, fillcolor='rgba(0,255,0,0.3)'))
    
    fig.add_trace(go.Scatter(x=df.index, y=[oversold] * len(df), fill=None, mode='lines', line=dict(color='red', width=0)))
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], fill='tonexty', mode='lines', line=dict(color='red', width=0), name='Oversold', opacity=0.3, fillcolor='rgba(255,0,0,0.3)'))
    
    fig.add_trace(go.Scatter(x=df.index, y=[extended_overbought] * len(df), fill=None, mode='lines', line=dict(color='darkgreen', width=0)))
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], fill='tonexty', mode='lines', line=dict(color='darkgreen', width=0), name='Extended Overbought', opacity=0.3, fillcolor='rgba(0,100,0,0.3)'))
    
    fig.add_trace(go.Scatter(x=df.index, y=[extended_oversold] * len(df), fill=None, mode='lines', line=dict(color='darkred', width=0)))
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], fill='tonexty', mode='lines', line=dict(color='darkred', width=0), name='Extended Oversold', opacity=0.3, fillcolor='rgba(139,0,0,0.3)'))

    # Plot flip areas
    current_color = None
    start_index = 0

    for i in range(1, len(df)):
        if df['flip_color'].iloc[i] == 'green' and current_color != 'green':
            if current_color == 'red':
                fig.add_trace(go.Scatter(x=df.index[start_index:i], y=df['RSI'].iloc[start_index:i], fill='tonexty', mode='lines', line=dict(color='red', width=0), opacity=0.3, fillcolor='rgba(255,0,0,0.3)'))
            start_index = i
            current_color = 'green'
        elif df['flip_color'].iloc[i] == 'red' and current_color != 'red':
            if current_color == 'green':
                fig.add_trace(go.Scatter(x=df.index[start_index:i], y=df['RSI'].iloc[start_index:i], fill='tonexty', mode='lines', line=dict(color='green', width=0), opacity=0.3, fillcolor='rgba(0,255,0,0.3)'))
            start_index = i
            current_color = 'red'

    if current_color == 'green':
        fig.add_trace(go.Scatter(x=df.index[start_index:], y=df['RSI'].iloc[start_index:], fill='tonexty', mode='lines', line=dict(color='green', width=0), opacity=0.3, fillcolor='rgba(0,255,0,0.3)'))
    elif current_color == 'red':
        fig.add_trace(go.Scatter(x=df.index[start_index:], y=df['RSI'].iloc[start_index:], fill='tonexty', mode='lines', line=dict(color='red', width=0), opacity=0.3, fillcolor='rgba(255,0,0,0.3)'))

    # Plot divergence signals
    bullish_divergence = df[df['Bullish Divergence']]
    bearish_divergence = df[df['Bearish Divergence']]
    shark_fin = df[df['Shark Fin']]
    inverse_shark_fin = df[df['Inverse Shark Fin']]

    fig.add_trace(go.Scatter(x=bullish_divergence.index, y=bullish_divergence['RSI'] - 20, mode='markers', marker=dict(symbol='triangle-up', color='lime'), name='Bullish Divergence'))
    fig.add_trace(go.Scatter(x=bearish_divergence.index, y=bearish_divergence['RSI'] + 20, mode='markers', marker=dict(symbol='triangle-down', color='magenta'), name='Bearish Divergence'))
    fig.add_trace(go.Scatter(x=shark_fin.index, y=shark_fin['RSI'] + 10, mode='markers', marker=dict(symbol='square', color='blue'), name='Shark Fin'))
    fig.add_trace(go.Scatter(x=inverse_shark_fin.index, y=inverse_shark_fin['RSI'] - 10, mode='markers', marker=dict(symbol='diamond', color='cyan'), name='Inverse Shark Fin'))

    # Add horizontal lines
    fig.add_hline(y=50, line=dict(dash='dash', color='grey'), name='Baseline')
    fig.add_hline(y=overbought, line=dict(dash='dash', color='green'))
    fig.add_hline(y=oversold, line=dict(dash='dash', color='red'))
    fig.add_hline(y=extended_overbought, line=dict(dash='dash', color='darkgreen'))
    fig.add_hline(y=extended_oversold, line=dict(dash='dash', color='darkred'))

    fig.update_layout(
        title='RSI and RSI EMA with Cloud Flip',
        legend=dict(orientation='h', x=0, y=1.1),
        xaxis_title='Date',
        yaxis_title='RSI'
    )

    fig.show()


# # Load data and plot
# symbol = "BTC/USDT"
# timeframe = '15m'
# start_date = '2024-01-05T00:00:00Z'  # None Or  '2023-01-01T00:00:00Z'  for start
# end_date = None     # None Or  '2023-01-01T00:00:00Z'  for end

# df = fetch_and_prepare_data(exchange, symbol, timeframe, start_date=start_date, end_date=end_date)
# df = calculate_inevitrade_pro_indicator(df,rsi_length=14, source_column="Close")
# # calculate_inevitrade_pro_indicator(df.tail(100), rsi_length=14, source_column='Close')
# plot_inevitrade_pro_indicator(df.tail(60), 'Close')
# plotly_inevi(df.tail(60), 'Close')
