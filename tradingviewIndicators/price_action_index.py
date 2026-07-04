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
        'defaultType': 'future',  # Correct type for futures trading
        'defaultSubType': 'linear'  # Bybit USDT perpetual futures are linear contracts
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

def res_in_minutes(timeframe):
    if timeframe.endswith("s"):
        return int(timeframe[:-1]) / 60.0
    elif timeframe.endswith("m"):
        return int(timeframe[:-1])
    elif timeframe.endswith("h"):
        return int(timeframe[:-1]) * 60
    elif timeframe.endswith("D"):
        return 1440
    elif timeframe.endswith("W"):
        return 10080
    elif timeframe.endswith("M"):
        return 43800
    else:
        return None

def res_next_step(res):
    if res <= 1:
        return "15"
    elif res <= 5:
        return "60"
    elif res <= 30:
        return "240"
    elif res <= 60:
        return "1D"
    elif res <= 360:
        return "3D"
    elif res <= 1440:
        return "1W"
    elif res <= 10080:
        return "1M"
    else:
        return "12M"

def multiple_of_res(res, mult):
    target_res_in_min = res * max(mult, 1)
    if target_res_in_min <= 0.083:
        return "5S"
    elif target_res_in_min <= 0.251:
        return "15S"
    elif target_res_in_min <= 0.501:
        return "30S"
    elif target_res_in_min <= 1440:
        return str(round(target_res_in_min))
    elif target_res_in_min <= 43800:
        return str(round(min(target_res_in_min / 1440, 365))) + "D"
    else:
        return str(round(min(target_res_in_min / 43800, 12))) + "M"

def get_htf(timeframe, htf_type, htf_mult, fixed_tf):
    res_in_minutes_value = res_in_minutes(timeframe)
    if htf_type == TF0:
        return timeframe
    elif htf_type == TF1:
        return res_next_step(res_in_minutes_value)
    elif htf_type == TF2:
        return multiple_of_res(res_in_minutes_value, htf_mult)
    elif htf_type == TF3:
        return fixed_tf

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

def apply_color_conditions(df, straddle_area):
    conditions = [
        (df['PAI'] < straddle_area) & (df['PAI'] > -straddle_area),
        (df['PAI'] > straddle_area),
        (df['PAI'] < -straddle_area)
    ]
    choices = ['fuchsia', 'lime', 'red']
    df['Color'] = np.select(conditions, choices, default='black')
    return df

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
    rangeLower = 2  # Min of Lookback Range
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
    lbR = 2  # Pivot Lookback Right
    lbL = 2  # Pivot Lookback Left
    rangeUpper = 10  # Max of Lookback Range
    rangeLower = 2  # Min of Lookback Range
    plotBull = True  # Plot Bullish
    plotHiddenBull = False  # Plot Hidden Bullish
    plotBear = True  # Plot Bearish
    plotHiddenBear = False  # Plot Hidden Bearish
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True, gridspec_kw={'height_ratios': [2, 1]})

    # Plot the PAI with colors on ax1
    for i in range(1, len(df)):
        ax1.plot(df.index[i-1:i+1], df['PAI'].iloc[i-1:i+1], color=df['Color'].iloc[i])

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

    # # Plot pivot lows
    # ax1.scatter(df.index, df['pivot_low'], marker='v', color='blue', label='Pivot Low')

    # # Plot pivot highs
    # ax1.scatter(df.index, df['pivot_high'], marker='^', color='orange', label='Pivot High')

    # Plot bullish conditions
    bullish_indices = df[df['bullCond']].index
    ax1.scatter(bullish_indices, df['PAI'][bullish_indices], marker='o', color=bullColor, s=100, edgecolor='black', label='Bullish Condition')

    # Plot plFound values for regular bullish conditions
    for i in range(len(df)):
        if df['plFound'].iloc[i]:
            ax1.plot(df.index[i], df['PAI'].iloc[i - lbR], 'o', color=bullColor if df['bullCond'].iloc[i] else noneColor)

    # Plot plFound values for hidden bullish conditions
    for i in range(len(df)):
        if df['plFound'].iloc[i]:
            ax1.plot(df.index[i], df['PAI'].iloc[i - lbR], 'o', color=hiddenBullColor if df['hiddenBullCond'].iloc[i] else noneColor)

    # Plot phFound values for regular bearish conditions
    for i in range(len(df)):
        if df['phFound'].iloc[i]:
            ax1.plot(df.index[i], df['PAI'].iloc[i - lbR], 'o', color=bearColor if df['bearCond'].iloc[i] else noneColor)

    # Plot phFound values for hidden bearish conditions
    for i in range(len(df)):
        if df['phFound'].iloc[i]:
            ax1.plot(df.index[i], df['PAI'].iloc[i - lbR], 'o', color=hiddenBearColor if df['hiddenBearCond'].iloc[i] else noneColor)

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

