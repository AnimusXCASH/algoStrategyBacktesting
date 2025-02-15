import pandas as pd
import numpy as np
import ccxt
from utils.dataManipulation import fetch_and_prepare_data
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots

pd.set_option("display.max_rows", None)


class BarByBarProcessor:
    def __init__(self, data):
        self.data = data.copy()
        self.data["Signal"] = None

        self.close_prices = self.data["Close"].to_numpy()
        self.open_prices = self.data["Open"].to_numpy()
        self.high_prices = self.data["High"].to_numpy()
        self.low_prices = self.data["Low"].to_numpy()
        self.volume = self.data["Volume"].to_numpy()

    def process_bars(self):
        """Default 'bar-by-bar' loop. Child classes override or define their own approach."""
        for i in range(len(self.close_prices)):
            self.process_bar(i)

    def process_bar(self, i):
        """Must be implemented in child class if using single-pass logic."""
        raise NotImplementedError(
            "The 'process_bar' method must be implemented in the strategy class."
        )

    def get_results(self):
        return self.data


class LinearRegressionOscillatorStrategy(BarByBarProcessor):
    def __init__(self, data, length, upper_threshold, lower_threshold):
        super().__init__(data)

        self.length = length
        self.upper_threshold = upper_threshold
        self.lower_threshold = lower_threshold

        # Prepare columns
        self.data["Signal"] = None
        self.data["LRO"] = np.nan
        self.data["Normalized LRO"] = np.nan
        self.data["Invalidation"] = np.nan
        self.data["CrossUnder"] = False
        self.data["CrossOver"] = False
        self.data["Reversion_Sell"] = False
        self.data["Reversion_Buy"] = False

        # Arrays for raw & normalized oscillator
        self.lro = np.full(len(self.close_prices), np.nan)
        self.normalized_lro = np.full(len(self.close_prices), np.nan)

        # If you want to replicate `source = close[barstate.isconfirmed ? 0 : 1]`,
        # shift the last bar’s close. Otherwise, for historical data, just use close.
        self.source = self.close_prices.copy()

        # In Pine Script, bar_index typically starts at 0 on the leftmost bar:
        self.bar_index = np.arange(len(self.close_prices))

    def calculate_linear_regression_oscillator(self, i):
        """
        Equivalent to Pine Script's 'linear_regression_osc(length)' function
        but done for bar i. No rounding, to keep full precision.
        """
        n = self.length
        if i < n - 1:
            return np.nan  # Not enough bars

        sum_x = 0.0
        sum_y = 0.0
        sum_xy = 0.0
        sum_x_sq = 0.0

        # Summation for the last n bars
        for j in range(n):
            x = j
            y = self.source[i - j]
            sum_x += x
            sum_y += y
            sum_xy += x * y
            sum_x_sq += x * x

        denom = (n * sum_x_sq) - (sum_x**2)
        if denom == 0:
            return np.nan

        m = (n * sum_xy - sum_x * sum_y) / denom
        c = (sum_y - m * sum_x) / n

        # In Pine: linear_regression = -(m * bar_index + c)
        return -(m * self.bar_index[i] + c)

    def pass1_compute_raw_lro(self):
        """Compute the entire raw LRO array first (like Pine Script does)."""
        for i in range(len(self.close_prices)):
            self.lro[i] = self.calculate_linear_regression_oscillator(i)

    def pass2_normalize_lro(self):
        """
        Compute the entire normalized LRO array using a rolling 100-bar window.
        Matches: (lro - ta.sma(lro,100)) / ta.stdev(lro,100).
        """
        n_norm = 100
        for i in range(len(self.close_prices)):
            if i < n_norm - 1:
                # Not enough bars for a 100-bar window
                self.normalized_lro[i] = np.nan
                continue

            window = self.lro[i - n_norm + 1 : i + 1]
            sma_lro = np.mean(window)
            stdev_lro = np.std(window, ddof=1)  # sample stdev => ddof=1
            if stdev_lro == 0:
                self.normalized_lro[i] = 0.0
            else:
                self.normalized_lro[i] = (self.lro[i] - sma_lro) / stdev_lro

    def pass3_detect_signals(self):
        """
        Replicates the Pine Script logic for crosses, threshold signals,
        AND the special 'diamond' reversion markers exactly.
        """
        n_norm = 100
        min_required_index = max(self.length + n_norm - 2, n_norm - 1)

        for i in range(len(self.close_prices)):
            if i < min_required_index or np.isnan(self.normalized_lro[i]):
                continue

            curr_lro  = self.lro[i]
            curr_norm = self.normalized_lro[i]

            # ----------------------------
            # 1) Zero cross detection
            # ----------------------------
            if i > 0 and not np.isnan(self.normalized_lro[i - 1]):
                prev_norm_lro = self.normalized_lro[i - 1]
                cond_crossunder = (prev_norm_lro > 0 and curr_norm <= 0)
                cond_crossover  = (prev_norm_lro < 0 and curr_norm >= 0)
            else:
                cond_crossunder = False
                cond_crossover  = False

            self.data.at[self.data.index[i], "CrossUnder"] = cond_crossunder
            self.data.at[self.data.index[i], "CrossOver"]  = cond_crossover

            # ----------------------------
            # 2) Basic threshold signals
            # ----------------------------
            signal = "Neutral"
            if cond_crossunder:
                signal = "CrossUnder_Sell"
            elif cond_crossover:
                signal = "CrossOver_Buy"
            elif curr_norm > self.upper_threshold:
                signal = "Sell"
            elif curr_norm < self.lower_threshold:
                signal = "Buy"

            # ----------------------------
            # 3) Reversion Markers (diamonds)
            # Replicate EXACT Pine logic:
            #
            # cond_1 = ta.crossunder(osc, osc[2]) and osc > upper ? osc[1] : na
            # plotchar(cond_1, "", "◇", offset = -1)
            #
            # => Means on bar i:
            #    a) crossunder => osc[i-1] >= osc[i-3], osc[i] < osc[i-2]
            #    b) osc[i] > upper
            #    c) We "plot" diamond on bar i-1 at y=osc[i-1]
            #
            # cond_2 = ta.crossover(osc, osc[2]) and osc < lower ? osc[1] : na
            # => Means on bar i:
            #    a) crossover => osc[i-1] <= osc[i-3], osc[i] > osc[i-2]
            #    b) osc[i] < lower
            #    c) We "plot" diamond on bar i-1 at y=osc[i-1]
            # ----------------------------
            if i >= 2:
                # The oscillator 2 bars ago is at i-2
                # The previous bar's oscillator is i-1
                # The "2 bars ago" previous bar's oscillator is i-3
                # Make sure we don't go out of range => i-3 >= 0 => i >= 3
                prev_osc = self.normalized_lro[i - 1]   # osc[i-1]
                prev2_osc= self.normalized_lro[i - 2]   # osc[i-2]
                prev_osc_2bars = (self.normalized_lro[i - 3] if (i - 3 >= 0) else np.nan)

                # Pine crossunder(osc, osc[2]) => was >=, now <
                crossunder2 = (
                    not np.isnan(prev_osc) and not np.isnan(prev_osc_2bars) and not np.isnan(prev2_osc)
                    and (prev_osc >= prev_osc_2bars)  # i-1 >= i-3
                    and (curr_norm < prev2_osc)        # i < i-2
                )
                # Pine crossunder condition also requires osc[i] > upper
                # so "the current bar's oscillator" is still above threshold
                if crossunder2 and (curr_norm > self.upper_threshold):
                    # Place diamond marker on bar i-1 at y= prev_osc
                    if i - 1 >= 0:
                        self.data.at[self.data.index[i - 1], "Reversion_Sell"] = True
                        # If you want to store the y-value for plotting:
                        self.data.at[self.data.index[i - 1], "Reversion_Sell_Val"] = prev_osc
                    signal = "Reversion_Sell"

                # Pine crossover(osc, osc[2]) => was <=, now >
                crossover2 = (
                    not np.isnan(prev_osc) and not np.isnan(prev_osc_2bars) and not np.isnan(prev2_osc)
                    and (prev_osc <= prev_osc_2bars)   # i-1 <= i-3
                    and (curr_norm > prev2_osc)        # i > i-2
                )
                # Pine crossover condition also requires osc[i] < lower
                if crossover2 and (curr_norm < self.lower_threshold):
                    # Place diamond marker on bar i-1 at y= prev_osc
                    if i - 1 >= 0:
                        self.data.at[self.data.index[i - 1], "Reversion_Buy"] = True
                        self.data.at[self.data.index[i - 1], "Reversion_Buy_Val"] = prev_osc
                    signal = "Reversion_Buy"

            # ----------------------------
            # 4) Invalidation levels (5-bar lookback)
            # ----------------------------
            if i >= 4:
                if cond_crossunder:
                    invalidation = np.max(self.high_prices[i - 4 : i + 1])
                    self.data.at[self.data.index[i], "Invalidation"] = invalidation
                elif cond_crossover:
                    invalidation = np.min(self.low_prices[i - 4 : i + 1])
                    self.data.at[self.data.index[i], "Invalidation"] = invalidation

            # ----------------------------
            # 5) Store final oscillator values & signal
            # ----------------------------
            self.data.at[self.data.index[i], "Signal"] = signal
            self.data.at[self.data.index[i], "LRO"] = curr_lro
            self.data.at[self.data.index[i], "Normalized LRO"] = curr_norm

    def process_bars(self):
        """
        This overrides the parent method to do a TWO-PASS approach:
          1) Compute raw LRO for all bars
          2) Normalize LRO for all bars
          3) Detect signals for all bars
        """
        self.pass1_compute_raw_lro()
        self.pass2_normalize_lro()
        self.pass3_detect_signals()

    def get_results(self):
        return self.data


