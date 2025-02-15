import pandas as pd
import numpy as np
import ccxt
from utils.dataManipulation import fetch_and_prepare_data
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots

class BarByBarProcessor:
    def __init__(self, data):
        self.data = data.copy()
        self.data['Signal'] = None

        self.close_prices = self.data['Close'].to_numpy()
        self.open_prices = self.data['Open'].to_numpy()
        self.high_prices = self.data['High'].to_numpy()
        self.low_prices = self.data['Low'].to_numpy()
        self.volume = self.data['Volume'].to_numpy()

    def process_bars(self):
        for i in range(len(self.close_prices)):
            self.process_bar(i)

    def process_bar(self, i):
        raise NotImplementedError("The 'process_bar' method must be implemented in the strategy class.")

    def get_results(self):
        return self.data

class LinearRegressionOscillatorStrategy(BarByBarProcessor):
    def __init__(self, data, length, upper_threshold, lower_threshold):
        super().__init__(data)
        self.length = length
        self.upper_threshold = upper_threshold
        self.lower_threshold = lower_threshold

        self.data['LRO'] = np.nan
        self.data['Normalized LRO'] = np.nan
        self.lro = np.full(len(self.close_prices), np.nan)
        self.normalized_lro = np.full(len(self.close_prices), np.nan)

        # Initialize source array similar to Pine Script
        self.source = self.close_prices.copy()
        self.bar_index = np.arange(len(self.close_prices))  # Equivalent to Pine Script's bar_index

    def calculate_linear_regression_oscillator(self, i):
        n = self.length
        if i < n - 1:
            return None  # Not enough data to calculate

        sum_x = 0.0
        sum_y = 0.0
        sum_xy = 0.0
        sum_x_squared = 0.0

        # Replicating Pine Script's loop and indexing
        for j in range(n):
            x = j  # x ranges from 0 to n - 1
            y = self.source[i - j]  # Accessing data from current bar backward
            sum_x += x
            sum_y += y
            sum_xy += x * y
            sum_x_squared += x ** 2

        # Calculate slope (m) and intercept (c)
        denominator = n * sum_x_squared - sum_x ** 2
        if denominator == 0:
            return None  # Avoid division by zero

        m = (n * sum_xy - sum_x * sum_y) / denominator
        c = (sum_y - m * sum_x) / n

        # Calculate linear regression oscillator value (equivalent to Pine Script)
        bar_idx = self.bar_index[i]
        linear_regression = - (m * bar_idx + c)

        # Round to 3 decimal places
        linear_regression = round(linear_regression, 3)

        return linear_regression

    @staticmethod
    def crossunder(prev_series, curr_series):
        return prev_series > 0 and curr_series <= 0

    @staticmethod
    def crossover(prev_series, curr_series):
        return prev_series < 0 and curr_series >= 0


    def process_bar(self, i):
        """Processes a single bar for the Linear Regression Oscillator strategy."""
        # Ensure sufficient history is available
        n_norm = 100  # Normalization period
        min_required_index = max(self.length + n_norm - 2, n_norm - 1)
        if i < min_required_index:
            return

        # Step 1: Calculate Linear Regression Oscillator (LRO) for the current bar
        lro = self.calculate_linear_regression_oscillator(i)
        if lro is None:
            return

        self.lro[i] = lro

        # Step 2: Normalize LRO
        sma_lro = np.mean(self.lro[i - n_norm + 1:i + 1])
        stdev_lro = np.std(self.lro[i - n_norm + 1:i + 1], ddof=1)

        # Round SMA and standard deviation to 3 decimal places
        sma_lro = round(sma_lro, 3)
        stdev_lro = round(stdev_lro, 3)

        if stdev_lro != 0:
            normalized_lro = (lro - sma_lro) / stdev_lro
        else:
            normalized_lro = 0.0  # Avoid division by zero

        # Round normalized LRO to 3 decimal places
        normalized_lro = round(normalized_lro, 3)
        self.normalized_lro[i] = normalized_lro

        # Step 3: Check for crossunder and crossover with zero on normalized LRO
        if i > 0 and self.normalized_lro[i - 1] is not None:
            prev_norm_lro = self.normalized_lro[i - 1]
            # Crossunder: Previous normalized LRO > 0 and Current normalized LRO <= 0
            cond1 = prev_norm_lro > 0 and normalized_lro <= 0
            # Crossover: Previous normalized LRO < 0 and Current normalized LRO >= 0
            cond2 = prev_norm_lro < 0 and normalized_lro >= 0
        else:
            cond1 = False
            cond2 = False

        # Identifiy reversion
        #TODO maker reversions here
        if i > self.normalized_lro[i-1] is not None:
            prev_norm_lro = self.normalized_lro[i-0]
            # cond3 = 

        # Optionally, store the conditions in the DataFrame
        self.data.at[self.data.index[i], 'CrossUnder'] = cond1
        self.data.at[self.data.index[i], 'CrossOver'] = cond2

        # Step 4: Assign signals based on normalized LRO thresholds
        if cond1:
            self.data.at[self.data.index[i], 'Signal'] = 'CrossUnder_Sell'
        elif cond2:
            self.data.at[self.data.index[i], 'Signal'] = 'CrossOver_Buy'
        elif normalized_lro > self.upper_threshold:
            self.data.at[self.data.index[i], 'Signal'] = 'Sell'
        elif normalized_lro < self.lower_threshold:
            self.data.at[self.data.index[i], 'Signal'] = 'Buy'
        else:
            self.data.at[self.data.index[i], 'Signal'] = 'Neutral'

        # Step 5: Save the LRO and normalized LRO for this bar into the DataFrame
        self.data.at[self.data.index[i], 'LRO'] = self.lro[i]
        self.data.at[self.data.index[i], 'Normalized LRO'] = self.normalized_lro[i]


    def get_results(self):
        return self.data