def backtest(df, initial_balance=1000, trade_percentage=10, trade_size_multiplier=10, maker_commission=0.0002, taker_commission=0.0005, take_profit=False, profit_target=1.05):
    balance = initial_balance
    total_quantity = 0
    total_contract_value = 0
    trades = []
    net_gain = 0
    initial_trade_amount = (trade_percentage / 100) * balance
    current_trade_amount = initial_trade_amount

    # Add columns for buy and sell markers, portfolio value, drawdown, cumulative net gain, and cumulative % gain
    df['Buy'] = np.nan
    df['Sell'] = np.nan
    df['Portfolio Value'] = np.nan
    df['Drawdown'] = np.nan
    df['Cumulative Net Gain'] = np.nan
    df['Cumulative % Gain'] = np.nan

    peak_value = initial_balance
    max_drawdown = 0

    open_trades_count = 0
    max_open_trades = 0

    for i in range(len(df)):
        current_price = df['Close'].iloc[i]
        portfolio_value = balance + total_quantity * current_price
        df.at[df.index[i], 'Portfolio Value'] = portfolio_value

        if portfolio_value > peak_value:
            peak_value = portfolio_value
        drawdown = (peak_value - portfolio_value) / peak_value
        max_drawdown = max(max_drawdown, drawdown)
        df.at[df.index[i], 'Drawdown'] = drawdown * 100  # Convert to percentage
        df.at[df.index[i], 'Cumulative Net Gain'] = net_gain
        df.at[df.index[i], 'Cumulative % Gain'] = (net_gain / initial_balance) * 100

        if df['cond_bear_bottom'].iloc[i]:
            trade_amount = current_trade_amount
            entry_price = current_price
            quantity = trade_amount / entry_price
            commission = trade_amount * maker_commission
            total_quantity += quantity
            total_contract_value += trade_amount
            balance -= (trade_amount + commission)
            df.at[df.index[i], 'Buy'] = current_price
            trades.append({
                'type': 'buy',
                'price': round(entry_price, 8),  
                'quantity': round(quantity, 8), 
                'total_quantity_invested': round(total_quantity, 8),
                'quote_quantity_used': round(trade_amount, 2),
                'total_quote_quantity_invested': round(total_contract_value, 2),
                'commission': round(commission, 2),
                'balance': round(balance, 2),
                'portfolio_value': round(portfolio_value, 2),
                'timestamp': df.index[i]
            })
            current_trade_amount *= (1 + trade_size_multiplier / 100)

            open_trades_count += 1
            max_open_trades = max(max_open_trades, open_trades_count)

        if take_profit and total_quantity > 0:
            avg_entry_price = total_contract_value / total_quantity
            target_price = avg_entry_price * profit_target
            if current_price >= target_price:
                exit_price = current_price
                profit = total_quantity * (exit_price - avg_entry_price)
                pnl_percentage = (profit / total_contract_value) * 100
                net_gain += profit
                quote_quantity = total_quantity * exit_price
                commission = quote_quantity * taker_commission
                balance += (quote_quantity - commission)
                df.at[df.index[i], 'Sell'] = current_price
                df.at[df.index[i], 'Portfolio Value'] = balance
                trades.append({
                    'type': 'sell',
                    'price': round(exit_price, 2),  # Assuming rounding to 2 decimal places
                    'quantity': round(total_quantity, 8),  # Common practice for cryptocurrency
                    'total_quantity_sold': round(total_quantity, 8),
                    'quote_quantity_received': round(quote_quantity, 2),
                    'total_quote_quantity_received': round(quote_quantity, 2),
                    'commission': round(commission, 2),
                    'balance': round(balance, 2),
                    'pnl': round(profit, 2),
                    'pnl_percentage': round(pnl_percentage, 2),  # Percentage usually to 2 decimal places
                    'portfolio_value': round(balance, 2),
                    'timestamp': df.index[i]
                })
                total_quantity = 0
                total_contract_value = 0
                current_trade_amount = initial_trade_amount
                open_trades_count = 0  # Reset count after sell

        elif not take_profit and df['cond_bull_top'].iloc[i] and total_quantity > 0:
            avg_entry_price = total_contract_value / total_quantity
            exit_price = current_price
            profit = total_quantity * (exit_price - avg_entry_price)
            pnl_percentage = (profit / total_contract_value) * 100
            net_gain += profit
            quote_quantity = total_quantity * exit_price
            commission = quote_quantity * taker_commission
            balance += (quote_quantity - commission)
            df.at[df.index[i], 'Sell'] = current_price
            df.at[df.index[i], 'Portfolio Value'] = balance
            trades.append({
                'type': 'sell',
                'price': exit_price,
                'quantity': total_quantity,
                'total_quantity_sold': total_quantity,
                'quote_quantity_received': quote_quantity,
                'total_quote_quantity_received': quote_quantity,
                'commission': commission,
                'balance': balance,
                'pnl': profit,
                'pnl_percentage': pnl_percentage,
                'portfolio_value': balance,
                'timestamp': df.index[i]
            })
            total_quantity = 0
            total_contract_value = 0
            current_trade_amount = initial_trade_amount
            open_trades_count = 0  # Reset count after sell

    # Force close any open position at the last price
    if total_quantity > 0:
        final_price = df['Close'].iloc[-1]
        avg_entry_price = total_contract_value / total_quantity
        profit = total_quantity * (final_price - avg_entry_price)
        pnl_percentage = (profit / total_contract_value) * 100
        net_gain += profit
        quote_quantity = total_quantity * final_price
        commission = quote_quantity * taker_commission
        balance += (quote_quantity - commission)
        df.at[df.index[-1], 'Sell'] = final_price
        df.at[df.index[-1], 'Portfolio Value'] = balance
        trades.append({
            'type': 'sell',
            'price': round(final_price, 2),  # Assuming rounding to 2 decimal places
            'quantity': round(total_quantity, 8),  # Common practice for cryptocurrency
            'total_quantity_sold': round(total_quantity, 8),
            'quote_quantity_received': round(quote_quantity, 2),
            'total_quote_quantity_received': round(quote_quantity, 2),
            'commission': round(commission, 2),
            'balance': round(balance, 2),
            'pnl': round(profit, 2),
            'pnl_percentage': round(pnl_percentage, 2),  # Percentage usually to 2 decimal places
            'portfolio_value': round(balance, 2),
            'timestamp': df.index[-1]
        })
        total_quantity = 0
        total_contract_value = 0

    percentage_gain = (net_gain / initial_balance) * 100
    recovery_factor = net_gain /(max_drawdown * initial_balance)

    return trades, initial_balance, balance, net_gain, percentage_gain, max_drawdown * 100, max_open_trades, recovery_factor  # Convert to percentage

