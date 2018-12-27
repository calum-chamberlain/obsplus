"""
Tests for the sql engine for decomposing and storing event data.
"""


import pytest

from obsplus.events.sqlengine import SQLEngine


@pytest.fixture(scope='class')
def engine(bingham_dataset):
    cat = bingham_dataset.event_client.get_events()
    return SQLEngine(cat)


class TestToDf:
    """ Ensure the contents of the engine can be returned as a df. """

