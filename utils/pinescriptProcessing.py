
class PineScriptProcessing:
    def __init__(self, data):
        """
        Base processor for bar-by-bar data.

        Parameters:
        - data: pandas DataFrame with 'Open', 'High', 'Low', 'Close', 'Volume' columns.
        """
        self.data = data.copy()
        self.data['Signal'] = None  # Placeholder for any signal logic

        # Extract OHLCV as NumPy arrays
        self.close_prices = self.data['Close'].to_numpy()
        self.open_prices = self.data['Open'].to_numpy()
        self.high_prices = self.data['High'].to_numpy()
        self.low_prices = self.data['Low'].to_numpy()
        self.volume = self.data['Volume'].to_numpy()

    def process_bars(self):
        """Processes each bar sequentially."""
        for i in range(len(self.close_prices)):
            self.process_bar(i)

    def process_bar(self, i):
        """
        Processes a single bar. To be overridden by child classes.

        Parameters:
        - i: Index of the current bar.
        """
        raise NotImplementedError("The 'process_bar' method must be implemented in the strategy class.")

    def get_results(self):
        """Returns the processed DataFrame."""
        return self.data
        