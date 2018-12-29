"""
A module for storing the catalog contents in a SQL database using a
SQLite engine. I suspect only SQLite and postgres will be supported because
a variable string column is needed.
"""
from typing import Sequence, Union

import pandas as pd
import sqlalchemy

import obsplus
from obsplus.constants import get_events_parameters
from obsplus.interfaces import EventClient
from obsplus.utils import compose_docstring
from obsplus.events.lazycatalog import _events_to_raw_table
import obspy.core.event as ev


class SQLEngine:
    """
    A SQL engine for storing info. in the lazy catalog.

    Acts as the interface to a sql backend where events are stored in a table
    as json blobs.

    There are two tables in the database. The first is a summary table which
    is referenced when the events are queried. It contains information about
    the preferred origin and magnitude, event_id, etc.

    The second table stores the raw data in the form of JSON strings. Each
    object is deconstructed into json. All children of the object that have
    resource identifiers are then separated and stored in a different column.
    The columns of this table are:

    | resource_id | event_id | class_name | parent_id | object |
    """

    def __init__(self, *, engine_args="sqlite://", events=None, **kwargs):
        self._engine = sqlalchemy.create_engine(engine_args, **kwargs)
        if events is not None:
            self.dump_events(events)

    def dump_events(self, event_like: Union[EventClient, Sequence[ev.Event]]):
        """
        Dump events into the database.

        Parameters
        ----------
        event_like
            A sequence of Events or anything with a `get_events` method.
        """
        if isinstance(event_like, EventClient):
            events = event_like.get_events()
        self._raw_table = _events_to_raw_table(events)
        self._summary_table = obsplus.events_to_df(event_like)

    @compose_docstring(get_events_params=get_events_parameters)
    def to_df(self, *args, level="summary", **kwargs) -> pd.DataFrame:
        """
        Dump contents of database to a dataframe, optionally filtering.

        Parameters
        ----------
        level
            Sets the level. Only summary supported for now.
        """
        if level == "summary":
            return self._summary_table
        elif level == "raw":
            return self._raw_table
