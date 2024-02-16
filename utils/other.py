import backtrader as bt 

class CCXTData(bt.feeds.PandasData):
    """
    Define a new data feed for Backtrader which is compatible with the data structure
    returned by CCXT
    """
    params = (
        ('open', 'Open'),
        ('high', 'High'),
        ('low', 'Low'),
        ('close', 'Close'),
        ('volume', 'Volume'),
        ('openinterest', None),
    )