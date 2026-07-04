import pandas as pd
import numpy as np
import datetime
import os
import sys
import datetime
import time

pd.set_option("display.max_rows", None)

pd.set_option("display.max_columns", None)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import datetime
import pandas as pd
import plotly.graph_objects as go

BYBIT_API_KEY = "Rl2tS7S8sIN39gmPiu"
BYBIT_API_SECRET = "vlXJ8CZwpLfO5XlbdS3zUaRSI44EidvIOgpn"
TESTNET = False  # True means your API keys were generated on testnet.bybit.com


from utils.pybitWrapper import BybitWrapper


def detect_fvg(data, lookback_period=500, body_multiplier=1.5, remove_mitigated=False):
    """
    Detects Fair Value Gaps (FVGs) in historical price data and optionally removes
    those gaps that have been mitigated (filled) by subsequent price action.

    Parameters:
        data (DataFrame): DataFrame with columns ['Open', 'High', 'Low', 'Close'].
        lookback_period (int): Number of candles to look back for average body size.
        body_multiplier (float): Multiplier to determine significant body size.
        remove_mitigated (bool): If True, gaps that have been filled later are removed.

    Returns:
        list: A list of the same length as `data` where each element is either:
              - a tuple: ('bullish', lower_bound, upper_bound, index) or
                         ('bearish', lower_bound, upper_bound, index) if an FVG is detected,
              - or None if no gap is detected at that candle.

    For a bullish gap:
      - lower_bound = first candle's High (i-2)
      - upper_bound = third candle's Low (i)
    For a bearish gap:
      - lower_bound = third candle's High (i)
      - upper_bound = first candle's Low (i-2)
    """
    # Initialize the list so that its length matches the DataFrame.
    fvg_list = [None] * len(data)

    # Loop starts at index 2 because we need three candles to detect a gap.
    for i in range(2, len(data)):
        first_high = data["High"].iloc[i - 2]
        first_low = data["Low"].iloc[i - 2]
        middle_open = data["Open"].iloc[i - 1]
        middle_close = data["Close"].iloc[i - 1]
        third_low = data["Low"].iloc[i]
        third_high = data["High"].iloc[i]

        # Calculate the average absolute body size over the lookback period.
        start_idx = max(0, i - 1 - lookback_period)
        prev_bodies = (
            data["Close"].iloc[start_idx : i - 1] - data["Open"].iloc[start_idx : i - 1]
        ).abs()
        avg_body_size = prev_bodies.mean() or 0.001  # Avoid division by zero

        middle_body = abs(middle_close - middle_open)
        gap = None

        # Detect Bullish FVG: gap exists if third_low > first_high and the middle candle's body is significant.
        if third_low > first_high and middle_body > avg_body_size * body_multiplier:
            # For bullish FVG, gap boundaries are: lower = first_high, upper = third_low.
            gap = ("bullish", first_high, third_low, i)
        # Detect Bearish FVG: gap exists if third_high < first_low.
        elif third_high < first_low and middle_body > avg_body_size * body_multiplier:
            # For bearish FVG, gap boundaries are: lower = third_high, upper = first_low.
            gap = ("bearish", third_high, first_low, i)

        fvg_list[i] = gap

    # If requested, remove gaps that have been filled.
    if remove_mitigated:
        for i, gap in enumerate(fvg_list):
            if gap is not None and is_gap_filled(gap, data):
                fvg_list[i] = None

    return fvg_list


def is_gap_filled(gap, data):
    """
    Checks whether the given gap has been mitigated (filled) by subsequent price action.

    Parameters:
        gap (tuple): A gap tuple in the format (type, lower_bound, upper_bound, index).
        data (DataFrame): Historical price data.

    Returns:
        bool: True if the gap is filled, False otherwise.
    """
    gap_type, lower_bound, upper_bound, gap_index = gap

    # Loop over all candles that occur after the gap formation.
    for j in range(gap_index + 1, len(data)):
        candle_low = data["Low"].iloc[j]
        candle_high = data["High"].iloc[j]

        # If any candle trades into the gap, consider it filled.
        if candle_high >= lower_bound and candle_low <= upper_bound:
            return True
    return False


# -------------------------
# New Backtesting Functions
# -------------------------


