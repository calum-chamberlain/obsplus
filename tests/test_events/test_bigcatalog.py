"""
Tests for the big catalog.
"""
import pandas as pd
import pytest

import obspy
from obspy.core.event import ResourceIdentifier, Catalog

from obsplus.utils import yield_obj_parent_attr
from obsplus.events.bigcatalog import BigCatalog, _LazyList


@pytest.fixture(scope='class')
def big_bingham(bingham_dataset):
    return BigCatalog(bingham_dataset.event_client)


class TestLazyList:

    @pytest.fixture(scope='class')
    def rid_dict(self):
        """ A dict of resource IDs and their referred objects. """
        cat = obspy.read_events()
        out = {}
        for obj, parent, attr in yield_obj_parent_attr(cat, ResourceIdentifier):
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

    def test_get_item(self, rid_dict):
        lazy_list = list(rid_dict)
        ll = _LazyList(list(rid_dict))
        breakpoint()
        print('hey')


class TestBasics:
    def test_to_df(self, big_bingham):
        """ ensure the catalog can return the df summary. """
        df = big_bingham.to_df()
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

    def test_resource_ids_correct(self, big_bingham):
        """ ensure the resource IDs point to the correct obj """
        for obj, parent, attr in yield_obj_parent_attr(big_bingham):
            if hasattr(obj, 'resource_id'):
                if isinstance(obj, ResourceIdentifier):
                    continue
                rid = obj.resource_id
                referred_obj = rid.get_referred_object()
                assert obj is referred_obj




