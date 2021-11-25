import functools
from collections import OrderedDict

import numpy as np
import pandas as pd

from .utils import add_dim


def from_dataframe(df):
    # Recreate columns to avoid pandas issue
    return TimeBlock(
        pd.DataFrame(
            df.values,
            index=df.index,
            columns=df.columns,
        )
    )


def from_dataframes(data):
    """
    Generate a TimeBlock from a list of dataframes.

    Parameters:
    -----------
    data: list of dataframes or dict of dataframes with assets as keys

    """
    if isinstance(data, list):
        data = {"asset_" + str(k): v for k, v in enumerate(data)}
    return TimeBlock(pd.concat(data.values(), axis=1, keys=data.keys()))


def from_array(values, index=None, assets=None, channels=None):

    values = add_dim(values, n=3 - len(values.shape))
    if assets is None:
        assets = range(values.shape[0])
    if index is None:
        index = range(values.shape[1])
    if channels is None:
        channels = range(values.shape[2])

    columns = pd.MultiIndex.from_product([assets, channels])
    df = pd.DataFrame(index=index, columns=columns)
    df.loc[:, (slice(None), slice(None))] = values.reshape(df.shape)
    return TimeBlock(df)


def rebuild(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        df = func(*args, **kwargs)
        return from_dataframe(df)

    return wrapper


class AssetSeries(pd.Series):
    def __init__(self, df, *args, **kwargs):
        super().__init__(df, *args, **kwargs)

    @property
    def _constructor_expanddim(self):
        return TimeBlock

    @property
    def _constructor(self):
        return AssetSeries


class TimeBlock(pd.DataFrame):
    def __init__(self, df, *args, **kwargs):
        super().__init__(df, *args, **kwargs)

    def __eq__(self, other):
        if not isinstance(other, TimeBlock):
            raise TypeError("'other' must be of type TimeBlock")
        return np.all(self.fillna(0).values == other.fillna(0).values)

    @property
    def _constructor(self):
        return TimeBlock

    @property
    def _constructor_sliced(self):
        return AssetSeries

    @property
    def start(self):
        return self.index[0]

    @property
    def end(self):
        return self.index[-1]

    @property
    def assets(self):
        assets = [col[0] for col in self.columns]
        # OrderedDict to keep order
        return pd.Series(tuple(OrderedDict.fromkeys(assets)))

    @property
    def channels(self):
        channels = [col[1] for col in self.columns]
        # OrderedDict to keep order
        return pd.Series(list(OrderedDict.fromkeys(channels)))

    @rebuild
    def filter(self, assets=None, channels=None):
        filtered = self.filter_assets(assets)
        filtered = filtered.filter_channels(channels)
        return filtered

    @rebuild
    def filter_assets(self, assets):
        if type(assets) == str:
            assets = [assets]

        # if assets is not None and any(asset not in self.columns.levels[0] for asset in assets):
        #     raise ValueError(f"{assets} not found in columns. Columns: {list(self.columns.levels[0])}")

        return self.loc[:, (assets, slice(None))] if assets else self

    @rebuild
    def filter_channels(self, channels):
        if type(channels) == str:
            channels = [channels]

        # if channels is not None and any(channel not in self.columns.levels[1] for channel in channels):
        #     raise ValueError(f"{channels} not found in columns. Columns:{list(self.columns.levels[1])}")

        return self.loc[:, (slice(None), channels)][self.assets] if channels else self

    def add_level(df, level_name):
        return pd.concat({level_name: df.T}, names=[level_name]).T

    def drop(self, assets=None, channels=None):
        filtered = self.drop_assets(assets)
        filtered = filtered.drop_channels(channels)
        return filtered

    def drop_assets(self, assets):
        if isinstance(assets, str):
            assets = [assets]
        new_assets = [u for u in self.assets if u not in assets]
        return self.filter_assets(new_assets)

    def drop_channels(self, channels):
        if isinstance(channels, str):
            channels = [channels]
        new_channels = [c for c in self.channels if c not in channels]
        return self.filter_channels(new_channels)

    def rename_assets(self, values, new_values):
        values = values if isinstance(values, list) else [values]
        new_values = new_values if isinstance(new_values, list) else [new_values]

        if len(values) != len(new_values):
            raise ValueError("'values' must have the same length as 'new_values'")

        assets = self.assets.replace(to_replace=values, value=new_values)
        return self.update(assets=assets.values)

    def rename_channels(self, values, new_values):
        values = values if isinstance(values, list) else [values]
        new_values = new_values if isinstance(new_values, list) else [new_values]

        if len(values) != len(new_values):
            raise ValueError("'values' must have the same length as 'new_values'")

        channels = self.channels.replace(to_replace=values, value=new_values)
        return self.update(channels=channels.values)

    def apply(self, func, axis=0):

        if axis == 0:
            return self._timestamp_apply(func)
        elif axis == 1:
            return self._channel_apply(func)

        raise ValueError(f"{axis} not acceptable for 'axis'. Available values are [0, 1]")

    def _timestamp_apply(self, func):
        df = self.pandas().apply(func, axis=0)
        if isinstance(df, pd.Series):
            return df.to_frame().T
        return df.T

    def _channel_apply(self, func):
        splits = self.split_assets()
        splits = [data.pandas().apply(func, axis=1).to_frame() for data in splits]
        splits = [from_array(data.values, index=data.index) for data in splits]
        splits = [data.rename_assets(0, asset) for data, asset in zip(splits, self.assets)]
        return pd.concat(splits).rename_channels(0, "new_channel")

    def update(self, values=None, index=None, assets=None, channels=None):
        values = values if values is not None else self.values
        assets = assets if assets is not None else self.assets
        index = index if index is not None else self.index
        channels = channels if channels is not None else self.channels
        return from_array(values, index, assets, channels)

    # @rebuild
    # def add_channel(self, name, values):
    #     for asset in self.assets:
    #         self.loc[:, (asset, name)] = values
    #     return self

    def split_assets(self):
        return [self.filter(asset) for asset in self.assets]

    def countna(self):
        s = pd.Series(dtype=int)
        for asset in self.assets:
            s[asset] = len(self[asset]) - len(self[asset].dropna())
        return s

    def pandas(self):
        return pd.DataFrame(self.values, index=self.index, columns=self.columns)

    def numpy(self):
        new_shape = (len(self), len(self.assets), len(self.channels))
        values = self.values.reshape(*new_shape)
        return values.transpose(1, 0, 2)
