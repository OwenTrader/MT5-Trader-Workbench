import backtrader as bt


STRATEGY_ID = 'bollinger_breakout'
STRATEGY_NAME = 'Bollinger Volatility Breakout'
STRATEGY_DESCRIPTION = 'Bollinger Bands breakout strategy. Enters on upper/lower band expansion and exits on middle band.'
SUPPORTED_TIMEFRAMES = ['M5', 'M15', 'M30', 'H1', 'H4']


class Strategy(bt.Strategy):
    params = (('period', 20), ('devfactor', 2.0))

    def __init__(self):
        self.bb = bt.ind.BollingerBands(
            self.data.close,
            period=self.p.period,
            devfactor=self.p.devfactor,
        )
        self.signal_output = 'hold'

    def next(self):
        if self.data.close[0] > self.bb.lines.top[0]:
            self.signal_output = 'buy'
        elif self.data.close[0] < self.bb.lines.bot[0]:
            self.signal_output = 'sell'
        elif self.data.close[0] < self.bb.lines.mid[0] and self.signal_output == 'buy':
            self.signal_output = 'close'
        else:
            self.signal_output = 'hold'
