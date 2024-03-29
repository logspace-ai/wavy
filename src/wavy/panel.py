from __future__ import annotations

import random
import uuid
import warnings

import numpy as np
import pandas as pd
from pandas.core.groupby import DataFrameGroupBy

from wavy.plot import plot
from wavy.validations import _validate_sample_panel, _validate_training_split

warnings.simplefilter(action="ignore", category=FutureWarning)



def is_iterable(obj):
    try:
        iter(obj)
        return True
    except TypeError:
        return False


def make_xy(df, lookback, horizon, gap):
    x_frames = [frame for frame in df.iloc[:-horizon].rolling(lookback) if len(frame) == lookback]

    y_frames = [frame for frame in df.iloc[lookback:].rolling(horizon) if len(frame) == horizon]

    x_frames = x_frames[:len(y_frames)]
    y_frames = y_frames[:len(x_frames)]

    x_frames = x_frames[:-gap]
    y_frames = y_frames[gap:]

    return x_frames, y_frames


# def make_xy_by_timestamp(df, lookback, horizon):

#     # sourcery skip: identity-comprehension
#     # ! datetime gaps are not supported yet
#     x_frames = [frame for frame in df[df.index < (df.index[-1] - pd.Timedelta(horizon))].rolling(lookback)]

#     y_frames = [frame for frame in df[df.index > (df.index[0] + pd.Timedelta(lookback))].rolling(horizon)]

#     x_frames = x_frames[:len(y_frames)]
#     y_frames = y_frames[:len(x_frames)]

#     print(len(x_frames), len(y_frames))

#     return x_frames, y_frames


def get_ids(x_frames, y_frames):
    assert len(x_frames) == len(y_frames)
    return [str(uuid.uuid4()) for _ in range(len(x_frames))]


def create_panels(df, lookback, horizon, gap=None):
    # if isinstance(lookback, str) and isinstance(horizon, str):
    #     if gap:
    #         raise ValueError("Gap is not supported for datetime lookback and horizon.")
    #     x_frames, y_frames = make_xy_by_timestamp(df, lookback, horizon)
    # elif isinstance(lookback, int) and isinstance(horizon, int):
    gap = gap or 1
    x_frames, y_frames = make_xy(df, lookback, horizon, gap)
    ids = get_ids(x_frames, y_frames)

    # ?
    # timesteps_name = df.index.name or "timesteps"

    x_panel = pd.concat(x_frames, keys=ids)
    y_panel = pd.concat(y_frames, keys=ids)

    x_panel.index.names = ['ids', 'timesteps']
    y_panel.index.names = ['ids', 'timesteps']

    return Panel(x_panel), Panel(y_panel)

def match(x, y):
    """
    Drop frames with NaN in panels and match ids.

    Args:
        x (``Panel``): Panel with x data
        y (``Panel``): Panel with y data

    Returns:
        ``Panel``: Panel with dropped frames and matched ids
    """

    x_t = x.drop_empty_frames()
    y_t = y.match(x_t)

    y_t = y_t.drop_empty_frames()
    x_t = x_t.match(y_t)

    return x_t, y_t


def set_training_split(
    x: Panel,
    y: Panel,
    train_size: float | int = 0.7,
    val_size: float | int = 0.2,
    test_size: float | int = 0.1,
) -> None:
    """
    Splits panel in training, validation, and test.

    Args:
        train_size (``float`` or ``int``): Fraction of data to use for training.
        test_size (``float`` or ``int``): Fraction of data to use for testing.
        val_size (``float`` or ``int``): Fraction of data to use for validation.

    Example:

    >>> x, y = set_training_split(x, y, train_size=0.8, val_size=0.2, test_size=0.1)
    """

    if x.num_timesteps >= y.num_timesteps:
        x.set_training_split(
            train_size=train_size, val_size=val_size, test_size=test_size
        )
        y.train_size = x.train_size
        y.val_size = x.val_size
        y.test_size = x.test_size
    else:
        y.set_training_split(
            train_size=train_size, val_size=val_size, test_size=test_size
        )
        x.train_size = y.train_size
        x.val_size = y.val_size
        x.test_size = y.test_size