def backtest_fvg_trading(
    data,
    fvg_list,
    initial_capital=1000,
    trade_amount=25,
    target_pct=0.0001,
    tolerance=0.001,
):
    capital = initial_capital
    long_trades = []    # list of closed long trades
    short_trades = []   # list of closed short trades
    open_long = None    # currently open long trade (None if no trade open)
    open_short = None   # currently open short trade (None if no trade open)
    
    # To ensure a gap signal is used only once per side.
    triggered_gap_indices_long = set()
    triggered_gap_indices_short = set()

    n = len(data)

    for i in range(n):
        candle_high = data["High"].iloc[i]
        candle_low = data["Low"].iloc[i]
        
        # Debug print for candle data.
        print(f"Candle {i}: High={candle_high:.5f}, Low={candle_low:.5f}")

        # --- Check for closing the open long trade ---
        if open_long is not None:
            if candle_high >= open_long["target_price"]:
                print(f"  [DEBUG] Candle {i}: Closing LONG trade (entry={open_long['entry_price']:.5f}, target={open_long['target_price']:.5f})")
                open_long["exit_index"] = i
                open_long["exit_price"] = open_long["target_price"]
                shares = trade_amount / open_long["entry_price"]
                open_long["profit"] = shares * (open_long["exit_price"] - open_long["entry_price"])
                capital += open_long["profit"]
                long_trades.append(open_long)
                open_long = None

        # --- Check for closing the open short trade ---
        if open_short is not None:
            if candle_low <= open_short["target_price"]:
                print(f"  [DEBUG] Candle {i}: Closing SHORT trade (entry={open_short['entry_price']:.5f}, target={open_short['target_price']:.5f})")
                open_short["exit_index"] = i
                open_short["exit_price"] = open_short["target_price"]
                shares = trade_amount / open_short["entry_price"]
                open_short["profit"] = shares * (open_short["entry_price"] - open_short["exit_price"])
                capital += open_short["profit"]
                short_trades.append(open_short)
                open_short = None

        # --- Check for new LONG entry (only if no long trade is open) ---
        if open_long is None:
            for j, gap in enumerate(fvg_list):
                if gap is not None and gap[0] == "bullish" and gap[3] < i and j not in triggered_gap_indices_long:
                    gap_price = gap[1]  # For bullish gaps, use gap's lower boundary as entry price.
                    tol = gap_price * tolerance
                    if candle_low - tol <= gap_price <= candle_high + tol:
                        entry_price = gap_price
                        target_price = entry_price * (1 + target_pct)
                        new_trade = {
                            "side": "long",
                            "gap_index": gap[3],
                            "entry_index": i,
                            "entry_price": entry_price,
                            "target_price": target_price,
                            "exit_index": None,
                            "exit_price": None,
                            "profit": None,
                        }
                        open_long = new_trade
                        triggered_gap_indices_long.add(j)
                        print(f"  [DEBUG] Candle {i}: Opening LONG trade at {entry_price:.5f}, target={target_price:.5f}")
                        break  # Only one long trade allowed at a time.

        # --- Check for new SHORT entry (only if no short trade is open) ---
        if open_short is None:
            for j, gap in enumerate(fvg_list):
                if gap is not None and gap[0] == "bearish" and gap[3] < i and j not in triggered_gap_indices_short:
                    gap_price = gap[2]  # For bearish gaps, use gap's upper boundary as entry price.
                    tol = gap_price * tolerance
                    if candle_high + tol >= gap_price >= candle_low - tol:
                        entry_price = gap_price
                        target_price = entry_price * (1 - target_pct)
                        new_trade = {
                            "side": "short",
                            "gap_index": gap[3],
                            "entry_index": i,
                            "entry_price": entry_price,
                            "target_price": target_price,
                            "exit_index": None,
                            "exit_price": None,
                            "profit": None,
                        }
                        open_short = new_trade
                        triggered_gap_indices_short.add(j)
                        print(f"  [DEBUG] Candle {i}: Opening SHORT trade at {entry_price:.5f}, target={target_price:.5f}")
                        break  # Only one short trade allowed at a time.

    # --- Force-close any remaining open trades at the final candle's close ---
    last_close = data["Close"].iloc[-1]
    final_index = n - 1

    if open_long is not None:
        open_long["exit_index"] = final_index
        open_long["exit_price"] = last_close
        shares = trade_amount / open_long["entry_price"]
        open_long["profit"] = shares * (open_long["exit_price"] - open_long["entry_price"])
        capital += open_long["profit"]
        long_trades.append(open_long)
        open_long = None

    if open_short is not None:
        open_short["exit_index"] = final_index
        open_short["exit_price"] = last_close
        shares = trade_amount / open_short["entry_price"]
        open_short["profit"] = shares * (open_short["entry_price"] - open_short["exit_price"])
        capital += open_short["profit"]
        short_trades.append(open_short)
        open_short = None

    return {
        "final_capital": capital,
        "long_trades": long_trades,
        "short_trades": short_trades,
    }

