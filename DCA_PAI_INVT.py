import pandas as pd
import numpy as np
import os
import sys
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from tradingviewIndicators.inevitrade_pro import calculate_inevitrade_pro_indicator, plot_inevitrade_pro_indicator
from tradingviewIndicators.price_action_index_clean import calculate_price_action_index_data
pd.set_option('display.max_columns', None)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.dataManipulation import fetch_and_prepare_data

import ccxt

# exchange = ccxt.binance({
#     'options': {'defaultType': 'swap',
#                 'defaultContractType': 'perpetual'},
#     'rateLimit': 1200,
#     'enableRateLimit': True,
# })


exchange = ccxt.bybit({
    'options': {
        'defaultType': 'future',  # Correct type for futures trading
        'defaultSubType': 'linear'  # Bybit USDT perpetual futures are linear contracts
    },
    'rateLimit': 1200,
    'enableRateLimit': True,
})


def calculate_ema_pine(df, column, length):
    alpha = 2 / (length + 1)
    close_prices = df[column].values
    ema = np.zeros_like(close_prices)
    ema[0] = close_prices[0]
    for i in range(1, len(close_prices)):
        ema[i] = alpha * close_prices[i] + (1 - alpha) * ema[i - 1]
    return ema

def add_multiple_emas(df, column:str = 'Close', lengths: list = [20,50,200]):
    for length in lengths:
        ema_column_name = f'EMA_{length}'
        df[ema_column_name] = calculate_ema_pine(df, column, length)
    return df


