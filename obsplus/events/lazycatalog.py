"""
A lazy catalog based on SQLite backend.
"""
from collections import UserList
from collections import deque
import json
from typing import List

import pandas as pd
import obspy.core.event as ev
from obspy import Catalog
from obspy.core.event import ResourceIdentifier

from obsplus.events.json import cat_to_json
from obsplus.events.utils import make_class_map, obj_to_dict
from obsplus.interfaces import EventClient

ATTR_TO_CLASS = make_class_map()
ATTR_TO_CLASS_NAME = {
    i: v.__name__ for i, v in ATTR_TO_CLASS.items() if hasattr(v, "__name__")
}


def _events_to_raw_table(events) -> pd.DataFrame:
    """
    Decompose the events into storage table required by SQLEngine.
    """
    # ensure we are working with an iterable of events
    if isinstance(events, EventClient):
        events = events.get_events()

    deq = deque()  # a queue for obspy objects with resource ids
    deq.append((events, {}))
    resource_dicts = []  # a list for storing dicts with data columns

    def _queue_containers(container, name, extras):
        """ Queue up items in container that have resource_ids,
        return new list with only resource_ids in it.  """

        out = []
        for item in container:
            try:  # test if item has resource_id
                out.append(str(item.resource_id))
            except AttributeError:  # item does not have resource_id
                out.append(item)
            else:
                extras = dict(extras)
                # add object specific stuff to extras
                extras["parent_id"] = extras["resource_id"]
                extras["resource_id"] = item.resource_id
                if name in ATTR_TO_CLASS_NAME:
                    extras["class_name"] = ATTR_TO_CLASS_NAME[name]
                deq.append((item, extras))
        assert len(out) == len(container)
        return out

    def func(obj, extras=None):
        """ Function for converting events to pandas table. """
        # if this is a common sequence just iterate
        if isinstance(obj, (list, tuple)):
            for item in obj:
                func(item, extras)
            return

        # extras dict is used to inject data from multiple levels in tree.
        extras = {} if extras is None else extras
        if hasattr(obj, "resource_id"):
            extras["resource_id"] = str(obj.resource_id)
            if isinstance(obj, ev.Event):
                extras["event_id"] = extras["resource_id"]

        odict = obj_to_dict(obj)
        # determine which types of containers this object has
        if isinstance(obj, ev.Catalog):
            containers = ["events"]
        else:
            containers = getattr(obj, "_containers", [])
        # check object for containers
        for name in containers:
            odict[name] = _queue_containers(getattr(obj, name), name, extras)

        resource_dicts.append({"object": cat_to_json(odict), **extras})

    # process the queue, create row entry for each item.
    while len(deq) > 0:
        item, kwargs = deq.pop()
        func(item, extras=kwargs)

    return pd.DataFrame(resource_dicts)


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

    # classes that can be used to refer to a lazy resource
    key_classes = (str, ResourceIdentifier)

    def __init__(self, *args, object_fetcher=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._obj_fetcher = object_fetcher or _get_resource_id_default
        self._failed_str = set()  # strs/resource_ids that could not be loaded

    def __getitem__(self, item):
        # if the item has already been loaded return it.
        obj = super().__getitem__(item)
        if not isinstance(obj, self.key_classes) or item in self._failed_str:
            return obj
        # try to load the referred object
        out = self._obj_fetcher(obj)
        # if does not actually refer to anything just return it
        if out is None and isinstance(obj, str):
            self._failed_str.add(out)
            out = obj
        else:  # cache loaded object
            self.data[item] = out
        return out

    def __setitem__(self, key, value):
        if isinstance(value, ResourceIdentifier):
            value = str(value)
        super().__setitem__(key, value)

    @property
    def _isloaded(self) -> List[bool]:
        """ return a list of booleans corresponding to if each element in list
        has been loaded. """
        return [
            not (isinstance(x, str) and x not in self._failed_str) for x in self.data
        ]


class LazyCatalog(Catalog):
    """
    A lazy catalog.
    """

    def flush(self, clear: bool = False):
        """
        Flush the events in memory to backend engine.

        Parameters
        ----------
        clear
            If True delete all catalog components currently in memory after
            saving to engine.
        """


def to_lazy_catalog(events: EventClient) -> LazyCatalog:
    """
    Convert an event client into a big catalog.

    Parameters
    ----------
    events
        Any event source.
    """

    return LazyCatalog(events)
