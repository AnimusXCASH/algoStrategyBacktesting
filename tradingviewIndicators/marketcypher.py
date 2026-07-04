"""
**Rules**

1) can only go long when price is above the 200 EMA and can only take shorts when price is below the 200 EMA

2) Can only take a position when price has pulled back into the 50 EMA

3) Can only go long if mf is positive and short only when mf is negative

4) Can only go long when wave trend is negative and only go short when wave trend is positive

entry on close via a wave trend cross stop below the swing low/ above the swing high, profit at 2x the stop
"""
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import backtrader as bt
import pandas as pd
import ccxt
import datetime
import numpy as np
from strategies.dca_size_multiplier_tp import DCAStrategyCompound2
from strategies.dca_macd import DCAMacd
from prettytable import PrettyTable
from customStats.profitAndLoss import PNLPercentage
from customStats.totalTestLengthStats import TotalTestLengthStats
from utils.other import CCXTData
from utils.dataManipulation import fetch_and_prepare_data
import pandas_ta as ta
import plotly.graph_objects as go
import numpy as np


exchange = ccxt.binance(
    {
        "options": {"defaultType": "swap", "defaultContractType": "perpetual"},
        "rateLimit": 1200,
        "enableRateLimit": True,
    }
)


# Create the table with these keys as column headers
table = PrettyTable()