def plot_indicators(df, pai_overbought=(80, 100), pai_oversold=(-80, -100), pai_straddle=(5, -5), inevi_overbought = (70,80), inevi_oversold=(30,25), emas=[20,50,200]):

    # Create subplots with 2 rows and shared x-axis
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, subplot_titles=('OHLC', 'PAI'),
                        row_width=[0.2, 0.2, 0.2])  

    for ema in emas:
        ema_col = f'EMA_{ema}'
        fig.add_trace(go.Scatter(x=df.index, y=df[ema_col], mode='lines', name=ema_col))



    # Add OHLC trace
    fig.add_trace(go.Candlestick(x=df.index,
                                 open=df['Open'],
                                 high=df['High'],
                                 low=df['Low'],
                                 close=df['Close'],
                                 name='OHLC'), row=1, col=1)

    # Add PAI trace
    fig.add_trace(go.Scatter(x=df.index, y=df['PAI'], mode='lines', name='PAI'), row=2, col=1)

    # Add straddle area as a shaded region for PAI 
    fig.add_shape(type="rect",
                  x0=df.index[0], x1=df.index[-1],
                  y0=pai_straddle[1], y1=pai_straddle[0],
                  line=dict(color="RoyalBlue", width=1),
                  fillcolor="LightSkyBlue", opacity=0.3,
                  row=2, col=1)

    # Add oversold area as a shaded region for PAI
    fig.add_shape(type="rect",
                  x0=df.index[0], x1=df.index[-1],
                  y0=pai_oversold[1], y1=pai_oversold[0],
                  line=dict(color="Green", width=1),
                  fillcolor="LightGreen", opacity=0.3,
                  row=2, col=1)

    # Add overbought area as a shaded region for PAI
    fig.add_shape(type="rect",
                  x0=df.index[0], x1=df.index[-1],
                  y0=pai_overbought[0], y1=pai_overbought[1],
                  line=dict(color="Red", width=1),
                  fillcolor="LightCoral", opacity=0.3,
                  row=2, col=1)
    
    # ADD inevitrade indicator
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], mode='lines', name='RSI', line=dict(color='blue')),row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI_EMA'], mode='lines', name='RSI_EMA', line=dict(color='orange')), row=3, col=1)

    fig.add_shape(type="rect",
                  x0=df.index[0], x1=df.index[-1],
                  y0=inevi_oversold[1], y1=inevi_oversold[0],
                  line=dict(color="Green", width=1),
                  fillcolor="LightGreen", opacity=0.3,
                  row=3, col=1)


    fig.add_shape(type="rect",
                  x0=df.index[0], x1=df.index[-1],
                  y0=inevi_overbought[0], y1=inevi_overbought[1],
                  line=dict(color="Red", width=1),
                  fillcolor="LightCoral", opacity=0.3,
                  row=3, col=1)
    
    # Extract the crossover points for plotting
    crossover_points = df[df['buy']]
    sell_point = df[df['sell']]

    # df.to_csv('buySignals.csv', index=True)

  
    # Add buy marks on all charts 
    fig.add_trace(go.Scatter(x=crossover_points.index, y=crossover_points['Low'], mode='markers', 
                             marker=dict(color='green', size=10, symbol='x'), name='RSI Crossover & PAI < -80'), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=crossover_points.index, y=crossover_points['PAI'], mode='markers', 
                        marker=dict(color='green', size=10, symbol='x'), name='RSI Crossover & PAI < -80'), row=2, col=1)

    fig.add_trace(go.Scatter(x=crossover_points.index, y=crossover_points['RSI'], mode='markers', 
                             marker=dict(color='green', size=10, symbol='x'), name='RSI Crossover & PAI < -80'), row=3, col=1)
    
    # Add sell marks on all charts
    fig.add_trace(go.Scatter(x=sell_point.index, y=sell_point['High'] + 2, mode='markers', 
                        marker=dict(color='purple', size=10, symbol='0'), name='RSI Crossover & PAI < -80'), row=1, col=1)
    
    fig.add_trace(go.Scatter(x=sell_point.index, y=sell_point['PAI'] + 10, mode='markers', 
                        marker=dict(color='purple', size=10, symbol='0'), name='RSI Crossover & PAI < -80'), row=2, col=1)

    fig.add_trace(go.Scatter(x=sell_point.index, y=sell_point['RSI'] + 10, mode='markers', 
                             marker=dict(color='purple', size=10, symbol='0'), name='RSI Crossover & PAI < -80'), row=3, col=1)
    # Update layout


    avg_entry_price_with_breaks = df['avg_entry_price'].replace(0, None)
    fig.add_trace(go.Scatter(x=df.index, y=avg_entry_price_with_breaks, mode='lines', name="AVG Entry price"), row=1, col=1)

    # Replace 0 values with None for line breaks in take_profit_price
    take_profit_price_with_breaks = df['take_profit_price'].replace(0, None)
    fig.add_trace(go.Scatter(x=df.index, y=take_profit_price_with_breaks, mode='lines', name="Take profit"), row=1, col=1)


    fig.update_layout(title='Dashboard',
                      xaxis_title='Time',
                      yaxis_title='Price',
                      xaxis2_title='Time',
                      yaxis2_title='PAI',
                      height=1500,  # Adjusted the height,
                      xaxis_rangeslider_visible=False)

    fig.show()