if __name__ == "__main__":
    exchange = ccxt.bybit(
        {
            "options": {"defaultType": "future", "defaultSubType": "linear"},
            "rateLimit": 1200,
            "enableRateLimit": True,
        }
    )

    symbol = "ETH/USDT"
    timeframe = "1h"
    start_date = "2025-01-01T00:00:00Z"
    end_date = None
    df = fetch_and_prepare_data(
        exchange, symbol, timeframe, start_date=start_date, end_date=end_date
    )

    # Ensure data is sorted chronologically
    df.sort_values("Date", inplace=True)

    # Initialize and run our TWO-PASS strategy
    strategy = LinearRegressionOscillatorStrategy(
        df, length=20, upper_threshold=1.5, lower_threshold=-1.5
    )
    strategy.process_bars()  # calls pass1, pass2, pass3
    processed_data = strategy.get_results()
    print(processed_data)
    # Select the last 200 data points for plotting
    df_last200 = processed_data.tail(400)

    # Identify events for markers
    cross_over = df_last200[df_last200["CrossOver"] == True]
    cross_under = df_last200[df_last200["CrossUnder"] == True]
    reversion_buy = df_last200[df_last200["Reversion_Buy"] == True]
    reversion_sell = df_last200[df_last200["Reversion_Sell"] == True]
