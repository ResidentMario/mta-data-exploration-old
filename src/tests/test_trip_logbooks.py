"""
Tests the routines for generating trip logbooks.

A single GTFS-Realtime update consists of a series of messages, which earlier in our pipeline are translated into
a collection of trip logs---each one a pandas DataFrame representing all known information about one particular train
trip.

A trip logbook is merely a convenient collection of trips, in the form of a dict whose keys are individual trips'
IDs. This test suite ascertains that we build these correctly.
"""

# parse_feeds_into_trip_logbook
# _join_trip_logs

import unittest
import pandas as pd
import numpy as np

import sys; sys.path.append("../")
# noinspection PyUnresolvedReferences
import processing


class SmokeTest(unittest.TestCase):
    """
    Tests for simpler cases which can be processed in a single action log.
    """
    def setUp(self):
        from google.transit import gtfs_realtime_pb2
        with open("./data/gtfs_realtime_pull_1.dat", "rb") as f:
            self.gtfs_r0 = gtfs_realtime_pb2.FeedMessage()
            self.gtfs_r0.ParseFromString(f.read())
        with open("./data/gtfs_realtime_pull_2.dat", "rb") as f:
            self.gtfs_r1 = gtfs_realtime_pb2.FeedMessage()
            self.gtfs_r1.ParseFromString(f.read())

    def test_smoke(self):
        left_logbook = processing.parse_feeds_into_trip_logbook([self.gtfs_r0], [0])
        right_logbook = processing.parse_feeds_into_trip_logbook([self.gtfs_r1], [1])
        import pdb; pdb.set_trace()
        result = processing.merge_trip_logbooks([left_logbook, right_logbook])
        import pdb; pdb.set_trace()
        # TODO: This takes too long to run! Profile this!
