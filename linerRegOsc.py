import pandas as pd
import numpy as np
import ccxt
from utils.dataManipulation import fetch_and_prepare_data
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots

pd.set_option("display.max_rows", None)


###############################################################################
# 2) Vectorized LRO Calculation
###############################################################################
def compute_linear_regression_oscillator_vectorized(close_array, bar_indices, length):
    """
    Compute the LRO for each bar in a vectorized manner.
    Returns a NumPy array 'lro' of the same length as close_array.
    For i < length-1, lro[i] = np.nan.
    """
    n = length
    N = len(close_array)
    lro = np.full(N, np.nan)

    # Precompute sums for x in [0..n-1]
    sum_x = n * (n - 1) / 2.0
    sum_x_sq = (n - 1) * n * (2 * n - 1) / 6.0
    denominator = n * sum_x_sq - sum_x**2

    # Rolling sum of y => sum_y[i] = sum of close[i-n+1..i]
    close_series = pd.Series(close_array)
    sum_y_series = close_series.rolling(n).sum()
    sum_y = sum_y_series.to_numpy()

    # Weighted rolling sum for sum_xy => sum_{j=0..n-1} (j * close[i-j])
    # We'll do a 1D convolution with weights = [0,1,2,...,n-1]
    weights = np.arange(n)
    conv_full = np.convolve(close_array, weights, mode="full")  # length = N + n - 1
    sum_xy = np.full(N, np.nan)

    # Align so sum_xy[i] matches the sum_{j=0..n-1} j*close[i-j]
    # i.e. at index i, we want the sum of the last n elements in conv_full
    # The last element in that window is conv_full[i], if i >= (n-1)
    for i in range(n - 1, N):
        sum_xy[i] = conv_full[i]

    # Compute slope & intercept for each valid i
    for i in range(n - 1, N):
        if pd.isna(sum_y[i]) or pd.isna(sum_xy[i]):
            continue
        m = (n * sum_xy[i] - sum_x * sum_y[i]) / denominator
        c = (sum_y[i] - m * sum_x) / n
        lro[i] = -(m * bar_indices[i] + c)

    return lro


def compute_normalized_lro_vectorized(lro_array, window=100):
    """
    Normalizes the LRO array using a rolling 'window' period (e.g. 100 bars).
    (lro - rolling_mean) / rolling_std
    """
    lro_series = pd.Series(lro_array)
    rolling_mean = lro_series.rolling(window).mean()
    rolling_std = lro_series.rolling(window).std(ddof=1)
    normalized = (lro_series - rolling_mean) / rolling_std
    return normalized.to_numpy()


###############################################################################
# 3) Signal Detection (Vectorized with shift)
###############################################################################
def detect_signals_vectorized(df, upper, lower):
    """
    Semi-vectorized approach to detect signals:
    - Zero crosses
    - Basic threshold signals
    - Reversion signals with offset = -1
    """
    # Create shifted columns
    df["prev_lro"] = df["Normalized LRO"].shift(1)
    df["lro_2"] = df["Normalized LRO"].shift(2)
    df["lro_3"] = df["Normalized LRO"].shift(3)

    # 1) Zero cross
    df["CrossUnder"] = (df["prev_lro"] > 0) & (df["Normalized LRO"] <= 0)
    df["CrossOver"] = (df["prev_lro"] < 0) & (df["Normalized LRO"] >= 0)

    # 2) Basic threshold signals
    conditions = [
        df["CrossUnder"],
        df["CrossOver"],
        df["Normalized LRO"] > upper,
        df["Normalized LRO"] < lower,
    ]
    choices = ["CrossUnder_Sell", "CrossOver_Buy", "Sell", "Buy"]
    df["Signal"] = np.select(conditions, choices, default="Neutral")

    # 3) Reversion Markers
    # Pine:
    # cond_1 = crossunder(osc, osc[2]) and osc>upper => diamond on bar i-1
    # crossunder => (osc[i-1]>=osc[i-3]) & (osc[i]<osc[i-2])
    df["Reversion_Sell"] = False
    df["Reversion_Buy"] = False

    crossunder2 = (
        (df["prev_lro"] >= df["lro_3"])
        & (df["Normalized LRO"] < df["lro_2"])
        & (df["Normalized LRO"] > upper)
    )
    # place diamond on bar i-1 => shift(0) means same row, but we store on that row
    df.loc[crossunder2, "Reversion_Sell"] = True

    crossover2 = (
        (df["prev_lro"] <= df["lro_3"])
        & (df["Normalized LRO"] > df["lro_2"])
        & (df["Normalized LRO"] < lower)
    )
    df.loc[crossover2, "Reversion_Buy"] = True

    # If you want the diamond at bar i-1 for the y-value, do:
    df["Reversion_Sell_Val"] = np.nan
    df["Reversion_Buy_Val"] = np.nan
    # The actual oscillator from bar i-1
    df.loc[df["Reversion_Sell"] == True, "Reversion_Sell_Val"] = df["prev_lro"]
    df.loc[df["Reversion_Buy"] == True, "Reversion_Buy_Val"] = df["prev_lro"]

    return df


