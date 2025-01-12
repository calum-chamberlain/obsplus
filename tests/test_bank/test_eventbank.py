"""
tests for event wavebank
"""
import os
import sys
from pathlib import Path
from io import StringIO

import obspy
import obspy.core.event as ev
import numpy as np
import pandas as pd
import pytest

import obsplus
from obsplus import EventBank, copy_dataset
from obsplus.events.utils import catalog_to_directory


# ----------- module fixtures


@pytest.fixture(scope="class")
def catalog(bingham_dataset):
    """ return the bingham_test_case events """
    return bingham_dataset.event_client.get_events().copy()


@pytest.fixture
def ebank(tmpdir):
    """ Create a bank from the default catalog. """
    path = Path(tmpdir) / "events"
    # get catalog, add event descriptions to it
    cat = obspy.read_events()
    descs = ["LR", "LR", "SomeSillyEvent"]
    for event, desc_txt in zip(cat, descs):
        desc = ev.EventDescription(desc_txt)
        event.event_descriptions.insert(0, desc)
    obsplus.events.utils.catalog_to_directory(cat, path)
    ebank = EventBank(path)
    ebank.update_index()
    return ebank


@pytest.fixture(scope="class")
def bing_ebank(bingham_dataset, tmpdir_factory):
    """
    Create a copy of the bingham data set. Then return an inited event bank
    using the temporary bingham bank
    """
    new = Path(str(tmpdir_factory.mktemp("bingham")))
    copy_dataset("bingham", new)
    path = new / "bingham" / "events"
    ebank = EventBank(path)
    ebank.update_index()
    return ebank


@pytest.fixture
def ebank_with_bad_files(tmpdir):
    """ create an event bank with bad files, ensure it doesn't choke
    indexer. """
    path = Path(tmpdir)
    cat = obspy.read_events()
    catalog_to_directory(cat, path)
    # add stream file
    st = obspy.read()
    st.write(str(path / "not_an_event.xml"), "mseed")
    bank = EventBank(path)
    # should issue warning
    with pytest.warns(UserWarning):
        bank.update_index()
    return bank


# ------------ tests


class TestBankBasics:
    expected_attrs = ["update_index", "read_index"]

    @pytest.fixture
    def ebank_low_version(self, ebank):
        """ return the default bank with a negative version number. """
        # monkey patch obsplus version
        negative_version = "0.0.-1"
        version = obsplus.__version__
        obsplus.__version__ = negative_version
        # write index with negative version
        os.remove(ebank.index_path)
        ebank.update_index()
        assert ebank._index_version == negative_version
        # restore correct version
        obsplus.__version__ = version
        return ebank

    def test_has_attrs(self, bing_ebank):
        """ ensure all the required attrs exist """
        for attr in self.expected_attrs:
            assert hasattr(bing_ebank, attr)

    def test_read_index(self, bing_ebank, catalog):
        """ read index, ensure its length matches events and id sets are
        equal """
        df = bing_ebank.read_index()
        assert isinstance(df, pd.DataFrame)
        assert len(catalog) == len(df)

    def test_read_timestamp(self, bing_ebank):
        """ read the current timestamp (after index has been updated)"""
        bing_ebank.update_index()
        ts = bing_ebank.last_updated
        assert isinstance(ts, float)
        assert ts > 0

    def test_init_bank_with_bank(self, bing_ebank):
        """ ensure an EventBank can be init'ed with an event bank. """
        ebank2 = EventBank(bing_ebank)
        assert isinstance(ebank2, EventBank)

    def test_bank_issubclass(self):
        """ ensure events is not a subclass of EventBank. """
        assert not issubclass(obspy.Catalog, EventBank)

    def test_bad_files_skipped(self, ebank_with_bad_files):
        """ make sure the index is still returnable and of the expected size. """
        cat = obspy.read_events()
        df = ebank_with_bad_files.read_index()
        assert len(cat) == len(df)

    def test_service_version(self, bing_ebank):
        """ The get_service_version method should return obsplus version """
        # first delete the old index and re-index, in case it is leftover
        # from a previous version.
        os.remove(bing_ebank.index_path)
        bing_ebank.update_index()
        assert bing_ebank.get_service_version() == obsplus.__version__

    def test_min_version_recreates_index(self, ebank_low_version):
        """
        If the min version is not met the index should be deleted and re-created.
        A warning should be issued.
        """
        ebank = ebank_low_version
        ipath = Path(ebank.index_path)
        mtime1 = ipath.stat().st_mtime
        with pytest.warns(UserWarning) as w:
            ebank.update_index()
        assert len(w)  # a warning should have been raised
        mtime2 = ipath.stat().st_mtime
        # ensure the index was deleted and rewritten
        assert mtime1 < mtime2

    def test_limit_keyword(self, ebank):
        """ Test that the limit keyword limits results (see #19) """
        limit = 2
        cat = ebank.get_events()
        assert len(cat) > limit
        cat2 = ebank.get_events(limit=limit)
        assert len(cat2) == limit
        assert cat.events[0:limit] == cat2.events

    def test_can_put_to_empty_bank(self, tmpdir):
        """ An empty bank should be init'able created when an event is
        put into it """
        path = Path(tmpdir) / "new_bank"
        bank = EventBank(path)
        assert not path.exists()
        cat = obspy.read_events()
        bank.put_events(cat)
        assert path.exists()
        assert len(bank.read_index()) == 3

    def test_index_version(self, ebank):
        """ ensure the index version returns the obsplus version. """
        assert ebank._index_version == obsplus.__version__

    def test_update_index_returns_self(self, ebank):
        """ ensure update index returns the instance for chaining. """
        out = ebank.update_index()
        assert out is ebank


