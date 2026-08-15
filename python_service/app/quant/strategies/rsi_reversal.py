import backtrader as bt


STRATEGY_ID = 'rsi_reversal'
STRATEGY_NAME = 'RSI Mean Reversion'
STRATEGY_DESCRIPTION = 'RSI dynamic mean reversion. Generates Buy on oversold (<30) and Close on overbought (>70).'
SUPPORTED_TIMEFRAMES = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1']


class Strategy(bt.Strategy):
    params = (('period', 14), ('oversold', 30), ('overbought', 70))

    def __init__(self):
        self.rsi = bt.ind.RSI(self.data.close, period=self.p.period)
        self.signal_output = 'hold'

    def next(self):
        if self.rsi[0] < self.p.oversold:
            self.signal_output = 'buy'
        elif self.rsi[0] > self.p.overbought:
            self.signal_output = 'close'
        else:
            self.signal_output = 'hold'
