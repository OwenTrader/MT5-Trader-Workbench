import backtrader as bt


STRATEGY_ID = 'macd_trend'
STRATEGY_NAME = 'MACD Trend Momentum'
STRATEGY_DESCRIPTION = 'MACD trend following strategy. Fast/slow line cross with zero-line confirmation.'
SUPPORTED_TIMEFRAMES = ['M5', 'M15', 'M30', 'H1', 'H4', 'D1']


class Strategy(bt.Strategy):
    params = (('fast', 12), ('slow', 26), ('signal', 9))

    def __init__(self):
        self.macd = bt.ind.MACD(
            self.data.close,
            period_me1=self.p.fast,
            period_me2=self.p.slow,
            period_signal=self.p.signal,
        )
        self.cross = bt.ind.CrossOver(self.macd.macd, self.macd.signal)
        self.signal_output = 'hold'

    def next(self):
        if self.cross[0] > 0 and self.macd.macd[0] > 0:
            self.signal_output = 'buy'
        elif self.cross[0] < 0 and self.macd.macd[0] < 0:
            self.signal_output = 'sell'
        elif self.cross[0] < 0 and self.signal_output == 'buy':
            self.signal_output = 'close'
        else:
            self.signal_output = 'hold'