class TestReadIndexQueries:
    """ tests to ensure the index can be queried """

    def test_query_min_magnitude(self, bing_ebank):
        """ test min mag query """
        min_mag = 1.1
        df = bing_ebank.read_index(minmagnitude=min_mag)
        assert (df["magnitude"] >= min_mag).all()

    def test_query_max_magnitude(self, bing_ebank):
        """ test min mag query """
        max_mag = 1.1
        df = bing_ebank.read_index(maxmagnitude=max_mag)
        assert (df["magnitude"] <= max_mag).all()

    def test_query_magnitudes_with_nan(self, bing_ebank):
        """ test querying a column with NaNs (local_mag) """
        minmag, maxmag = 1.0, 1.5
        df = bing_ebank.read_index(minlocal_magnitude=minmag, maxlocal_magnitude=maxmag)
        con1 = df.local_magnitude > minmag
        con2 = df.local_magnitude < maxmag
        assert (con1 & con2).all()

    def test_query_event_id(self, bing_ebank, catalog):
        """ test query on an event id """
        eve_id = str(catalog[0].resource_id)
        df = bing_ebank.read_index(event_id=eve_id)
        assert len(df) == 1
        assert eve_id in df.index

    def test_query_resource_id(self, bing_ebank, catalog):
        """ test query on a resource id """
        eve_id = catalog[0].resource_id
        df = bing_ebank.read_index(event_id=eve_id)
        assert len(df) == 1
        assert str(eve_id) in df.index

    def test_query_event_ids(self, bing_ebank, catalog):
        """
        test querying multiple ids (specifically using something other
        than a list)
        """
        eve_ids = bing_ebank.read_index().iloc[0:2].index
        df = bing_ebank.read_index(eventid=eve_ids)
        assert len(df) == 2
        assert df.index.isin(eve_ids).all()

    def test_bad_param_raises(self, bing_ebank):
        """ assert bad query param will raise """
        with pytest.raises(ValueError):
            bing_ebank.read_index(minradius=20)

    def test_no_none_strs(self, bing_ebank):
        """
        There shouldn't be any None strings in the df.
        These should have been replaced with proper None values.
        """
        df = bing_ebank.read_index()
        assert not "None" in df.values

    def test_event_description_as_set(self, ebank):
        """
        The event description should be usable as a set, list, np array etc.
        """
        # get index with no filtering
        df_raw = ebank.read_index()
        # test filtering params
        filts = [{"LR"}, "LR", np.array(["LR"]), ["LR"]]
        for filt in filts:
            # filter with dataframe
            df_filt = [filt] if isinstance(filt, str) else filt
            df1 = df_raw[df_raw["event_description"].isin(df_filt)]
            df2 = ebank.read_index(event_description=filt)
            assert len(df1) == len(df2)
            assert df1.equals(df2)


class TestGetEvents:
    """ tests for pulling events out of the bank """

    def test_no_params(self, bing_ebank, catalog):
        """ ensure a basic query can get an event """
        cat = bing_ebank.get_events()
        ev1 = sorted(cat.events, key=lambda x: str(x.resource_id))
        ev2 = sorted(catalog.events, key=lambda x: str(x.resource_id))
        assert ev1 == ev2

    def test_query(self, bing_ebank, catalog):
        """ test a query """
        t2 = obspy.UTCDateTime("2013-04-10")
        t1 = obspy.UTCDateTime("2010-01-01")
        cat = bing_ebank.get_events(endtime=t2, starttime=t1)
        assert cat == catalog.get_events(starttime=t1, endtime=t2)

    def test_issue_30(self, crandall_dataset):
        """ ensure eventid can accept a numpy array. see #30. """
        ds = crandall_dataset
        ebank = obsplus.EventBank(ds.event_path)
        # get first two indices
        inds = ebank.read_index().index[0:2]
        # query with inds as np array
        assert len(ebank.get_events(eventid=np.array(inds))) == 2


