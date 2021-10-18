import numpy as np
import pandas as pd

from .pair import TimePair
from .block import TimeBlock
from .side import PanelSide


def from_pairs(pairs):
    if len(pairs) == 0:
        raise ValueError("Cannot build TimePanel from empty list")
    blocks = [(pair.x, pair.y) for pair in pairs]
    x = PanelSide([block[0] for block in blocks])
    y = PanelSide([block[1] for block in blocks])
    return TimePanel(x, y)


def from_xy_data(x, y, lookback, horizon, gap=0):

    x_timesteps = len(x.index)

    if x_timesteps - lookback - horizon - gap <= -1:
        raise ValueError("Not enough timesteps to build")

    end = x_timesteps - horizon - gap + 1

    # Get units and channels
    # x = TimeBlock(x)
    # y = TimeBlock(y)

    indexes = np.arange(lookback, end)
    xblocks, yblocks = [], []

    for i in indexes:
        xblocks.append(x.iloc[i - lookback : i])
        yblocks.append(y.iloc[i + gap : i + gap + horizon])


    return TimePanel(PanelSide(xblocks), PanelSide(yblocks))


def from_data(
        df,
        lookback,
        horizon,
        gap=0,
        x_assets=None,
        y_assets=None,
        x_channels=None,
        y_channels=None
        ):

    df = TimeBlock(df)
    xdata = df.filter(x_assets, x_channels)
    ydata = df.filter(y_assets, y_channels)
    return from_xy_data(xdata, ydata, lookback, horizon, gap)


class TimePanel:

    DIMS = ("size", "assets", "timesteps", "channels")

    def __init__(self, x, y):
        self._x, self._y = x, y
        self.train_size, self.val_size, self.test_size = None, None, None

        # freq checks
        # if x.isnull().values.any() or y.isnull().values.any():
        #     warnings.warn("Data contains null values.")

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    @x.setter
    def x(self, value):
        if not isinstance(value, PanelSide):
            raise ValueError("'x' must be of type PanelSide")
        if len(value) != len(self.x):
            raise ValueError("'x' must keep the same length")
        self._x = value

    @y.setter
    def y(self, value):
        if not isinstance(value, PanelSide):
            raise ValueError("'y' must be of type PanelSide")
        if len(value) != len(self.y):
            raise ValueError("'y' must keep the same length")
        self._y = value

    @property
    def pairs(self):
        return [TimePair(x, y) for x, y in zip(self.x.blocks, self.y.blocks)]

    @property
    def lookback(self):
        return len(self.x.first)

    @property
    def horizon(self):
        return len(self.y.first)

    @property
    def shape(self):
        return pd.DataFrame([self.x.shape, self.y.shape], index=["x", "y"], columns=self.DIMS)

    @property
    def start(self):
        return self.x.start

    @property
    def end(self):
        return self.y.end

    @property
    def index(self):
        return sorted(list(set(self.x.index + self.y.index)))

    def apply(self, func, axis):
        x = self.x.apply(func=func, axis=axis)
        y = self.y.apply(func=func, axis=axis)
        return TimePanel(x, y)

    def dropna(self, x=True, y=True):
        x_nan = self.x.findna() if x else []
        y_nan = self.y.findna() if y else []
        idx = tuple(i for i in range(len(self)) if i not in set(x_nan + y_nan))
        if not idx:
            raise ValueError("'dropna' would create empty TimePanel")
        return self[idx]

    def __repr__(self):
        summary = pd.Series(
            {
                "size": self.__len__(),
                "lookback": self.lookback,
                "horizon": self.horizon,
                # "gap": self.gap,
                "num_xassets": len(self.x.assets),
                "num_yassets": len(self.y.assets),
                "num_xchannels": len(self.x.channels),
                "num_ychannels": len(self.y.channels),
                "start": self.x.start,
                "end": self.y.end,
            },
            name="TimePanel")

        print(summary)
        return f"<TimePanel, size {self.__len__()}>"

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, key):
        if isinstance(key, tuple):
            return from_pairs([pair for i, pair in enumerate(self.pairs) if i in key])
        return self.pairs[key]

