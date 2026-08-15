import backtrader as bt


STRATEGY_ID = 'dual_thrust'
STRATEGY_NAME = 'Dual Thrust Range Breakout'
STRATEGY_DESCRIPTION = 'Classic Dual Thrust intraday range breakout system calculating asymmetric trigger bands.'
SUPPORTED_TIMEFRAMES = ['M15', 'M30', 'H1', 'H4', 'D1']


class Strategy(bt.Strategy):
    params = (('period', 20), ('k1', 0.5), ('k2', 0.5))

    def __init__(self):
        self.highest = bt.ind.Highest(self.data.high, period=self.p.period)
        self.lowest = bt.ind.Lowest(self.data.low, period=self.p.period)
        self.signal_output = 'hold'

    def next(self):
        if len(self.data) <= self.p.period:
            self.signal_output = 'hold'
            return

        range_val = self.highest[-1] - self.lowest[-1]
        buy_trig = self.data.open[0] + self.p.k1 * range_val
        sell_trig = self.data.open[0] - self.p.k2 * range_val

        if self.data.close[0] > buy_trig:
            self.signal_output = 'buy'
        elif self.data.close[0] < sell_trig:
            self.signal_output = 'sell'
        else:
            self.signal_output = 'hold'
