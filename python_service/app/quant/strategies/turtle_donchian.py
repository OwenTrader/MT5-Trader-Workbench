import backtrader as bt


STRATEGY_ID = 'turtle_donchian'
STRATEGY_NAME = 'Turtle Donchian Breakout'
STRATEGY_DESCRIPTION = 'Turtle trading 20-period channel breakout with 10-period trailing exit.'
SUPPORTED_TIMEFRAMES = ['M15', 'M30', 'H1', 'H4', 'D1']


class Strategy(bt.Strategy):
    params = (('entry_period', 20), ('exit_period', 10))

    def __init__(self):
        self.entry_high = bt.ind.Highest(self.data.high, period=self.p.entry_period)
        self.exit_low = bt.ind.Lowest(self.data.low, period=self.p.exit_period)
        self.signal_output = 'hold'

    def next(self):
        if len(self.data) <= self.p.entry_period:
            self.signal_output = 'hold'
            return

        if self.data.close[0] > self.entry_high[-1]:
            self.signal_output = 'buy'
        elif self.data.close[0] < self.exit_low[-1]:
            self.signal_output = 'close'
        else:
            self.signal_output = 'hold'