###############################################################################
# 4) Final “Run Strategy” Function
###############################################################################
def run_strategy(df, length=20, upper=1.5, lower=-1.5):
    # Vectorized LRO
    close_array = df["Close"].to_numpy()
    bar_indices = np.arange(len(close_array))
    lro = compute_linear_regression_oscillator_vectorized(
        close_array, bar_indices, length
    )

    # Vectorized Normalization
    norm_lro = compute_normalized_lro_vectorized(lro, window=100)

    # Store results
    df["LRO"] = lro
    df["Normalized LRO"] = norm_lro

    # Detect signals
    df = detect_signals_vectorized(df, upper, lower)
    return df


if __name__ == "__main__":
    exchange = ccxt.bybit(
        {
            "options": {"defaultType": "future", "defaultSubType": "linear"},
            "rateLimit": 1200,
            "enableRateLimit": True,
        }
    )

    symbol = "ETH/USDT"
    timeframe = "1m"
    start_date = "2025-02-13T00:00:00Z"
    end_date = None

    df = fetch_and_prepare_data(
        exchange, symbol, timeframe, start_date=start_date, end_date=end_date
    )

    # # df.sort_values("Date", inplace=True)
    # df.set_index("Date", inplace=True)

    # 2) Run vectorized strategy
    df = run_strategy(df, length=20, upper=1.5, lower=-1.5)

    # 3) Plot last 200 bars with Plotly
    df_last200 = df.tail(200).copy()

    cross_over = df_last200[df_last200["CrossOver"] == True]
    cross_under = df_last200[df_last200["CrossUnder"] == True]
    reversion_sell = df_last200[df_last200["Reversion_Sell"] == True]
    reversion_buy = df_last200[df_last200["Reversion_Buy"] == True]

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.7, 0.3],
        subplot_titles=("OHLC Chart", "Normalized LRO"),
    )

    # --- TOP CHART: Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df_last200.index,
            open=df_last200["Open"],
            high=df_last200["High"],
            low=df_last200["Low"],
            close=df_last200["Close"],
            name="OHLC",
        ),
        row=1,
        col=1,
    )

    # --- BOTTOM CHART: Oscillator with area fill
    osc_values = df_last200["Normalized LRO"].values
    x_values = df_last200.index
    y_pos = [v if v > 0 else 0 for v in osc_values]
    y_neg = [v if v < 0 else 0 for v in osc_values]

    # Fill area above zero
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=y_pos,
            fill="tozeroy",
            mode="none",
            fillcolor="rgba(16,202,184,0.6)",
            name="Osc > 0",
        ),
        row=2,
        col=1,
    )
    # Fill area below zero
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=y_neg,
            fill="tozeroy",
            mode="none",
            fillcolor="rgba(0,128,255,0.6)",
            name="Osc < 0",
        ),
        row=2,
        col=1,
    )
    # White line for oscillator
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=osc_values,
            mode="lines",
            line=dict(color="white", width=2),
            name="Normalized LRO",
        ),
        row=2,
        col=1,
    )
    # Threshold lines
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=[1.5] * len(x_values),
            mode="lines",
            line=dict(color="red", dash="dash"),
            name="Upper (1.5)",
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=[-1.5] * len(x_values),
            mode="lines",
            line=dict(color="green", dash="dash"),
            name="Lower (-1.5)",
        ),
        row=2,
        col=1,
    )

    # Markers
    fig.add_trace(
        go.Scatter(
            x=cross_over.index,
            y=cross_over["Normalized LRO"],
            mode="markers",
            marker=dict(color="lime", symbol="triangle-up", size=10),
            name="CrossOver",
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=cross_under.index,
            y=cross_under["Normalized LRO"],
            mode="markers",
            marker=dict(color="red", symbol="triangle-down", size=10),
            name="CrossUnder",
        ),
        row=2,
        col=1,
    )

    # Reversion Sell => Diamond
    fig.add_trace(
        go.Scatter(
            x=reversion_sell.index,
            y=reversion_sell["Reversion_Sell_Val"],
            mode="markers",
            marker=dict(color="red", symbol="diamond", size=10),
            name="Reversion Sell",
        ),
        row=2,
        col=1,
    )
    # Reversion Buy => Diamond
    fig.add_trace(
        go.Scatter(
            x=reversion_buy.index,
            y=reversion_buy["Reversion_Buy_Val"],
            mode="markers",
            marker=dict(color="lime", symbol="diamond", size=10),
            name="Reversion Buy",
        ),
        row=2,
        col=1,
    )

    # Dark theme layout
    fig.update_layout(
        title="OHLC Chart with Dark Background & Area-Filled Oscillator",
        height=800,
        legend_title="Legend",
        paper_bgcolor="black",
        plot_bgcolor="black",
        font_color="white",
    )
    fig.update_xaxes(
        rangeslider=dict(visible=False),
        gridcolor="gray",
        zerolinecolor="gray",
        color="white",
    )
    fig.update_yaxes(gridcolor="gray", zerolinecolor="gray", color="white")
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Normalized LRO", row=2, col=1)

    fig.show()

    print(df.head())