# 1) Create subplots with two rows (OHLC on top, oscillator on bottom)
fig = make_subplots(
    rows=2,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.02,
    row_heights=[0.7, 0.3],
    subplot_titles=("OHLC Chart", "Normalized LRO"),
)

# ----------------------------------------------------------------
# 2) TOP CHART (row=1): Candlestick + Invalidation Lines
# ----------------------------------------------------------------
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

if "Invalidation" in df_last200.columns:
    inv_levels = df_last200["Invalidation"].dropna()
    if not inv_levels.empty:
        fig.add_trace(
            go.Scatter(
                x=inv_levels.index,
                y=inv_levels,
                mode="lines+markers",
                line=dict(color="white", dash="dot"),  # White or any bright color
                name="Invalidation",
            ),
            row=1,
            col=1,
        )

# ----------------------------------------------------------------
# 3) BOTTOM CHART (row=2): Oscillator with "Area" Fill
# ----------------------------------------------------------------
osc_values = df_last200["Normalized LRO"].values
x_values = df_last200.index

# Split the oscillator into positive part (above 0) and negative part (below 0)
y_pos = [val if val > 0 else 0 for val in osc_values]
y_neg = [val if val < 0 else 0 for val in osc_values]

# (A) Fill area above zero
fig.add_trace(
    go.Scatter(
        x=x_values,
        y=y_pos,
        fill="tozeroy",  # Fill down to y=0
        mode="none",  # No line or markers
        fillcolor="rgba(16,202,184,0.6)",  # A teal color with some transparency
        name="Osc > 0",
    ),
    row=2,
    col=1,
)

# (B) Fill area below zero
fig.add_trace(
    go.Scatter(
        x=x_values,
        y=y_neg,
        fill="tozeroy",  # Fill up to y=0 (since y_neg is negative)
        mode="none",
        fillcolor="rgba(0,128,255,0.6)",  # A bluish color with some transparency
        name="Osc < 0",
    ),
    row=2,
    col=1,
)

# (C) White line overlaid on top so you can see the actual oscillator path
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

# (D) Threshold lines
fig.add_trace(
    go.Scatter(
        x=x_values,
        y=[1.5] * len(x_values),
        mode="lines",
        line=dict(color="red", dash="dash"),
        name="Upper Threshold (1.5)",
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
        name="Lower Threshold (-1.5)",
    ),
    row=2,
    col=1,
)

# (Optional) If you want the zero line, uncomment below:
# fig.add_trace(
#     go.Scatter(
#         x=x_values,
#         y=[0]*len(x_values),
#         mode='lines',
#         line=dict(color='gray', dash='dot'),
#         name='Zero Line (0)'
#     ),
#     row=2, col=1
# )

# (E) Markers for CrossOver, CrossUnder, etc.
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
# For Reversion Sell
reversion_sell_df = df_last200[df_last200['Reversion_Sell'] == True]
fig.add_trace(
    go.Scatter(
        x=reversion_sell_df.index,
        y=reversion_sell_df['Reversion_Sell_Val'],  # The oscillator's value from bar i-1
        mode='markers',
        marker=dict(color='red', symbol='diamond', size=10),
        name='Reversion Sell'
    ),
    row=2, col=1
)

# For Reversion Buy
reversion_buy_df = df_last200[df_last200['Reversion_Buy'] == True]
fig.add_trace(
    go.Scatter(
        x=reversion_buy_df.index,
        y=reversion_buy_df['Reversion_Buy_Val'],
        mode='markers',
        marker=dict(color='lime', symbol='diamond', size=10),
        name='Reversion Buy'
    ),
    row=2, col=1
)

# ----------------------------------------------------------------
# 4) Layout: Make the background black, text/axes white, etc.
# ----------------------------------------------------------------
fig.update_layout(
    title="OHLC Chart with Dark Background & Area-Filled Oscillator",
    height=800,
    legend_title="Legend",
    paper_bgcolor="black",  # Overall figure background
    plot_bgcolor="black",  # Plot area background
    font_color="white",  # Legend and title text color
)

# Make grid lines gray, axes text white
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