# -------------------------
# Example Main Block
# -------------------------

if __name__ == "__main__":

    now = datetime.datetime.now(datetime.timezone.utc)
    print(f"current time {now}")
    today = now.date()

    wrapper = BybitWrapper(
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET,
        testnet=TESTNET,
    )

    wrapper.symbol_setter(symbol="DOGEUSDT")

    df = wrapper.get_kline_data(interval=1, limit=500)
    print(df)

    # Detect FVGs using your function.
    fvg_list = detect_fvg(df)

    results = backtest_fvg_trading(df, fvg_list, initial_capital=1000, trade_amount=25, target_pct=0.005, tolerance=0.001)

    final_capital = results["final_capital"]
    long_trades = results["long_trades"]
    short_trades = results["short_trades"]

    print("Final Capital: ${:.2f}".format(final_capital))
    print("Number of long trades executed:", len(long_trades))
    for t in long_trades:
        shares = 25 / t["entry_price"]
        print("Long Trade from candle {} to {}: entry @ {:.4f}, exit @ {:.4f}, shares {:.2f}, profit ${:.2f}".format(
            t["entry_index"], t["exit_index"], t["entry_price"], t["exit_price"], shares, t["profit"]
        ))
    print("Number of short trades executed:", len(short_trades))
    for t in short_trades:
        shares = 25 / t["entry_price"]
        print("Short Trade from candle {} to {}: entry @ {:.4f}, exit @ {:.4f}, shares {:.2f}, profit ${:.2f}".format(
            t["entry_index"], t["exit_index"], t["entry_price"], t["exit_price"], shares, t["profit"]
        ))

    # -------------
    # Plot the Chart
    # -------------
    fig = go.Figure(data=[go.Candlestick(
        x=df.index,
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        name="Candles"
    )])

    # Mark the detected bullish FVG zones.
    for idx, gap in enumerate(fvg_list):
        if gap is not None and gap[0] == "bullish":
            gap_lower = gap[1]
            gap_upper = gap[2]
            gap_index = gap[3]
            fig.add_shape(
                type="rect",
                x0=df.index[gap_index],
                x1=df.index[min(gap_index + 10, len(df)-1)],
                y0=gap_lower,
                y1=gap_upper,
                fillcolor="rgba(0,255,0,0.3)",
                opacity=0.5,
                layer="below",
                line=dict(width=0),
            )
    
    # Mark the trade paths.
    # For each closed long trade, draw a dotted green line with entry and exit annotations.
    for trade in long_trades:
        entry_time = df.index[trade["entry_index"]]
        exit_time = df.index[trade["exit_index"]]
        fig.add_shape(
            type="line",
            x0=entry_time,
            y0=trade["entry_price"],
            x1=exit_time,
            y1=trade["exit_price"],
            line=dict(color="green", width=2, dash="dot")
        )
        fig.add_annotation(
            x=entry_time,
            y=trade["entry_price"],
            text="Long Entry",
            showarrow=True,
            arrowhead=1,
            ax=0,
            ay=-20,
            font=dict(color="green"),
            bgcolor="white"
        )
        fig.add_annotation(
            x=exit_time,
            y=trade["exit_price"],
            text="Long Exit",
            showarrow=True,
            arrowhead=1,
            ax=0,
            ay=20,
            font=dict(color="green"),
            bgcolor="white"
        )
    
    # For each closed short trade, draw a dotted red line with entry and exit annotations.
    for trade in short_trades:
        entry_time = df.index[trade["entry_index"]]
        exit_time = df.index[trade["exit_index"]]
        fig.add_shape(
            type="line",
            x0=entry_time,
            y0=trade["entry_price"],
            x1=exit_time,
            y1=trade["exit_price"],
            line=dict(color="red", width=2, dash="dot")
        )
        fig.add_annotation(
            x=entry_time,
            y=trade["entry_price"],
            text="Short Entry",
            showarrow=True,
            arrowhead=1,
            ax=0,
            ay=20,
            font=dict(color="red"),
            bgcolor="white"
        )
        fig.add_annotation(
            x=exit_time,
            y=trade["exit_price"],
            text="Short Exit",
            showarrow=True,
            arrowhead=1,
            ax=0,
            ay=-20,
            font=dict(color="red"),
            bgcolor="white"
        )

    fig.update_layout(
        width=1200,
        height=800,
        title="Candlestick Chart with Fair Value Gaps and Trade Paths",
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=False),
        plot_bgcolor="black",
        paper_bgcolor="black"
    )
    fig.show()