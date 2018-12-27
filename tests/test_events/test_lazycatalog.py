"""
Tests for the big catalog.
"""

import obspy
import obspy.core.event as ev
import pandas as pd
import pytest
from obspy.core.event import ResourceIdentifier

from obsplus.events.lazycatalog import LazyCatalog, _LazyList
from obsplus.utils import yield_obj_parent_attr


@pytest.fixture(scope="class")
def lazy_cat(bingham_dataset):
    """ Lazify the bingham catalog and flush, run gc, return result. """
    lazy = LazyCatalog(bingham_dataset.event_client)
    lazy.flush(clear=True)
    return lazy


class TestLazyList:
    @pytest.fixture(scope="class")
    def rid_dict(self):
        """ A dict of resource IDs and their referred objects. """
        cat = obspy.read_events()
        out = {}
        for obj, parent, attr in yield_obj_parent_attr(cat, ResourceIdentifier):
            if attr != "resource_id":
                continue
            out[str(obj)] = parent
        return out

    @pytest.fixture
    def rid_list(self, rid_dict):
        """ return a list of resource ids used in the rid_dict """
        return list(rid_dict)

    @pytest.fixture
    def lazy_list(self, rid_list):
        """ init a lazy list. """
        return _LazyList(rid_list)

    def test_get_item(self, rid_dict, rid_list, lazy_list):
        """ Ensure that get item returns the loaded object. """
        # iterate the lazy list and ensure each item was loaded
        for item, rid in zip(lazy_list, rid_list):
            assert hasattr(item, "resource_id")
            assert str(rid) == str(item.resource_id)

    def test_append_object(self, lazy_list):
        """ A non-resource id bearing object should be appendable """
        lazy_list.append("hey")
        assert lazy_list[-1] == "hey"

    def test_insert_resource_id(self, lazy_list):
        """ Appending a resource ID should work to cache object. """
        obj = ev.Event()
        rid = obj.resource_id
        lazy_list.insert(0, rid)
        assert lazy_list[0] is obj

    def test_is_loaded(self, lazy_list):
        """ Ensure list can tell which items are loaded. """
        # this test may be too tightly coupled to implementation...
        assert not any(lazy_list._isloaded)
        _ = lazy_list[0]
        assert lazy_list._isloaded[0]
        assert not any(lazy_list._isloaded[1:])
        for _ in lazy_list:
            pass
        assert all(lazy_list._isloaded)


class TestBasics:
    def test_to_df(self, lazy_cat):
        """ ensure the catalog can return the df summary """
        df = lazy_cat.to_df()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    def test_resource_ids_correct(self, lazy_cat):
        """ ensure the resource IDs point to the correct obj """
        for obj, parent, attr in yield_obj_parent_attr(lazy_cat):
            if hasattr(obj, "resource_id"):
                if isinstance(obj, ResourceIdentifier):
                    continue
                rid = obj.resource_id
                referred_obj = rid.get_referred_object()
                assert obj is referred_obj
