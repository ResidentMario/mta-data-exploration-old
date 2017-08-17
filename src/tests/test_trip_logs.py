"""
Tests the routines for generating trip logs.

A single GTFS-Realtime update consists of a series of messages, which earlier in our pipeline are translated into
a collection of action logs---each one a pandas DataFrame representing a set of observations on the state of the
system at some time.

The next step thereafter in our processing pipeline is to concatenate those action logs into cohesive trip logs,
which contain the entire known state for that train trip.

This test suite ascertains that we correctly construct trip logs for all of our possible trip construct cases.

Note: the use assertions like e.g. str(value) == "nan" is due to some odd type casting behavior in `pandas`.
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


class UnaryTests(unittest.TestCase):
    """
    Tests for simpler cases which can be processed in a single action log.
    """

    def test_unary_stopped(self):
        """
        An action log with just a stoppage ought to report as a trip log with just a stoppage.
        """
        actions = [create_mock_action_log(['STOPPED_AT'])]
        result = processing.parse_tripwise_action_logs_into_trip_log(actions)

        assert len(result) == 1
        assert result.iloc[0].action == 'STOPPED_AT'
        assert all([str(result.iloc[0]['maximum_time']) == 'nan', str(result.iloc[0]['minimum_time']) == 'nan',
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
            create_mock_action_log(actions=['STOPPED_AT', 'EXPECTED_TO_ARRIVE_AT'],
                                   stops=['999X', '998X'])
        ]
        result = processing.parse_tripwise_action_logs_into_trip_log(actions)

        assert len(result) == 2
        assert list(result['action'].values) == ['STOPPED_AT', 'EN_ROUTE_TO']
        assert list(result['minimum_time'].values.astype(str)) == ['nan', '0']
        assert list(result['maximum_time'].values.astype(str)) == ['nan', 'nan']


class BinaryTests(unittest.TestCase):
    """
    Tests for more complicated cases necessitating both action logs.

    These tests do not invoke station list changes between action logs, e.g. they do not address reroutes.
    """

    def test_binary_en_route(self):
        """
        In the first observation, the train is EN_ROUTE to a station. In the next observation, it is still EN_ROUTE
        to that station.

        Our output should be a trip log with a single row. Critically, the minimum_time recorded should correspond
        with the time at which the second observation was made---1, in this test case.
        """
        base = create_mock_action_log(actions=['EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_ARRIVE_AT'],
                                      stops=['999X', '999X'])
        first = base.head(1)
        second = base.tail(1).set_value(1, 'information_time', 1)
        actions = [first, second]

        result = processing.parse_tripwise_action_logs_into_trip_log(actions)

        assert len(result) == 1
        assert list(result['action'].values) == ['EN_ROUTE_TO']
        assert list(result['minimum_time'].values.astype(int)) == [1]
        assert list(result['maximum_time'].values.astype(str)) == ['nan']

    def test_binary_en_route_stop(self):
        """
        In the first observation, the train is EN_ROUTE to a station. In the next observation, it STOPPED_AT that
        station.

        Our output should be a trip log with a single row, recording the time at which the stop was made.
        """
        base = create_mock_action_log(actions=['EXPECTED_TO_ARRIVE_AT', 'STOPPED_AT'],
                                      stops=['999X', '999X'])
        first = base.head(1)
        second = base.tail(1).set_value(1, 'information_time', 1)
        actions = [first, second]

        result = processing.parse_tripwise_action_logs_into_trip_log(actions)

        assert len(result) == 1
        assert list(result['action'].values) == ['STOPPED_AT']
        assert list(result['minimum_time'].values.astype(int)) == [0]
        assert list(result['maximum_time'].values.astype(str)) == ['nan']

    def test_binary_stop_or_skip_en_route(self):
        """
        In the first observation, the train is EN_ROUTE to a station. In the next observation, it is EN_ROUTE to
        a different station, one further along in the record.

        Our output should be a trip log with two rows, one STOPPED_OR_SKIPPED at the first station,
        and one EXPECTED_TO_ARRIVE_AT in another.
        """
        base = create_mock_action_log(actions=['EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_DEPART_AT',
                                               'EXPECTED_TO_ARRIVE_AT',
                                               'EXPECTED_TO_ARRIVE_AT'],
                                      stops=['999X', '999X', '998X', '998X'])
        first = base.head(3)
        second = base.tail(1).set_value(3, 'information_time', 1)
        actions = [first, second]

        result = processing.parse_tripwise_action_logs_into_trip_log(actions)

        assert len(result) == 2
        assert list(result['action'].values) == ['STOPPED_OR_SKIPPED', 'EN_ROUTE_TO']
        assert list(result['minimum_time'].values.astype(int)) == [0, 1]
        assert list(result['maximum_time'].values.astype(str)) == ['1', 'nan']

    def test_binary_skip_en_route(self):
        """
        In the first observation, the train is EN_ROUTE to a station which it is going to skip. In the second
        observation the train is en route to another station further down the line.

        Our output should be a trip log with two rows. The first entry should be a STOPPED_OR_SKIPPED at the first
        station, and then the second should be an EN_ROUTE_TO at the second station.
        """
        base = create_mock_action_log(actions=['EXPECTED_TO_SKIP', 'EXPECTED_TO_ARRIVE_AT',
                                               'EXPECTED_TO_ARRIVE_AT'],
                                      stops=['999X', '998X', '998X'])
        first = base.head(2)
        second = base.tail(1).set_value(2, 'information_time', 1)
        actions = [first, second]

        result = processing.parse_tripwise_action_logs_into_trip_log(actions)

        assert len(result) == 2
        assert list(result['action'].values) == ['STOPPED_OR_SKIPPED', 'EN_ROUTE_TO']
        assert list(result['minimum_time'].values.astype(int)) == [0, 1]
        assert list(result['maximum_time'].values.astype(str)) == ['1', 'nan']

    def test_binary_skip_stop(self):
        """
        In the first observation, the train is EN_ROUTE to a station which it is going to skip. In the second
        observation the train is stopped at another station further down the line.

        Our output should be a trip log with two rows. The first entry should be a STOPPED_OR_SKIPPED at the first
        station, and then the second should be a STOPPED_AT at the second station.
        """
        base = create_mock_action_log(actions=['EXPECTED_TO_SKIP', 'EXPECTED_TO_ARRIVE_AT',
                                               'STOPPED_AT'],
                                      stops=['999X', '998X', '998X'])
        first = base.head(2)
        second = base.tail(1).set_value(2, 'information_time', 1)
        actions = [first, second]

        result = processing.parse_tripwise_action_logs_into_trip_log(actions)

        assert len(result) == 2
        assert list(result['action'].values) == ['STOPPED_OR_SKIPPED', 'STOPPED_AT']
        assert list(result['minimum_time'].values.astype(int)) == [0, 0]
        assert list(result['maximum_time'].values.astype(str)) == ['1', 'nan']


class FinalizationTests(unittest.TestCase):
    """
    Tests for finalization.

    Within the GTFS-Realtime log, a signal that a train trip is complete only comes in the form of that trip's
    messages no longer appearing in the queue in the next update. The most recently recorded message may be in any
    conceivable state prior to this occurring. Finalization is the procedure "capping off" any still to-be-arrived-at
    stations. Since this involves contextual knowledge about records appearing and not appearing in the data stream,
    this procedure is provided as a separate method.

    These tests ascertain that said method, `_finish_trip`, works as advertised.

    NB: it's easier to test this using this internal method because the requisite forward-facing method relies on the
    Google protobuf wrapper library, which produces objects that are neither constructable nor mutable.
    """
    def test_finalize_no_op(self):
        """
        Finalization should do nothing to trip logs that are already complete.
        """
        base = create_mock_action_log(actions=['STOPPED_AT'], stops=['999X'])
        trip = processing.parse_tripwise_action_logs_into_trip_log([base])
        result = processing._finish_trip(trip, np.nan)

        assert len(result) == 1
        assert list(result['action'].values) == ['STOPPED_AT']

    def test_finalize_en_route(self):
        """
        Finalization should cap off trips that are still EN_ROUTE.
        """
        base = create_mock_action_log(actions=['EXPECTED_TO_ARRIVE_AT'], stops=['999X'])
        trip = processing.parse_tripwise_action_logs_into_trip_log([base])
        result = processing._finish_trip(trip, np.nan)

        assert len(result) == 1
        assert list(result['action'].values) == ['STOPPED_OR_SKIPPED']

    def test_finalize_all(self):
        """
        Make sure that finalization works across columns as well.
        """
        base = create_mock_action_log(actions=['EXPECTED_TO_SKIP', 'EXPECTED_TO_ARRIVE_AT'], stops=['999X', '998X'])
        first = base.head(1)
        second = base.tail(1)

        trip = processing.parse_tripwise_action_logs_into_trip_log([first, second])
        result = processing._finish_trip(trip, 42)

        assert len(result) == 2
        assert list(result['action'].values) == ['STOPPED_OR_SKIPPED', 'STOPPED_OR_SKIPPED']
        assert list(result['maximum_time'].astype(int).values) == [42, 42]


class ReroutingTests(unittest.TestCase):
    """
    These tests make sure that trip logs work as expected when the train gets rerouted.
    """
    def test_en_route_reroute(self):
        """
        Behavior when en route, and rerouted to another en route, is that the earlier station(s) ought to be marked
        "STOPPED_OR_SKIPPED".
        """
        base = create_mock_action_log(actions=['EXPECTED_TO_ARRIVE_AT', 'EXPECTED_TO_ARRIVE_AT'],
                                      stops=['999X', '998X'])
        first = base.head(1)
        second = base.tail(1).set_value(1, 'information_time', 1)

        result = processing.parse_tripwise_action_logs_into_trip_log([first, second])

        assert len(result) == 2
        assert list(result['action'].values) == ['STOPPED_OR_SKIPPED', 'EN_ROUTE_TO']


class SmokeTests(unittest.TestCase):
    """
    Make sure that the user-facing wrapper method over all of the above works correctly. We only need to smoke test
    this because all of the core logic is covered in the tests above.
    """

    def setUp(self):
        from google.transit import gtfs_realtime_pb2

        with open("./data/gtfs_realtime_pull_1.dat", "rb") as f:
            gtfs_r0 = gtfs_realtime_pb2.FeedMessage()
            gtfs_r0.ParseFromString(f.read())
        with open("./data/gtfs_realtime_pull_2.dat", "rb") as f:
            gtfs_r1 = gtfs_realtime_pb2.FeedMessage()
            gtfs_r1.ParseFromString(f.read())

        self.gtfs_r0 = gtfs_r0
        self.gtfs_r1 = gtfs_r1

    def test_smoke(self):
        example_trip_messages = [[self.gtfs_r0.entity[0], self.gtfs_r0.entity[1]],
                                 [self.gtfs_r1.entity[0], self.gtfs_r1.entity[1]]]
        actions = [processing.parse_message_into_action_log(t_u, v_u, i) for (i, (t_u, v_u)) in
                   enumerate(example_trip_messages)]
        result = processing.parse_tripwise_action_logs_into_trip_log(actions)

        assert len(result) == 4
        assert list(result['action']) == ['STOPPED_AT', 'STOPPED_OR_SKIPPED', 'EN_ROUTE_TO', 'EN_ROUTE_TO']


class TripLogJoinTests(unittest.TestCase):
    """
    Out of necessity, we implement join logic: in other words, we have and use routines for combining trip logs
    corresponding with the same trip together. This allows us to consolidate two different trip logs representing
    two trips for different observatory "stretches" into unitary trip logs.

    The necessity of implementing this methodology comes out of practical considerations of library usage.
    """
    pass