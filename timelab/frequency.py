import numpy as np
import pandas as pd
import exchange_calendars as ecals


"""
Calendars:
https://github.com/rsheftel/pandas_market_calendars
https://github.com/gerrymanoim/exchange_calendars

Create a calendar from holidays:
https://pypi.org/project/holidays/
https://pandas.pydata.org/pandas-docs/version/0.17.1/timeseries.html#holidays-holiday-calendars


Available Frequencies:
https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html

Alias    Description
B        business day frequency
C        custom business day frequency
D        calendar day frequency
W        weekly frequency
M        month end frequency
SM       semi-month end frequency (15th and end of month)
BM       business month end frequency
CBM      custom business month end frequency
MS       month start frequency
SMS      semi-month start frequency (1st and 15th)
BMS      business month start frequency
CBMS     custom business month start frequency
Q        quarter end frequency
BQ       business quarter end frequency
QS       quarter start frequency
BQS      business quarter start frequency
A, Y     year end frequency
BA, BY   business year end frequency
AS, YS   year start frequency
BAS, BYS business year start frequency
BH       business hour frequency
H        hourly frequency
T, min   minutely frequency
S        secondly frequency
L, ms    milliseconds
U, us    microseconds
N        nanoseconds
"""


def available_calendars():
    # TODO: Should support pandas default calendars
    return ecals.get_calendar_names()


def index_info(df):
    index_df = pd.DataFrame(index=df.index)
    idx = index_df.index
    index_df['weekday'] = idx.weekday
    index_df['day'] = idx.day
    index_df['week'] = idx.isocalendar().week  # .week deprecated
    index_df['month'] = idx.month
    index_df['year'] = idx.year
    index_df['hour'] = idx.hour
    index_df['minute'] = idx.minute
    index_df['second'] = idx.second
    # index_df['milisecond'] = idx.milisecond # ! Did pandas forget it?
    index_df['microsecond'] = idx.microsecond
    index_df['nanosecond'] = idx.nanosecond
    return index_df


def custom_resample(df, calendar=None, weekdays=None, between_time=[],
                    holidays=[], include_start=True, include_end=True):

    # TODO: Should support pandas default calendars and others not in ecals

    rule = find_closest(df)
    df = df.resample(rule).asfreq()
    index = df.index.tz_localize(None)  # ! removes timezone

    if calendar:
        # FIX: Not working
        cal = ecals.get_calendar(calendar)
        cal_df = pd.DataFrame(index=cal.all_minutes)
        cal_df = cal_df.resample(rule).mean()
        cal_index = cal_df.index.tz_localize(None)  # ! removes timezone
        df = df[to_nanos(index).isin(to_nanos(cal_index))]

    if weekdays:
        df = df.loc[df.index.weekday.isin(weekdays)]

    if holidays:
        df = df[~(df.index.isin(holidays))]

    if between_time:
        df = df.between_time(
            *between_time, include_start=include_start, include_end=include_end)

    return df


def find_closest(df):
    """Infer closest or most granular frequency

    Args:
        df ([type]): [description]

    Returns:
        [type]: [description]
    """""

    freqs = ['N', 'U', 'L', 'S', 'T', 'H', 'D', 'W', 'M', 'Y']
    for f in freqs:
        if minfreq(df) <= to_nano(pd.Timedelta('1' + f)):
            return f


# TODO: Merge two functions
def to_nano(date):
    if isinstance(date, pd.Timedelta):
        return int(date.total_seconds() * 10**9)
    elif isinstance(date, pd.Timestamp):
        return (date - pd.Timestamp("1970-01-01")) // pd.Timedelta('1ns')


# TODO: Merge two functions
def to_nanos(dates):
    if isinstance(dates[0], pd.Timedelta):
        return [int(date.total_seconds() * 10**9) for date in dates]
    elif isinstance(dates[0], pd.Timestamp):
        return (dates - pd.Timestamp("1970-01-01")) // pd.Timedelta('1ns')


def minfreq(data):
    return np.diff(data.index.values).min().astype(int)


def maxfreq(data):
    return np.diff(data.index.values).max().astype(int)


def is_constant(data):
    return minfreq(data) == maxfreq(data)


def is_positive(data):
    return minfreq(data) > 0


def infer(data):
    return data.index.inferred_freq


def get_duplicated(data):
    return data.loc[data.index.duplicated()].index.tolist()


def remove_duplicated(data):
    duplicated = get_duplicated(data)
    non_duplicated = list(~np.array(duplicated))
    return data.loc[non_duplicated]


def inspect(data, verbose=1):
    """
    Inspect if the data frequency is inferable at each timestep.

    Parameters
    ----------
    data : dataframe

    """

    if verbose > 0:
        print(f"First: {data.index[0]}")
        print(f"Last: {data.index[-1]}\n")

        print(f"Min Frequency: {minfreq(data)} ns")
        print(f"Max Frequency: {maxfreq(data)} ns\n")

    duplicated = get_duplicated(data)
    if duplicated and verbose > 0:
        print(f"Duplicated Date Times found:\n{duplicated}")

    breaks = []

    while True:
        for i, index in enumerate(data.index):
            if index in (data.index[0], data.index[1]):
                continue
            if not infer(data.loc[:index]):
                if verbose > 1:
                    print(f"Frequency breaks at {index}")
                breaks.append(index)
                data = data.iloc[i:]
                break
        if infer(data.loc[:index]):
            break
    return duplicated, breaks
