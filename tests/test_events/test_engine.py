"""
Generic tests for lazy catalog engines (just sql for now).
"""

import pandas as pd
import pytest

from obsplus.events.sqlengine import SQLEngine


@pytest.fixture(scope="class")
def sqlengine(bingham_dataset):
    cat = bingham_dataset.event_client.get_events()
    return SQLEngine(events=cat)


@pytest.fixture(scope="class", params=["sqlengine"])
def engine(request):
    """ A fixture to collect all engines. """
    return request.getfixturevalue(request.param)


@pytest.fixture(scope="class")
def summary_df(engine):
    """ Return the summary DF used for queries, etc. """
    return engine.to_df(level="summary")


@pytest.fixture(scope="class")
def raw_df(engine):
    """ return a dataframe of the main table stored in database. """
    return engine.to_df(level="raw")


class TestToDf:
    """ Ensure the contents of the engine can be returned as a df. """

    def test_summary_df(self, summary_df):
        """ ensure the summary df """
        assert isinstance(summary_df, pd.DataFrame)
        assert not summary_df.empty
