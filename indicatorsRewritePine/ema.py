import sys
import os
import pandas
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import numpy as np


def calculate_ema_pine(df, column, length):
    alpha = 2 / (length + 1)
    close_prices = df[column].values
    ema = np.zeros_like(close_prices)
    ema[0] = close_prices[0]
    for i in range(1, len(close_prices)):
        ema[i] = alpha * close_prices[i] + (1 - alpha) * ema[i - 1]
    return ema


def add_multiple_emas(df: pandas.DataFrame , column:str = 'Close', lengths: list = [20, 50, 200]):
    """
    Adds multiple emas to the dataframe 
    df = dataframe
    column to apply ema to = Close, High, Low, etc.
    lengths  of emas 
    """
    for length in lengths:
        ema_column_name = f'EMA_{length}'
        df[ema_column_name] = calculate_ema_pine(df, column, length)
    return df