def plot_trades(df, chart_name, backtest_results):
    trades, initial_balance, balance, net_gain, percentage_gain, max_drawdown, recovery_factor = backtest_results

    # Create subplots with adjusted row heights and column widths
    fig = make_subplots(
        rows=4, cols=2, shared_xaxes=True, vertical_spacing=0.05, horizontal_spacing=0.1,
        row_heights=[0.50, 0.10, 0.10, 0.10], column_widths=[0.75, 0.25],
        specs=[[{"colspan": 1}, {"type": "domain"}],
               [{"colspan": 1}, {"type": "domain"}],
               [{"colspan": 1}, {"type": "domain"}],
               [{"colspan": 1}, {"type": "domain"}]],
        subplot_titles=(f"{chart_name} - Price with Buy/Sell Signals", 
                        "Portfolio Value Over Time", 
                        "Drawdown Over Time",
                        "Cumulative Net Gain and % Gain Over Time", "")
    )

    # Plot close prices with buy and sell markers
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], mode='lines', name='Close Price', line=dict(color='blue')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Buy'], mode='markers', name='Buy', marker=dict(symbol='triangle-up', color='green', size=10)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Sell'], mode='markers', name='Sell', marker=dict(symbol='triangle-down', color='red', size=10)), row=1, col=1)

    # Plot portfolio value
    fig.add_trace(go.Scatter(x=df.index, y=df['Portfolio Value'], mode='lines', name='Portfolio Value', line=dict(color='blue')), row=2, col=1)

    # Plot drawdown
    fig.add_trace(go.Scatter(x=df.index, y=df['Drawdown'], mode='lines', name='Drawdown', line=dict(color='orange')), row=3, col=1)

    # Plot cumulative net gain and % gain
    fig.add_trace(go.Scatter(x=df.index, y=df['Cumulative Net Gain'], mode='lines', name='Cumulative Net Gain', line=dict(color='purple')), row=4, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['Cumulative % Gain'], mode='lines', name='Cumulative % Gain', line=dict(color='green')), row=4, col=1)

    # Add the table with the backtest results
    table_header = ['Metric', 'Value']
    table_data = [
        ['Initial Balance', f'{initial_balance:.2f}'],
        ['Final Balance', f'{balance:.2f}'],
        ['Net Gain', f'{net_gain:.2f}'],
        ['Percentage Gain', f'{percentage_gain:.2f}%'],
        ['Max Drawdown', f'{max_drawdown:.2f}%'],
        ['Total Trades', f'{len(trades)}'],
        ['Recovery Factor', f'{recovery_factor:.4f}']
    ]

    fig.add_trace(
        go.Table(
            header=dict(values=table_header, fill_color='paleturquoise', align='left'),
            cells=dict(values=[list(row) for row in zip(*table_data)], fill_color='lavender', align='left')
        ),
        row=1, col=2
    )

    # Update layout
    fig.update_layout(
        height=1400, width=1800, title_text=chart_name, showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    # Update x-axes
    fig.update_xaxes(title_text='Date', row=4, col=1)
    
    # Update y-axes
    fig.update_yaxes(title_text='Close Price', row=1, col=1)
    fig.update_yaxes(title_text='Portfolio Value', row=2, col=1)
    fig.update_yaxes(title_text='Drawdown (%)', row=3, col=1)
    fig.update_yaxes(title_text='Net Gain / % Gain', row=4, col=1)
    
    # Add gridlines
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')

    # Add annotations for buys and sells
    buy_signals = df[df['Buy'].notna()]
    sell_signals = df[df['Sell'].notna()]
    
    for i in range(len(buy_signals)):
        fig.add_annotation(
            x=buy_signals.index[i], y=buy_signals['Buy'].iloc[i],
            text="Buy", showarrow=True, arrowhead=1, ax=-10, ay=-40, 
            bgcolor="green", font=dict(color="white")
        )
    
    for i in range(len(sell_signals)):
        fig.add_annotation(
            x=sell_signals.index[i], y=sell_signals['Sell'].iloc[i],
            text="Sell", showarrow=True, arrowhead=1, ax=10, ay=40, 
            bgcolor="red", font=dict(color="white")
        )

    fig.show()




if __name__ == "__main__":


    # Example parameters
    symbol = "BTC/USDT"
    timeframe = "15m"
    start_date = "2024-05-01T00:00:00Z"
    end_date = None


    df = fetch_and_prepare_data(exchange, symbol, timeframe, start_date=start_date, end_date=end_date)

    # HTF Framework
    TF0 = None
    TF1 = "Auto-Steps (15min, 60min, 4H, 1D, 3D, 1W, 1M, 12M)"
    TF2 = "Multiple Of Current TF"
    TF3 = "Fixed TF"

    i_htfRepaints = False  # Repaint HTF
    i_htfType = TF0  # Higher Timeframe Selection
    i_htfType2 = 3.0  # Multiple of Current TF (minimum value 1)
    i_htfType3 = "D"  # Fixed TF

    htfOn = i_htfType != TF0

    current_timeframe = timeframe
    res_in_minutes_value = res_in_minutes(current_timeframe)
    next_step = res_next_step(res_in_minutes_value)
    mult_res = multiple_of_res(res_in_minutes_value, 3)
    htf = get_htf(current_timeframe, i_htfType, i_htfType2, i_htfType3)

    length = 5
    src = df["Close"]
    high = df['High']
    low = df["Low"]

    # Price Action Index inputs
    length = 20  # Stochastic length
    smooth = 3  # Smoothing length
    dis_method = 'dis0'  # Dispersion method (default to dis0)
    dis_len = 20  # Dispersion length
    straddle_area = 5.0  # Straddle area

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

    df['PAI'] = pai(df, "Close", dis_method, dis_len, length, smooth)
    df = apply_color_conditions(df, straddle_area) 
    df = calculate_additional_stuff(df)

    df['cond_bull_breakout'] = crossover(df['PAI'], straddle_area)
    df['cond_bear_breakout'] = crossunder(df['PAI'], -straddle_area)
    df['cond_bull_top'] = crossunder(df['PAI'], 80)
    df['cond_bear_bottom'] = crossover(df['PAI'], -60)

    overbought_area = (80, 100)
    oversold_area = (-60, -100)

    
    initial_balance = 300


    # trades, balance_init, balance, net_gain, percentage_gain, max_drawdown, max_open_trades, recovery_factor = backtest(df, initial_balance=initial_balance, trade_percentage=10, trade_size_multiplier=10, take_profit=True)

    # plot_trades(df, chart_name=f'{symbol}-{timeframe}', backtest_results=(trades, initial_balance, balance, net_gain, percentage_gain, max_drawdown, recovery_factor))
    plot_pai(df.tail(100), straddle_area=straddle_area)