class _PanelSeries(pd.Series):
    def __init__(self, df, *args, **kwargs):
        super().__init__(df, *args, **kwargs)

    @property
    def _constructor_expanddim(self):
        return Panel

    @property
    def _constructor(self):
        return _PanelSeries

class CustomDataFrameGroupBy(DataFrameGroupBy):
    # ! Does not work with ids
    def __getitem__(self, key):
        key = list(key) if is_iterable(key) else [key]
        if isinstance(key[0], int):
            key = self.obj.ids[list(key)]
        return self.obj.loc[key]

class Panel(pd.DataFrame):
    """
    Panel class.
    """

    def __init__(self, *args, **kw):
        super(Panel, self).__init__(*args, **kw)
        if len(args) == 1 and isinstance(args[0], Panel):
            args[0]._copy_attrs(self)


    _attributes_ = "train_size,test_size,val_size"

    def _copy_attrs(self, df):
        for attr in self._attributes_.split(","):
            df.__dict__[attr] = getattr(self, attr, None)

    @property
    def _constructor(self):
        def f(*args, **kw):
            df = Panel(*args, **kw)

            # Workaround to fix pandas bug
            if (df.index.nlevels > 1 and self.index.nlevels > 1) and len(
                df.index.levels
            ) > len(self.index.levels):
                df = df.droplevel(0, axis="index")

            if df.num_frames == self.num_frames:
                self._copy_attrs(df)

            # ?
            # df.style.set_properties(**{"background-color": "black", "color": "green"})

            return df

        return f

    @property
    def _constructor_sliced(self):
        return _PanelSeries

    @property
    def num_frames(self) -> int:
        """Returns the number of frames in the panel."""
        return self.shape_[0]

    @property
    def num_timesteps(self) -> int:
        """Returns the number of timesteps in the panel."""
        return self.shape_[1]

    @property
    def num_columns(self) -> int:
        """Returns the number of columns in the panel."""
        return self.shape_[2]


    @property
    def frames(self) -> CustomDataFrameGroupBy:
        """
        Returns panel's frames.
        """
        return CustomDataFrameGroupBy(self, self.groupby(level=0, as_index=True).grouper)

    @property
    def timesteps(self) -> pd.Int64Index:
        """
        Returns panel's timesteps.
        """
        return self.index.get_level_values(1)

    @property
    def ids(self) -> pd.Int64Index:
        """
        Returns panel's ids without duplicates.
        """
        return self.index.get_level_values(0).drop_duplicates()

    @ids.setter
    def ids(self, ids: list[int]) -> None:
        """
        Set panel's ids.

        Args:
            ids (``list``): List of ids.
        """

        ids = np.repeat(ids, self.shape_[1])
        timestep = self.index.get_level_values(1)

        index = pd.MultiIndex.from_arrays([ids, timestep], names=["id", timestep.name])

        self.index = index

    def reset_ids(self, inplace: bool = False) -> Panel | None:
        """
        Reset panel's ids.

        Args:
            inplace (``bool``): Whether to reset ids inplace.
        """
        new_ids = np.repeat(np.arange(self.num_frames), self.num_timesteps)
        new_index = pd.MultiIndex.from_arrays(
            [new_ids, self.index.get_level_values(1)],
            names=self.index.names,
        )

        return self.set_index(new_index, inplace=inplace)

    @property
    def shape_(self) -> tuple[int, int, int]:
        """
        Return a tuple representing the dimensionality of the Panel.
        """
        return (len(self.ids), int(self.shape[0] / len(self.ids)), self.shape[1])

    def nth(self, n: list[int] | int = 0) -> Panel:
        # ? rename with get_nth_rows?
        """
        Returns the nth row of each of a panel's frame.

        Args:
            n (``list[int]`` or ``int``): Row index.
        """
        if isinstance(n, int):
            n = [n]

        if all(n < -1 or n >= self.num_timesteps for n in n):
            raise ValueError("n must be -1 or between 0 and the number of timesteps")

        new_panel = self.frames.nth(n)
        self._copy_attrs(new_panel)
        return new_panel

    @property
    def values_(self) -> np.ndarray:
        """
        3D matrix with Panel value.

        Example:

        >>> panel.values
        array([[[283.95999146, 284.13000488, 280.1499939 , 281.77999878],
                [282.58999634, 290.88000488, 276.73001099, 289.98001099]],
               [[282.58999634, 290.88000488, 276.73001099, 289.98001099],
                [285.54000854, 286.3500061 , 274.33999634, 277.3500061 ]],
               [[285.54000854, 286.3500061 , 274.33999634, 277.3500061 ],
                [274.80999756, 279.25      , 271.26998901, 274.73001099]],
               [[274.80999756, 279.25      , 271.26998901, 274.73001099],
                [270.05999756, 272.35998535, 263.32000732, 264.57998657]]])
        """
        return np.reshape(self.to_numpy(), self.shape_)

    def smash(self) -> pd.DataFrame:
        """
        Returns a DataFrame with the panel's frames smashed into a single frame.
        """

        new_timesteps = np.resize(
            np.arange(self.num_timesteps), self.num_timesteps * self.num_frames
        )
        new_index = pd.MultiIndex.from_arrays(
            [self.index.get_level_values(0), new_timesteps],
            names=self.index.names,
        )

        panel = (
            self.set_index(new_index)
            .reset_index()
            .pivot(index="ids", columns=self.index.names[1])
        )

        columns = [f"{col}_{index}" for col, index in panel.columns.to_flat_index()]

        panel.columns = columns

        return panel

    def drop_ids(self, ids: list[int] | int, inplace: bool = False) -> Panel | None:
        """
        Drop frames by id.

        Args:
            ids (``list[int]`` or ``int``): List of ids to drop.
            inplace (``bool``): Whether to drop ids inplace.

        Returns:
            ``Panel``: Panel with frames dropped.
        """

        if self.index.nlevels == 1:
            return self.drop(index=ids, axis=0, inplace=inplace)

        return self.drop(index=ids, level=0, inplace=inplace)

    def find_empty_frames(self) -> pd.Int64Index:
        """
        Find frames with all missing values.

        Returns:
            ``List``: List with index of empty frames.
        """
        na = self.isna().any(axis=1)
        return (
            self[na].index.get_level_values(0).drop_duplicates()
            if na.any()
            else pd.Int64Index([], name="id")
        )

    def drop_empty_frames(self, inplace: bool = False) -> Panel | None:
        """
        Drop frames with missing values from the panel.

        Args:
            inplace (``bool``): Whether to drop frames inplace.

        Returns:
            ``Panel``: Panel with frames dropped.
        """
        return self.drop_ids(self.find_empty_frames(), inplace=inplace)

    def match(self, other: Panel, inplace: bool = False) -> Panel | None:
        """
        Match panel with other panel.

        This function will match the ids and id order of self based on the ids of other.

        Args:
            other (``Panel``): Panel to match with.
            inplace (``bool``): Whether to match inplace.

        Returns:
            ``Panel``: Result of match function.
        """

        other_ids = set(other.ids)
        self_ids = set(self.ids)

        if [i for i in other_ids if i not in self_ids]:
            raise ValueError("There are elements in other that are not in self.")

        if inplace:
            return self.drop_ids(self_ids - other_ids, inplace=True)

        return self.loc[other.ids]

    def set_training_split(
        self,
        train_size: float | int = 0.7,
        val_size: float | int = 0.2,
        test_size: float | int = 0.1,
    ) -> None:
        """
        Splits Panel into training, validation, and test.

        Args:
            train_size (``float`` or ``int``): Fraction of data to use for training.
            test_size (``float`` or ``int``): Fraction of data to use for testing.
            val_size (``float`` or ``int``): Fraction of data to use for validation.

        Example:

        >>> panel.set_training_split(train_size=0.8, val_size=0.2, test_size=0.1)
        """

        n_train, n_val, n_test = _validate_training_split(
            self.num_frames,
            train_size=train_size,
            val_size=val_size,
            test_size=test_size,
        )

        self.train_size = n_train
        self.val_size = n_val - self.num_timesteps + 1
        self.test_size = n_test - self.num_timesteps + 1

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert panel to dataframe.

        Returns:
            ``pd.DataFrame``: Dataframe with panel values.
        """
        return pd.DataFrame(self)

    @property
    def train(self) -> Panel:
        """
        Returns the Panel with the training set.

        Returns:
            ``Panel``: Panel with the training set.
        """

        return self[: self.train_size * self.num_timesteps] if self.train_size else None

    @train.setter
    def train(self, value: np.ndarray) -> None:
        """
        Set the training set.

        Args:
            value (``Panel``): Panel with the training set.
        """

        if not self.train_size:
            raise ValueError("No training set was set.")
        self[: self.train_size * self.num_timesteps] = value.values

    @property
    def val(self) -> Panel:
        """
        Returns the Panel with the validation set.

        Returns:
            ``Panel``: Panel with the validation set.
        """

        return (
            self[
                (self.train_size + self.num_timesteps - 1)
                * self.num_timesteps : (
                    self.train_size + self.val_size + self.num_timesteps - 1
                )
                * self.num_timesteps
            ]
            if self.val_size
            else None
        )

    @val.setter
    def val(self, value: np.ndarray) -> None:
        """
        Set the validation set.

        Args:
            value (``Panel``): Panel with the validation set.
        """

        if not self.val_size:
            raise ValueError("No validation set was set.")
        self[
            (self.train_size + self.num_timesteps - 1)
            * self.num_timesteps : (
                self.train_size + self.val_size + self.num_timesteps - 1
            )
            * self.num_timesteps
        ] = value.values

    @property
    def test(self) -> Panel:
        """
        Returns the Panel with the testing set.

        Returns:
            ``Panel``: Panel with the testing set.
        """

        return self[-self.test_size * self.num_timesteps :] if self.test_size else None

    @test.setter
    def test(self, value: np.ndarray) -> None:
        """
        Set the testing set.

        Args:
            value (``Panel``): Panel with the testing set.
        """

        if not self.test_size:
            raise ValueError("No testing set was set.")
        self[-self.test_size * self.num_timesteps :] = value.values

    def head_(self, n: int = 2) -> Panel:
        """
        Return the first n frames of the panel.

        Args:
            n (``int``): Number of frames to return.

        Returns:
            ``Panel``: Result of head function.
        """
        return self[: n * self.shape_[1]]

    def tail_(self, n: int = 2) -> Panel:
        """
        Return the last n frames of the panel.

        Args:
            n (``int``): Number of frames to return.

        Returns:
            ``Panel``: Result of tail function.
        """
        return self[-n * self.shape_[1] :]

    def sort_(
        self,
        ascending: bool = True,
        inplace: bool = False,
        kind: str = "quicksort",
        key: callable = None,
    ) -> Panel | None:
        """
        Sort panel by ids.

        Args:
            ascending (``bool`` or list-like of ``bools``, default True): Sort ascending vs. descending. When the index is a MultiIndex the sort direction can be controlled for each level individually.
            inplace (``bool``, default False): If True, perform operation in-place.
            kind ({'quicksort', 'mergesort', 'heapsort', 'stable'}, default 'quicksort'): Choice of sorting algorithm. See also numpy.sort() for more information. mergesort and stable are the only stable algorithms. For DataFrames, this option is only applied when sorting on a single column or label.
            key (callable, optional): If not None, apply the key function to the index values before sorting. This is similar to the key argument in the builtin sorted() function, with the notable difference that this key function should be vectorized. It should expect an Index and return an Index of the same shape. For MultiIndex inputs, the key is applied per level.

        Returns:
            ``Panel`` or ``None``: The original DataFrame sorted by the labels or None if `inplace=True`.
        """

        return self.sort_index(
            level=0,
            ascending=ascending,
            inplace=inplace,
            kind=kind,
            sort_remaining=False,
            key=key,
        )

    def sample_(
        self,
        samples: int | float = 5,
        how: str = "spaced",
        reset_ids: bool = False,
        seed: int = 42,
    ) -> Panel | None:
        """
        Sample panel returning a subset of frames.

        Args:
            samples (``int`` or ``float``): Number or percentage of samples to return.
            how (``str``): Sampling method, 'spaced' or 'random'
            reset_ids (``bool``): If True, reset the index of the sampled panel.
            seed (``int``): Random seed.

        Returns:
            ``Panel``: Result of sample function.
        """

        train_size = self.train_size if hasattr(self, "train_size") else self.num_frames
        val_size = self.val_size if hasattr(self, "val_size") else 0
        test_size = self.test_size if hasattr(self, "test_size") else 0

        train_samples, val_samples, test_samples = _validate_sample_panel(
            samples=samples,
            train_size=train_size,
            val_size=val_size,
            test_size=test_size,
        )

        if how == "random":
            # Set seed
            np.random.seed(seed)

            if hasattr(self, "train_size"):
                train_ids = sorted(
                    np.random.choice(self.train.ids, train_samples, replace=False)
                )
                val_ids = sorted(
                    np.random.choice(self.val.ids, val_samples, replace=False)
                )
                test_ids = sorted(
                    np.random.choice(self.test.ids, test_samples, replace=False)
                )
            else:
                train_ids = sorted(
                    np.random.choice(self.ids, train_samples, replace=False)
                )
                val_ids = []
                test_ids = []

        elif how == "spaced":
            if hasattr(self, "train_size"):
                train_ids = np.linspace(
                    0,
                    self.train.shape_[0],
                    train_samples,
                    dtype=int,
                    endpoint=False,
                )
                val_ids = np.linspace(
                    0,
                    self.val.shape_[0],
                    val_samples,
                    dtype=int,
                    endpoint=False,
                )
                test_ids = np.linspace(
                    0,
                    self.test.shape_[0],
                    test_samples,
                    dtype=int,
                    endpoint=False,
                )
            else:
                train_ids = np.linspace(
                    0, self.shape_[0], train_samples, dtype=int, endpoint=False
                )
                val_ids = []
                test_ids = []

        new_panel = self.frames[[*train_ids, *val_ids, *test_ids]]

        # Reset ids
        if reset_ids:
            new_panel.reset_ids(inplace=True)

        # Set new train, val, test sizes
        if hasattr(self, "train_size"):
            new_panel.train_size = train_samples
            new_panel.val_size = val_samples
            new_panel.test_size = test_samples

        # # TODO inplace not working
        # if inplace:
        #     self = new_panel
        #     return None

        return new_panel

    def shuffle_(self, seed: int = None, reset_ids: bool = False) -> Panel | None:
        """
        Shuffle the panel.

        Args:
            seed (``int``): Random seed.
            reset_ids (``bool``): If True, reset the index of the shuffled panel.

        Returns:
            ``Panel``: Result of shuffle function.
        """

        # warnings.warn("Shuffling the panel can result in data leakage.")

        if hasattr(self, "train_size"):
            train_ids = list(self.train.ids)
            val_ids = list(self.val.ids)
            test_ids = list(self.test.ids)
        else:
            train_ids = list(self.ids)
            val_ids = []
            test_ids = []

        random.seed(seed)
        random.shuffle(train_ids)
        random.shuffle(val_ids)
        random.shuffle(test_ids)

        new_panel = self.loc[[*train_ids, *val_ids, *test_ids]]

        # Reset ids
        if reset_ids:
            new_panel.reset_ids(inplace=True)

        # # TODO inplace not working
        # if inplace:
        #     self = new_panel
        #     return None

        return new_panel

    # ! Inconsistent with lookback >= 2 if frames were modified.
    def plot_(
        self,
        add_annotation: bool = True,
        max: int = 10_000,
        use_timestep: bool = False,
        **kwargs,
    ) -> plot.PanelFigure:
        """
        Plot the panel.

        Args:
            add_annotation (``bool``): If True, plot the training, validation, and test annotation.
            max (``int``): Maximum number of samples to plot.
            use_timestep (``bool``): If True, plot the timestep instead of the sample index.
            **kwargs: Additional arguments to pass to the plot function.

        Returns:
            ``plot``: Result of plot function.
        """

        panel = self.nth(n=0)
        panel = panel.reset_index(level=0, drop=True)

        if max and self.num_frames > max:
            return plot(
                panel.sample_(max, how="spaced"),
                use_timestep=use_timestep,
                add_annotation=add_annotation,
                **kwargs,
            )
        return plot(
            panel, use_timestep=use_timestep, add_annotation=add_annotation, **kwargs
        )
