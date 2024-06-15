from backtrader import Indicator
from backtrader.indicators import EMA, SMA


class WaveTrendMc(Indicator):
    """
    WaveTrend indicator enhanced with a horizontal line at level 0 for improved visuals,
    overbought and oversold level area lines, and detection of wt1 and wt2 crossovers. It is part of the market cypher b
    """

    lines = (
        "wt1",
        "wt2",
        "hz_line",
        "cross",
        "overbought",
        "overbought_extreme",
        "oversold",
        "oversold_extreme",
    )
    params = (
        ("n1", 9),
        ("n2", 12),
        ("overbought", 53),
        ("overbought_extreme", 60),
        ("oversold", -53),
        ("oversold_extreme", -60),
    )

    plotinfo = dict(subplot=True, plotlinelabels=True)
    plotlines = dict(
        hz_line=dict(color="gray"),  # 0 line color
        wt1=dict(color="lightblue"),  # Customize wt1 line color here
        wt2=dict(color="darkblue"),  # Customize wt2 line color here
        overbought=dict(color="red", ls="--"),  # Overbought line style
        overbought_extreme=dict(
            color="darkred", ls="--"
        ),  # Extreme overbought line style
        oversold=dict(color="green", ls="--"),  # Oversold line style
        oversold_extreme=dict(
            color="darkgreen", ls="--"
        ),  # Extreme oversold line style
    )

    def __init__(self):
        ap = (self.data.high + self.data.low + self.data.close) / 3
        esa = EMA(ap, period=self.p.n1)
        d = EMA(abs(ap - esa), period=self.p.n1)
        ci = (ap - esa) / (0.015 * d)
        self.lines.wt1 = EMA(ci, period=self.p.n2)
        self.lines.wt2 = SMA(self.lines.wt1, period=3)

    def next(self):
        # Update the hz_line value for each bar to 0
        self.lines.hz_line[0] = 0
        # Set overbought and oversold line values
        self.lines.overbought[0] = self.p.overbought
        self.lines.overbought_extreme[0] = self.p.overbought_extreme
        self.lines.oversold[0] = self.p.oversold
        self.lines.oversold_extreme[0] = self.p.oversold_extreme