if __name__ == "__main__":

    symbol = "ETH/USDT"
    timeframe = "1h"
    start_date = "2024-06-01T00:00:00Z"  # None Or  '2023-01-01T00:00:00Z'  for start
    end_date = None  # None Or  '2023-01-01T00:00:00Z'  for end

    df = fetch_and_prepare_data(
        exchange, symbol, timeframe, start_date=start_date, end_date=end_date
    )

    # Wave trend
    n1 = 9  # channel length
    n2 = 12  # average length

    # Wave trend indicator
    df["ap"] = (df.High + df.Low + df.Close) / 3  # wt ma source
    df["esa"] = ta.ema(df.ap, n1)  # EMA of the ma source by channel length
    df["d"] = ta.ema(abs(df.ap - df.esa), n1)
    df["ci"] = (df.ap - df.esa) / (0.015 * df.d)
    df["wt1"] = ta.ema(df.ci, n2)
    df["wt2"] = ta.sma(df.wt1, 3)  # set to 3 or 4

    # RSI Of the money flow

    period = 60
    multi = 150
    posy = 2.5

    df["mfrsi"] = (
        ta.sma(((df.Close - df.Open) / (df.High - df.Low) * multi), period)
    ) - posy

    # Moving averages
    df["ma50"] = ta.ema(df.Close, 50)
    df["ma200"] = ta.ema(df.Close, 200)

    df = round(df, 2)

    x = df.index
    y = df["mfrsi"]
    cutoff = 0

    x_pairs = [(x[i], x[i + 1]) for i in range(len(x) - 1)]
    y_pairs = [(y[i], y[i + 1]) for i in range(len(y) - 1)]

    colors = [
        "green" if any([i > cutoff for i in y_values]) else "red"
        for y_values in y_pairs
    ]


    candlestick = go.Candlestick(
        x=df.index,
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        name="Candlestick",
    )

    # Create a trace for the 50-day moving average (blue)
    trace_ma50 = go.Scatter(
        x=df.index, y=df["ma50"], name="50-day MA", line=dict(color="blue")
    )

    # Create a trace for the 200-day moving average (orange)
    trace_ma200 = go.Scatter(
        x=df.index, y=df["ma200"], name="200-day MA", line=dict(color="orange")
    )


    fig = go.Figure(data=[candlestick, trace_ma50, trace_ma200])
    # fig.update_layout(height=800, width=1200)

    # Add the candlestick chart and the mfrsi line
    fig.add_trace(
        go.Candlestick(
            x=x,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="Candlestick",
        )
    )

    # Add the mfrsi line with conditional color
    for x_range, y_range, color in zip(x_pairs, y_pairs, colors):
        fig.add_trace(
            go.Scatter(
                x=list(x_range),
                y=list(y_range),
                mode="lines",
                line={"color": color},
                xaxis="x",
                yaxis="y2",
                showlegend=False,
            )
        )

    # Add a constant black line at y=0
    fig.add_trace(
        go.Scatter(
            x=[x[0], x[-1]],
            y=[0, 0],
            mode="lines",
            line={"color": "black"},
            xaxis="x",
            yaxis="y2",
            showlegend=False,
        )
    )

    # Calculate crossing points
    cross_above = (df["wt1"] > df["wt2"]) & (df["wt1"].shift(1) <= df["wt2"].shift(1))
    cross_below = (df["wt1"] < df["wt2"]) & (df["wt1"].shift(1) >= df["wt2"].shift(1))

    # Add red dots for crossings below
    fig.add_trace(
        go.Scatter(
            x=df.index[cross_below],
            y=df["wt1"][cross_below],
            mode="markers",
            marker=dict(color="red"),
            name="Cross Below",
            xaxis="x",
            yaxis="y2",
            showlegend=False,
        )
    )

    # Add green dots for crossings above
    fig.add_trace(
        go.Scatter(
            x=df.index[cross_above],
            y=df["wt1"][cross_above],
            mode="markers",
            marker=dict(color="green"),
            name="Cross Above",
            xaxis="x",
            yaxis="y2",
            showlegend=False,
        )
    )

    # Create subplots for wt1 (light blue) and wt2 (dark blue)
    trace_wt1 = go.Scatter(
        x=df.index,
        y=df["wt1"],
        name="wt1",
        xaxis="x",
        yaxis="y2",
        line=dict(color="lightblue"),
    )
    trace_wt2 = go.Scatter(
        x=df.index,
        y=df["wt2"],
        name="wt2",
        xaxis="x",
        yaxis="y2",
        line=dict(color="darkblue"),
    )

    fig.add_trace(trace_wt1)
    fig.add_trace(trace_wt2)

    layout = go.Layout(
        title="candlestick chart",
        xaxis=dict(domain=[0, 1]),
        yaxis=dict(domain=[0.4, 1]),
        yaxis2=dict(domain=[0, 0.3]),
        xaxis_rangeslider_visible=False,
    )

    fig.update_layout(layout)
    fig.show()

    ## Trading rules

    df["HH"] = df.High.rolling(5).max()
    df["LL"] = df.Low.rolling(5).min()
    columns_to_drop = ["Volume", "ap", "esa", "d", "ci"]
    df.drop(columns=columns_to_drop, inplace=True)

    df = round(df, 2)
    df = df.dropna()

    # cross of waves
    df["cross"] = np.select(
        [
            (df["wt1"].shift(1) < df["wt2"].shift(1)) & (df["wt1"] > df["wt2"]),
            (df["wt1"].shift(1) > df["wt2"].shift(1)) & (df["wt1"] < df["wt2"]),
        ],
        ["up", "down"],
    )

    df["signal"] = np.select(
        [
            (df.cross == "up")
            & (df.Close > df.ma200)
            & (df.LL < df.ma50)
            & (df.mfrsi > 0)
            & (df.wt1 < 0)
            & (df.wt2 < 0),
            (df.cross == "down")
            & (df.Close < df.ma200)
            & (df.HH > df.ma50)
            & (df.mfrsi < 0)
            & (df.wt1 > 0)
            & (df.wt2 > 0),
        ],
        [1, 2],
    )

    # with pd.option_context('display.max_rows', None,
    #                    'display.max_columns', None,
    #                    'display.precision', 3,
    #                    ):

    # print(df)

    # trade processing
    trades = []
    entry = 0
    exit = 0
    stop = 0
    profit = 0
    entry_date = 0
    exit_date = 0
    position = None

    for i in range(len(df)):
        if position == None:

            # long entry
            if df.signal.iloc[i] == 1:
                entry = df.Close.iloc[i]
                stop = df.LL.iloc[i]
                profit = (entry - stop) * 2 + entry
                entry_date = df.index[i]
                position = "Long"

            # short entry
            elif df.signal.iloc[i] == 2:
                entry = df.Close.iloc[i]
                stop = df.HH.iloc[i]
                profit = entry - (stop - entry) * 2
                entry_date = df.index[i]
                position = "Short"

        # long exit
        if position == "Long":
            if df.High.iloc[i] > profit:
                exit = profit
                exit_date = df.index[i]
            elif df.Low.iloc[i] <= stop:
                exit = stop
                exit_date = df.index[i]

        # short exit
        if position == "Short":
            if df.Low.iloc[i] < profit:
                exit = profit
                exit_date = df.index[i]
            elif df.High.iloc[i] >= stop:
                exit = stop
                exit_date = df.index[i]

        # record the trades
        if exit != 0:
            if position == "Long":
                trades.append(
                    {
                        "Entry Date": entry_date,
                        "Direction": position,
                        "Entry Price": entry,
                        "Profit": profit,
                        "Stop": stop,
                        "Exit Price": exit,
                        "Exit Date": exit_date,
                        "PL": exit - entry,
                    }
                )

            elif position == "Short":
                trades.append(
                    {
                        "Entry Date": entry_date,
                        "Direction": position,
                        "Entry Price": entry,
                        "Profit": profit,
                        "Stop": stop,
                        "Exit Price": exit,
                        "Exit Date": exit_date,
                        "PL": entry - exit,
                    }
                )

            entry_date = 0
            position = None
            entry = 0
            profit = 0
            stop = 0
            exit = 0
            exit_date = 0

    trades_df = pd.DataFrame(trades)
    print(trades_df)
    Total = trades_df["PL"].sum()
    print(Total)
