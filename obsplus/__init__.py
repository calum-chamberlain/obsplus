"""
ObsPlus: A Pandas-Centric ObsPy Expansion Pack
"""

# -------------------- pull key objects to package level

# turn off chained assignment warnings (consider not doing this)
import pandas as pd

# package version
from obsplus.version import __version__

pd.options.mode.chained_assignment = None

# json conversions
from obsplus.events.json import json_to_cat, cat_to_json, cat_to_dict
from obsplus.events.utils import bump_creation_version, duplicate_events, get_preferred

# events validation and version bumping
from obsplus.events.validate import catalog_validator, validate_catalog

# pandas conversions
from obsplus.stations.pd import stations_to_df
from obsplus.events.pd import (
    events_to_df,
    picks_to_df,
    arrivals_to_df,
    amplitudes_to_df,
    station_magnitudes_to_df,
    magnitudes_to_df,
)

# Bank and WaveFetcher objects
from obsplus.bank.wavebank import WaveBank
from obsplus.bank.eventbank import EventBank
from obsplus.bank.stationbank import StationBank

# Sbank is depreciated, but better to not break codes
Sbank = WaveBank

from obsplus.structures.fetcher import Fetcher

# misc functions
from obsplus.utils import get_reference_time
from obsplus.structures.dfextractor import DataFrameExtractor

# load datasets function
from obsplus.datasets.utils import copy_dataset
from obsplus.datasets.dataset import DataSet

load_dataset = DataSet.load_dataset

# import xarray stuff
from obsplus.waveforms.xarray.convert import (
    obspy_to_array_dict,
    obspy_to_array,
    array_to_obspy,
)

# legacy code names, consider emitting a depreciation warning
waveform2data_array = obspy_to_array
waveform2data_array_dict = obspy_to_array_dict

# ensure all obspy objects are monkeypatched with added methods
from .events.get_events import get_events
from .stations.get_stations import get_stations
from .waveforms.get_waveforms import get_waveforms

# get the get_client methods into obsplus namespace
from obsplus.waveforms.utils import get_waveform_client
from obsplus.events.utils import get_event_client
from obsplus.stations.utils import get_station_client
