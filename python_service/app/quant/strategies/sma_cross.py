import backtrader as bt


STRATEGY_ID = 'sma_cross'
STRATEGY_NAME = 'SMA Cross'
STRATEGY_DESCRIPTION = 'Fast/slow SMA crossover with one-position directional bias.'
SUPPORTED_TIMEFRAMES = ['M1', 'M5', 'M15', 'M30', 'H1']


class Strategy(bt.Strategy):
    params = (('fast', 10), ('slow', 30))

    def __init__(self):
        self.fast_sma = bt.ind.SMA(self.data.close, period=self.p.fast)
        self.slow_sma = bt.ind.SMA(self.data.close, period=self.p.slow)
        self.cross = bt.ind.CrossOver(self.fast_sma, self.slow_sma)
        self.signal_output = 'hold'

    def next(self):
        if self.cross[0] > 0:
            self.signal_output = 'buy'
        elif self.cross[0] < 0:
            self.signal_output = 'close'
        else:
            self.signal_output = 'hold'
