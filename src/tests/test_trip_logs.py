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


def create_mock_action_log(actions=None, stops=None, information_time=0):
    length = len(actions)
    return pd.DataFrame({
        'trip_id': ['TEST'] * length,
        'route_id': [1] * length,
        'action': actions,
        'stop_id': ['999X'] * length if stops is None else stops,
        'information_time': [information_time] * length,
        'time_assigned': list(range(length))
    })


class TestParsingActionLogsIntoTripLogs(unittest.TestCase):
    def test_unary_stopped(self):
        """
        An action log with just a stoppage ought to report as a trip log with just a stoppage.
        """
        actions = [create_mock_action_log(['STOPPED_AT'])]
        result = processing.parse_tripwise_action_logs_into_trip_log(actions)

        assert len(result) == 1
        assert result.iloc[0].action == 'STOPPED_AT'
        assert all([int(result.iloc[0]['maximum_time']) == 0, int(result.iloc[0]['minimum_time']) == 0,
                    int(result.iloc[0]['latest_information_time']) == 0])

    def test_unary_en_route(self):
        """
        An action log with just an arrival and departure ought to report as just an arrival (note: this is the same
        technically broken case tested by the eight test in action log testing; for more on when this arises,
        check the docstring there).
        """
        actions = [create_mock_action_log(actions=['EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_DEPART_AT'])]
        result = processing.parse_tripwise_action_logs_into_trip_log(actions)

        assert len(result) == 1
        assert result.iloc[0].action == 'EN_ROUTE_TO'
        assert all([result.iloc[0]['maximum_time'] in [np.nan, 'nan'],
                    int(result.iloc[0]['minimum_time']) == 0,
                    int(result.iloc[0]['latest_information_time']) == 0])

    def test_unary_end(self):
        """
        An action log with a single arrival ought to report a single EN_ROUTE_TO in the trip log.
        """
        result = processing.parse_tripwise_action_logs_into_trip_log([
            create_mock_action_log(actions=['EXPECTED_TO_ARRIVE_AT'])
        ])
        assert len(result) == 1
        assert result.iloc[0].action == 'EN_ROUTE_TO'
        assert all([result.iloc[0]['maximum_time'] in [np.nan, 'nan'],
                    int(result.iloc[0]['minimum_time']) == 0,
                    int(result.iloc[0]['latest_information_time']) == 0])

    def test_unary_arriving_skip(self):
        """
        An action log with a stop to be skipped ought to report an arrival at that stop in the resultant trip log.
        This is because we leave the job of detecting a skip to the combination process.

        This is an "arriving skip" because a skip will occur on a station that has either a departure or arrival
        defined, but not both.
        """
        # TODO: Affirm that this is actually true.
        actions = [
            create_mock_action_log(actions=['EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_DEPART',
                                            'EXPECTED_TO_ARRIVE_AT'], stops=['999X', '998X', '998X', '997X'])
        ]
        result = processing.parse_tripwise_action_logs_into_trip_log(actions)

        assert len(result) == 3
        assert list(result['action'].values) == ['EN_ROUTE_TO', 'EN_ROUTE_TO', 'EN_ROUTE_TO']
        assert list(result['minimum_time'].values.astype(int)) == [0] * 3
        assert list(result['maximum_time'].values.astype(str)) == ['nan'] * 3

    def test_unary_departing_skip(self):
        """
        An action log with a stop to be skipped ought to report an arrival at that stop in the resultant trip log.
        This is because we leave the job of detecting a skip to the combination process.

        This is an "arriving skip" because a skip will occur on a station that has either a departure or arrival
        defined, but not both.
        """
        actions = [
            create_mock_action_log(actions=['EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_DEPART', 'EXPECTED_TO_DEPART',
                                            'EXPECTED_TO_ARRIVE_AT'], stops=['999X', '998X', '998X', '997X'])
        ]
        result = processing.parse_tripwise_action_logs_into_trip_log(actions)

        assert len(result) == 3
        assert list(result['action'].values) == ['EN_ROUTE_TO', 'EN_ROUTE_TO', 'EN_ROUTE_TO']
        assert result['action'].values.all() == 'EN_ROUTE_TO'
        assert list(result['minimum_time'].values.astype(int)) == [0] * 3
        assert list(result['maximum_time'].values.astype(str)) == ['nan'] * 3

    def test_unary_en_route_trip(self):
        """
        A slightly longer test. Like `test_unary_en_route`, but with a proper station terminus.
        """
        actions = [
            create_mock_action_log(actions=['EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_DEPART_FROM',
                                            'EXPECTED_TO_ARRIVE_AT'],
                                   stops=['999X', '999X', '998X'])
        ]
        result = processing.parse_tripwise_action_logs_into_trip_log(actions)

        assert len(result) == 2
        assert list(result['action'].values) == ['EN_ROUTE_TO', 'EN_ROUTE_TO']
        assert result['action'].values.all() == 'EN_ROUTE_TO'
        assert list(result['minimum_time'].values.astype(int)) == [0] * 2
        assert list(result['maximum_time'].values.astype(str)) == ['nan'] * 2

    def test_unary_ordinary_stopped_trip(self):
        """
        A slightly longer test. Like `test_unary_stopped`, but with an additional arrival after the present one.
        """
        actions = [
            create_mock_action_log(actions=['STOPPED_AT',
                                            'EXPECTED_TO_ARRIVE_AT'],
                                   stops=['999X', '998X'])
        ]
        result = processing.parse_tripwise_action_logs_into_trip_log(actions)

        assert len(result) == 2
        assert list(result['action'].values) == ['STOPPED_AT', 'EN_ROUTE_TO']
        assert list(result['minimum_time'].values.astype(int)) == [0] * 2
        assert list(result['maximum_time'].values.astype(str)) == ['0', 'nan']

# TODO: Non-unary tests, cranking them together.