class TestPutEvents:
    """ tests for putting events into the bank """

    def test_put_new_events(self, bing_ebank):
        """ ensure a new event can be put into the bank """
        ori = ev.Origin(time=obspy.UTCDateTime("2016-01-01"))
        event = ev.Event(origins=[ori])
        event.origins[0].depth_errors = None  # see obspy 2173
        bing_ebank.put_events(event)
        event_out = bing_ebank.get_events(event_id=event.resource_id)
        assert len(event_out) == 1
        assert event_out[0] == event

    def test_update_event(self, bing_ebank, catalog):
        """ modify and event and ensure index is updated """
        index1 = bing_ebank.read_index()
        eve = catalog[0]
        # modify event
        old_lat = eve.origins[0].latitude
        new_lat = old_lat + 0.15
        eve.origins[0].latitude = new_lat
        # check event back in
        bing_ebank.put_events(eve)
        # read index, ensure event_ids are unique and have correct values
        index2 = bing_ebank.read_index()
        assert len(index1) == len(index2)
        index_lat = index2.loc[index2.index == str(eve.resource_id), "latitude"]
        assert index_lat.iloc[0] == new_lat


class TestProgressBar:
    """ Tests for the progress bar functionality of banks. """

    @pytest.fixture
    def custom_bar(self):
        """ return a custom bar implementation. """

        class Bar:
            called = False

            def __init__(self, *args, **kwargs):
                self.finished = False

            def update(self, num):
                self.__class__.called = True

            def finish(self):
                self.finished = True
                pass

        return Bar

    @pytest.fixture()
    def bar_ebank(self, ebank, monkeypatch):
        """ return an event bank specifically for testing ProgressBar. """
        # set the interval and min files to 1 to ensure bar gets called
        monkeypatch.setattr(ebank, "_bar_update_interval", 1)
        monkeypatch.setattr(ebank, "_min_files_for_bar", 1)
        # move the index to make sure there are files to update
        index_path = Path(ebank.index_path)
        if index_path.exists():
            os.remove(index_path)
        return ebank

    @pytest.fixture()
    def bar_ebank_bad_file(self, bar_ebank):
        """ Add a waveform file to ensure ProgressBar doesnt choke. """
        path = Path(bar_ebank.bank_path)
        st = obspy.read()
        st.write(str(path / "waveform.xml"), "mseed")
        return bar_ebank

    def test_custom_bar_class(self, bar_ebank, custom_bar):
        """ Ensure a custom update bar function works. """
        bar_ebank.update_index(bar=custom_bar)
        assert custom_bar.called

    def test_custom_bar_instances(self, bar_ebank, custom_bar):
        """ Ensure passing an instance to bar will simply use instance. """
        bar = custom_bar()
        assert not bar.finished
        bar_ebank.update_index(bar=bar)
        assert bar.finished

    def test_bad_file_raises_warning(self, bar_ebank_bad_file, custom_bar):
        """ Ensure a bad files raises warning but doesn't kill progress. """
        with pytest.warns(UserWarning):
            bar_ebank_bad_file.update_index(custom_bar)

    def test_false_disables_bar(self, bar_ebank, monkeypatch):
        """ Passing False for bar argument should disable it. """
        # we ensure the default bar isnt by monkey patching the util to get it
        state = {"called": False}

        def new_get_bar(*args, **kwargs):
            state["called"] = True
            obsplus.utils.get_progressbar(*args, **kwargs)

        monkeypatch.setattr(obsplus.utils, "get_progressbar", new_get_bar)

        bar_ebank.update_index(bar=False)
        assert state["called"] is False

    def test_bad_value_raises(self, bar_ebank):
        """ Passing an unsupported value to bar should raise. """
        with pytest.raises(ValueError):
            bar_ebank.update_index(bar="unsupported")

    def test_update_bar_default(self, bar_ebank, monkeypatch):
        """ Ensure the default progress bar shows up. """
        stringio = StringIO()
        monkeypatch.setattr(sys, "stdout", stringio)
        bar_ebank.update_index()
        stringio.seek(0)
        out = stringio.read()
        assert "updating or creating" in out
