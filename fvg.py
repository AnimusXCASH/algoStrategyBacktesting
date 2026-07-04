import pandas as pd
import numpy as np
import datetime
import os
import sys
import time
import plotly.graph_objects as go
from datetime import datetime

pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.pybitWrapper import BybitWrapper


def detect_fvg(data, lookback_period=100, body_multiplier=1.5, remove_mitigated=True):
    """
    Detects Fair Value Gaps (FVGs) in historical price data and optionally removes
    those gaps that have been mitigated (filled) by subsequent price action.
    
    For a bullish gap:
      - lower_bound = first candle's High (i-2)
      - upper_bound = third candle's Low (i)
    For a bearish gap:
      - lower_bound = third candle's High (i)
      - upper_bound = first candle's Low (i-2)
    """
    fvg_list = [None] * len(data)
    
    for i in range(2, len(data)):
        first_high = data['High'].iloc[i-2]
        first_low  = data['Low'].iloc[i-2]
        middle_open  = data['Open'].iloc[i-1]
        middle_close = data['Close'].iloc[i-1]
        third_low  = data['Low'].iloc[i]
        third_high = data['High'].iloc[i]

        start_idx = max(0, i-1-lookback_period)
        prev_bodies = (data['Close'].iloc[start_idx:i-1] - data['Open'].iloc[start_idx:i-1]).abs()
        avg_body_size = prev_bodies.mean() or 0.001

        middle_body = abs(middle_close - middle_open)
        gap = None

        if third_low > first_high and middle_body > avg_body_size * body_multiplier:
            gap = ('bullish', first_high, third_low, i)
        elif third_high < first_low and middle_body > avg_body_size * body_multiplier:
            gap = ('bearish', third_high, first_low, i)
        
        fvg_list[i] = gap

    if remove_mitigated:
        for i, gap in enumerate(fvg_list):
            if gap is not None and is_gap_filled(gap, data):
                fvg_list[i] = None

    return fvg_list

def is_gap_filled(gap, data):
    """
    Returns True if any candle after the gap formation trades through the gap.
    """
    gap_type, lower_bound, upper_bound, gap_index = gap
    for j in range(gap_index + 1, len(data)):
        candle_low = data['Low'].iloc[j]
        candle_high = data['High'].iloc[j]
        if candle_high >= lower_bound and candle_low <= upper_bound:
            return True
    return False


def detect_order_blocks(data):
    """
    Detects potential order blocks using a looser engulfing pattern:
      - For bullish blocks, the next candle's HIGH >= the previous candle's HIGH
      - For bearish blocks, the next candle's LOW <= the previous candle's LOW
    """
    blocks = []
    for i in range(1, len(data)):
        prev = data.iloc[i-1]
        curr = data.iloc[i]
        
        # Bullish order block
        if prev["Close"] < prev["Open"] and curr["Close"] > curr["Open"]:
            if curr["High"] >= prev["High"]:
                blocks.append({
                    "type": "bullish",
                    "index": i-1,
                    "low": prev["Low"],
                    "high": prev["High"]
                })
        
        # Bearish order block
        if prev["Close"] > prev["Open"] and curr["Close"] < curr["Open"]:
            if curr["Low"] <= prev["Low"]:
                blocks.append({
                    "type": "bearish",
                    "index": i-1,
                    "low": prev["Low"],
                    "high": prev["High"]
                })
    return blocks

def is_order_block_mitigated(block, data):
    """
    Checks if an order block is mitigated.
    
    For a bullish block, if any candle after the block's formation has a Low that is at or below
    the block's Low, it is considered mitigated.
    
    For a bearish block, if any candle after the block's formation has a High that is at or above
    the block's High, it is considered mitigated.
    """
    block_index = block["index"]
    if block["type"] == "bullish":
        for i in range(block_index+1, len(data)):
            if data["Low"].iloc[i] <= block["low"]:
                return True
        return False
    elif block["type"] == "bearish":
        for i in range(block_index+1, len(data)):
            if data["High"].iloc[i] >= block["high"]:
                return True
        return False
    return False


if __name__ == "__main__":

    BYBIT_API_KEY = "Rl2tS7S8sIN39gmPiu"
    BYBIT_API_SECRET = "vlXJ8CZwpLfO5XlbdS3zUaRSI44EidvIOgpn"
    TESTNET = False  # False for mainnet

    now = datetime.datetime.now(datetime.timezone.utc)
    print(f"current time {now}")
    today = now.date()

    wrapper = BybitWrapper(
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET,
        testnet=TESTNET,
    )
    wrapper.symbol_setter(symbol="ETHUSDT")

    df = wrapper.get_kline_data(interval=15)
    df["FVG"] = detect_fvg(df)


    # Create the candlestick chart.
    fig = go.Figure(data=[go.Candlestick(
        x=df.index,
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        name="Candles"
    )])

    # Overlay FVG zones.
    for _, row in df.iterrows():
        if isinstance(row["FVG"], tuple):
            fvg_type, start, end, index = row["FVG"]
            color = "rgba(0,255,0,0.3)" if fvg_type == "bullish" else "rgba(255,0,0,0.3)"
            fig.add_shape(
                type="rect",
                x0=df.index[index],
                x1=df.index[min(index + 10, len(df)-1)],
                y0=start,
                y1=end,
                fillcolor=color,
                opacity=0.8,
                layer="below",
                line=dict(width=0)
            )

    # Detect order blocks.
    order_blocks = detect_order_blocks(df)

    # Overlay order block zones.
    # We will only mark non-mitigated order blocks (mitigated ones are omitted).
    for block in order_blocks:
        if not is_order_block_mitigated(block, df):
            idx = block["index"]
            x0 = df.index[idx]
            x1 = df.index[min(idx + 10, len(df)-1)]
            # Use white fill for order block zones.
            fig.add_shape(
                type="rect",
                x0=x0,
                x1=x1,
                y0=block["low"],
                y1=block["high"],
                fillcolor="rgba(255,255,255,0.3)",
                opacity=0.5,
                layer="below",
                line=dict(width=0)
            )

    fig.update_layout(
        width=1200,
        height=800,
        title="Candlestick Chart with FVG Zones and Order Blocks",
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=False),
        plot_bgcolor="black",
        paper_bgcolor="black"
    )
    fig.show()
