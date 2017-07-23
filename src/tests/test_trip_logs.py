"""
Tests the routines for generating trip logs.

A single GTFS-Realtime update consists of a series of messages, which earlier in our pipeline are translated into
a collection of action logs---each one a pandas DataFrame representing a set of observations on the state of the
system at some time.

The next step thereafter in our processing pipeline is to concatenate those action logs into cohesive trip logs,
which contain the entire known state for that train trip.

This test suite ascertains that we correctly construct trip logs for all of our possible trip construct cases.
"""

import unittest
import pandas as pd
import numpy as np

import sys; sys.path.append("../")
# noinspection PyUnresolvedReferences
import processing


def create_mock_action_log(actions=None, stops=None):
    length = len(actions)
    return pd.DataFrame({
        'trip_id': ['TEST'] * length,
        'route_id': [1] * length,
        'action': actions,
        'stop_id': ['999X'] * length if stops is None else stops,
        'minimum_time': list(range(0, length)),
        'maximum_time': list(range(1, length + 1)),
        'information_time': list(range(0, length))
    })


class TestParsingActionLogsIntoTripLogs(unittest.TestCase):
    def test_unary_stopped(self):
        result = processing.parse_tripwise_action_logs_into_trip_log([create_mock_action_log(['STOPPED_AT'])])
        assert len(result) == 1
        assert result.iloc[0].action == 'STOPPED_AT'

    def test_unary_en_route(self):
        result = processing.parse_tripwise_action_logs_into_trip_log([
            create_mock_action_log(actions=['EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_DEPART_AT'])
        ])
        assert len(result) == 1
        assert result.iloc[0].action == 'EN_ROUTE_TO'

    def test_unary_end(self):
        result = processing.parse_tripwise_action_logs_into_trip_log([
            create_mock_action_log(actions=['EXPECTED_TO_ARRIVE_AT'])
        ])
        assert len(result) == 1
        assert result.iloc[0].action == 'EN_ROUTE_TO'

    def test_unary_skip(self):
        result = processing.parse_tripwise_action_logs_into_trip_log([
            create_mock_action_log(actions=['EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_DEPART',
                                            'EXPECTED_TO_ARRIVE_AT'], stops=['999X', '998X', '998X', '997X'])
        ])
        assert len(result) == 3
        import pdb; pdb.set_trace()
        assert result.iloc[0].action == 'STOPPED_OR_SKIPPED'
        # TODO: Wrong!