if __name__ == "__main__":
    exchange = ccxt.bybit({
        'options': {
            'defaultType': 'future',
            'defaultSubType': 'linear'
        },
        'rateLimit': 1200,
        'enableRateLimit': True,
    })

    symbol = "ETH/USDT"
    timeframe = "1h"
    start_date = "2025-01-01T00:00:00Z"
    end_date = None
    df = fetch_and_prepare_data(exchange, symbol, timeframe, start_date=start_date, end_date=end_date)

    # Ensure data is sorted correctly
    df.sort_values('Date', inplace=True)

    # Initialize and process Linear Regression Oscillator Strategy
    strategy = LinearRegressionOscillatorStrategy(
        df,
        length=20,
        upper_threshold=1.5,
        lower_threshold=-1.5
    )
    strategy.process_bars()

    # Get and print results
    processed_data = strategy.get_results()
    print(processed_data.tail(20))


    # Select the last 200 data points
    # Select the last 200 data points
    df_last200 = processed_data.tail(200)

        # Identify CrossOver events
    cross_over = df_last200[df_last200['CrossOver'] == True]
    # Identify CrossUnder events
    cross_under = df_last200[df_last200['CrossUnder'] == True]


    # Create subplots with shared x-axis
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.02,
                        row_heights=[0.7, 0.3])  # Adjust heights as needed

    # Add OHLC candlestick chart
    fig.add_trace(go.Candlestick(
        x=df_last200.index,
        open=df_last200['Open'],
        high=df_last200['High'],
        low=df_last200['Low'],
        close=df_last200['Close'],
        name='OHLC'
    ), row=1, col=1)

    # Add 'Normalized LRO' line in the second subplot
    fig.add_trace(go.Scatter(
        x=df_last200.index,
        y=df_last200['Normalized LRO'],
        mode='lines+markers',
        name='Normalized LRO'
    ), row=2, col=1)

    # Add upper threshold line
    fig.add_trace(go.Scatter(
        x=df_last200.index,
        y=[1.5]*len(df_last200),
        mode='lines',
        line=dict(color='red', dash='dash'),
        name='Upper Threshold (1.5)'
    ), row=2, col=1)

    # Add lower threshold line
    fig.add_trace(go.Scatter(
        x=df_last200.index,
        y=[-1.5]*len(df_last200),
        mode='lines',
        line=dict(color='green', dash='dash'),
        name='Lower Threshold (-1.5)'
    ), row=2, col=1)

    # Update layout
    fig.update_layout(
        title='OHLC Chart with Normalized LRO Indicator',
        xaxis=dict(
            rangeslider=dict(visible=False)
        ),
        xaxis2=dict(
            tickangle=45,
            tickformat='%Y-%m-%d %H:%M:%S'
        ),
        yaxis_title='Price',
        yaxis2_title='Normalized LRO',
        legend_title='Legend',
        template='plotly_white',
        height=800
    )

    # Add zero line at y=0
    fig.add_trace(go.Scatter(
        x=df_last200.index,
        y=[0]*len(df_last200),
        mode='lines',
        line=dict(color='blue', dash='dot'),
        name='Zero Line (0)'
    ), row=2, col=1)


    # Add markers for CrossOver events
    fig.add_trace(go.Scatter(
        x=cross_over.index,
        y=cross_over['Normalized LRO'],
        mode='markers',
        marker=dict(color='green', symbol='triangle-up', size=10),
        name='CrossOver'
    ), row=2, col=1)

    # Add markers for CrossUnder events
    fig.add_trace(go.Scatter(
        x=cross_under.index,
        y=cross_under['Normalized LRO'],
        mode='markers',
        marker=dict(color='red', symbol='triangle-down', size=10),
        name='CrossUnder'
    ), row=2, col=1)


    # Show the figure
    fig.show()