def backtest_with_signals(df, cond1_active=True, cond2_active=True, cond3_active=True, cond4_active=True,cond5_active=True, take_profit_multiplier=1.05, initial_allocation_pct=0.02, dca_multiplier=1.5):
    df = df.reset_index(drop=True).copy()

    df['buy'] = False
    df['sell'] = False

    initial_cash = 10000.0
    cash = initial_cash
    position = 0.0
    total_contract_value = 0.0
    cooldown_period = 10
    last_buy_signal = -cooldown_period

    inevi_oversold = (30, 35)
    pai_oversold = (-80, -60)
    pai_straddle = (5, -5)

    first_purchase = True
    current_dca_amount = 0.0

    for i in range(1, len(df)):
        if pd.isna(df['PAI'].iloc[i]) or pd.isna(df['RSI'].iloc[i]) or pd.isna(df['RSI_EMA'].iloc[i]):
            continue

        condition_1 = cond1_active and ((df['RSI'].iloc[i-1] < inevi_oversold[1]) & (df['RSI'].iloc[i] >= inevi_oversold[1]) & (df['PAI'].iloc[i] < pai_oversold[0]))
        condition_2 = cond2_active and ((df['PAI'].iloc[i] <= pai_oversold[0]) & (df['PAI'].iloc[i-1] > pai_oversold[0]) & (df['RSI'].iloc[i] < df['RSI_EMA'].iloc[i]))
        condition_3 = cond3_active and ((df['RSI'].iloc[i] < 40) & (df['PAI'].iloc[i] < 0) & (df['RSI'].iloc[i-1] < df['RSI_EMA'].iloc[i-1]) & (df['RSI'].iloc[i] >= df['RSI_EMA'].iloc[i]))
        condition_4 = cond4_active and ((df['RSI'].iloc[i] > df['RSI_EMA'].iloc[i]) & (df['RSI'].iloc[i] > 50) & (df['RSI'].iloc[i] < 70) & (df['RSI_EMA'].iloc[i] > 50) & (df['PAI'].iloc[i-1] <= pai_straddle[0]) & (df['PAI'].iloc[i] > pai_straddle[0]))
        
        if (condition_1 | condition_2 | condition_3 | condition_4) and (i - last_buy_signal >= cooldown_period):
            df.at[i, 'buy'] = True
            last_buy_signal = i

            if first_purchase:
                current_dca_amount = initial_cash * initial_allocation_pct
                first_purchase = False
            else:
                current_dca_amount *= dca_multiplier

            if cash >= current_dca_amount:
                units_to_buy = current_dca_amount / df['Close'].iloc[i]
                position += units_to_buy
                total_contract_value += units_to_buy * df['Close'].iloc[i]
                cash -= current_dca_amount
                avg_entry_price = total_contract_value / position
                print(f"Buy executed on index {i}: ${current_dca_amount} worth, {units_to_buy} units at price {df['Close'].iloc[i]}")

        take_profit_price = avg_entry_price * take_profit_multiplier if position > 0 else 0
        df.at[i, 'take_profit_price'] = take_profit_price

        condition_sell = (df['High'].iloc[i] >= take_profit_price) if position > 0 else False

        if condition_sell:
            df.at[i, 'sell'] = True
            cash += position * take_profit_price
            print(f"Sell executed on index {i}: Sold {position} units at price {take_profit_price}")
            position = 0.0
            total_contract_value = 0.0
            avg_entry_price = 0.0
            first_purchase = True
            current_dca_amount = 0.0

        df.at[i, 'cash'] = cash
        df.at[i, 'position'] = position
        df.at[i, 'portfolio_value'] = cash + position * df['Close'].iloc[i]
        if position > 0:
            df.at[i, 'avg_entry_price'] = total_contract_value / position
        else:
            df.at[i, 'avg_entry_price'] = 0.0
        print(f"Portfolio at index {i}: Cash: {cash}, Position: {position}, Portfolio Value: {df.at[i, 'portfolio_value']}, Avg Entry Price: {df.at[i, 'avg_entry_price']}")

    final_portfolio_value = df['portfolio_value'].iloc[-1]
    total_invested = initial_cash * initial_allocation_pct * df['buy'].sum()
    total_return = (final_portfolio_value - initial_cash) / initial_cash * 100

    print(f"Final Portfolio Value: {final_portfolio_value}")
    print(f"Total Return: {total_return}%")
    return df

if __name__ == "__main__":
    symbol = "BTC/USDT"
    timeframe = "4h"
    start_date = "2022-01-01T00:00:00Z"
    end_date = None
    emas = [20, 50, 200]
    df = fetch_and_prepare_data(exchange, symbol, timeframe, start_date=start_date, end_date=end_date)
    df = calculate_inevitrade_pro_indicator(df, rsi_length=14, source_column="Close")
    df = add_multiple_emas(df, column="Close", lengths=emas)
    df = calculate_price_action_index_data(df=df)

    df = backtest_with_signals(df, initial_allocation_pct=0.02, dca_multiplier=1.5 )
    plot_indicators(df, emas=emas)
