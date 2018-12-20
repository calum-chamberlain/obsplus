"""
A catalog based on SQLlite backend.
"""
import sqlite3
from collections import UserList

import pandas as pd
from obspy import Catalog
from obspy.core.event import ResourceIdentifier
from obsplus.interfaces import EventClient


def _get_resource_id_default(name: str) -> object:
    """
    The default function for getting resource identifiers.

    Parameters
    ----------
    name
        Any identifier that can be loaded.
    """
    return ResourceIdentifier(name).get_referred_object()


class _LazyList(UserList):
    """
    A lazy list that stores resource IDs. When each element is accessed the
    referred object is loaded.
    """

    def __init__(self, *args, object_fetcher=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._obj_fetcher = object_fetcher or _get_resource_id_default
        self._failed_str = set()  # strings that could not be loaded

    def __getitem__(self, item):
        # if the item has already been loaded return it.
        obj = super().__getitem__(item)
        if not isinstance(obj, str) or item in self._failed_str:
            return obj
        # try to load the referred object
        out = self._obj_fetcher(obj)
        if out is None and isinstance(obj, str):
            self._failed_str.add(out)
        else:
            self.data[item] = out
        return out


class BigCatalog(Catalog):
    """
    A big lazy catalog.
    """


def to_big_catalog(events: EventClient) -> BigCatalog:
    """
    Convert an event client into a big catalog.

    Parameters
    ----------
    events
        Any event source.
    """

    return BigCatalog(events)
