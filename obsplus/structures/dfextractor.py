"""
DataFrameExtractor class and friends.
"""
import copy
import warnings
from collections import UserDict
from functools import singledispatch, reduce
from typing import Mapping, Sequence, Optional, Dict

import obspy
import pandas as pd

from obsplus.utils import iterate, order_columns


def _pass_through_dataframe(df: pd.DataFrame):
    return df


def _merge_dicts(dict1: Mapping, dict2: Mapping) -> Mapping:
    """ Merge two mappings (dict-likes) together. """
    return {**dict1, **dict2}


def _timestampit(maybe_time):
    """ Convert a possible time object to UTCDateTime and get timestamp or
    return None. """
    if pd.isnull(maybe_time):
        return maybe_time
    return obspy.UTCDateTime(maybe_time).timestamp


def _get_output_dict(obj, name, func):
    """ return an output dict.  """
    out = func(obj)
    # a dict was returned, each key, value maps to a column, value
    if isinstance(out, dict):
        return out
    else:  # a value that maps to a column was returned
        # get rid of get_ or _get_ prefix for naming column
        if name.startswith("get_"):
            name = name[4:]
        elif name.startswith("_get_"):
            name = name[5:]
        return {name: out}


class DataFrameExtractor(UserDict):
    """
    A class to extract dataframes from nested object trees.

    Generally used to construct summary dataframes from nested object
    structures such as the obspy Catalog.

    Parameters
    ----------
    cls
        The top-level class the extractor acts on.
    required_columns
        If not None, assert required columns are in dataframe, and order
        columns the same as required_columns, with extra columns at the end.
    dtypes
        A dict of {column name: required data type}. Can also be specified
        when registering extractors.
    pass_dataframe
        If True, return dataframes passed to DataFrameExtractor.__call__.
        This allows the DataFrameExtractor to be idempotent.
    utc_columns
        Columns that are UTCDateTime objects. Will correctly handle
        UTCDateTime-able objects (like date-time strings, floats, etc).
    """

    def __init__(
        self,
        cls,
        required_columns: Sequence[str] = None,
        dtypes=None,
        pass_dataframe=True,
        utc_columns=None,
    ):
        super().__init__()
        self.cls = cls
        self._func = singledispatch(self._base_call)
        self._base_required_columns = required_columns
        self._dtypes = [dtypes] if dtypes is not None else []
        self.utc_columns = utc_columns or ()
        if pass_dataframe:
            self._func.register(pd.DataFrame)(_pass_through_dataframe)

    def extractor(self, dtypes: Optional[Dict[str, type]] = None):
        """
        Register an extractor.

        An extractor is a function which extracts values from instances of a
        class. It should either return a dict of {column names: values} or
        a single value and the name of the function (minus get_ prefix if
        one exists) will be the column name.

        Parameters
        ----------
        dtypes
            A dict of {column name: dtype} to enforce a schema on the data.
        """
        # this allows the extractor to be used with or without calling it.
        # this case is when the decorator was applied without calling it
        if callable(dtypes):
            return self.extractor(dtypes=None)(dtypes)

        # case when extractor was called before applying decorator
        def register_extractor(func):
            name = self._get_name(func)
            if name in self.data:
                msg = f"{name} is already a registered extractor, overwriting"
                warnings.warn(msg)
            self.data[name] = func
            if dtypes is not None:
                self._dtypes.append(dtypes)
            return func

        return register_extractor

    def register(self, cls):
        """
        Registers an alternate constructor.

        Registers an althernate constructor that is called when the input is
        not an instance of the expected class. This is useful, for examples to
        make the DataFrameExtractor idempotent or to default to various read
        methods in a path/str is passed.

        Parameters
        ----------
        cls
            The dtype to register
        """

        def register_single_dispatch(func):
            self._func.register(cls)(func)
            return func

        return register_single_dispatch

    def _get_name(self, func):
        """ get the name of a callable. """
        try:
            return func.__name__
        except AttributeError:  # if this is an instance
            return func.__class__.__name__

    def _base_call(self, objs, extras=None) -> pd.DataFrame:
        """
        Extract information from objects for creating dataframes.

        The typical call method when the standard datatype is passed.
        An iterable of self.cls objects should be passed.

        Parameters
        ----------
        objs
            An iterable of self.cls objects
        extras
            A dict with keys as object identities and values as a dict
            to add to object row. Allows injecting additional information
            that is not normally found on the object itself.
        """
        extras = extras or {}
        rows = []
        if isinstance(objs, self.cls):  # ensure and iterable was passed
            objs = [objs]
        for obj in objs:
            try:
                row = [_get_output_dict(obj, n, f) for n, f in self.data.items()]
            except self.SkipRow:
                continue
            row.append(extras.get(id(obj), {}))

            # add extras injected to call
            if row:
                rows.append(reduce(_merge_dicts, row))

        return pd.DataFrame(rows)

    def copy(self):
        return copy.deepcopy(self)

    def __call__(self, obj, **kwargs) -> pd.DataFrame:
        """
        Iterate an object tree and create a dataframe.

        Finds all instances of targeted class and returns a row for each.

        Parameters
        ----------
        obj
            The object to recurse.
        """
        df = self._func(obj, **kwargs)
        assert isinstance(df, pd.DataFrame), "must return a DataFrame instance"
        if not df.empty:  # if df is not empty it should have all the columns
            # read in any UTCDateTime
            for col in set(iterate(self.utc_columns)) & set(df.columns):
                df[col] = df[col].apply(_timestampit)
        replace, dtypes = {"nan": "", "None": ""}, self.dtypes
        required_cols = self._base_required_columns
        return order_columns(df, required_cols, dtypes, replace)

    def __str__(self):
        msg = (
            f"DataFrameExtractor for {self.cls} with "
            f"registered extractors:\n {set(self.data)} \n "
            f"and registered types:\n {set(self._func.registry)}"
        )
        return msg

    class SkipRow(StopIteration):
        """ exception to raise to skip a row. """

    @property
    def dtypes(self):
        """ return a dictionary of datatypes. """
        return reduce(_merge_dicts, self._dtypes)
