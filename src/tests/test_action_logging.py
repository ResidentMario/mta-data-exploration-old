"""
Tests the routines for generating action logs.
"""

import unittest
from google.transit import gtfs_realtime_pb2

import sys; sys.path.append("../")
# noinspection PyUnresolvedReferences
import processing


class TestParsingMessagesIntoActionLog(unittest.TestCase):
    """
    Tests parsing an individual (TripUpdate, VehicleUpdate) message tuple into an action log.

    This test suite is broken up into cases, with each case corresponding with one of the possible trip update states.
    """
    def setUp(self):
        with open("./data/gtfs_realtime_pull_1.dat", "rb") as f:
            gtfs_r0 = gtfs_realtime_pb2.FeedMessage()
            gtfs_r0.ParseFromString(f.read())
        with open("./data/gtfs_realtime_pull_2.dat", "rb") as f:
            gtfs_r1 = gtfs_realtime_pb2.FeedMessage()
            gtfs_r1.ParseFromString(f.read())

        self.gtfs_r0 = gtfs_r0
        self.gtfs_r1 = gtfs_r1

    def test_case_1(self):
        """
        The train is STOPPED_AT a station somewhere along the route. Hence, a vehicle update is also present. The
        train is not expected to skip any of the stops along the route. There should be a single STOPPED_AT entry in the
        first space in the action log, and every other station should get two entries, one each of
        EXPECTED_TO_ARRIVE_AT and EXPECTED_TO_DEPART_AT.

        As a convenience, also test that the last entry is EXPECTED_TO_ARRIVE_AT.
        """
        trip_update = self.gtfs_r0.entity[0]
        vehicle_update = self.gtfs_r0.entity[1]
        result = processing.parse_message_into_action_log(trip_update, vehicle_update, None)
        assert len(result) == 6
        assert result['action'].iloc[0] == 'STOPPED_AT'
        assert set(result['action'].value_counts().values) == {1, 3, 2}
        assert result['action'].iloc[-1] == 'EXPECTED_TO_ARRIVE_AT'

    def test_case_2(self):
        """
        The train is currently IN_TRANSIT_TO a station somewhere along the route.
        """
        trip_update = self.gtfs_r0.entity[24]
        vehicle_update = self.gtfs_r0.entity[25]
        result = processing.parse_message_into_action_log(trip_update, vehicle_update, None)
        assert len(result) == 33
        assert result['action'].iloc[0] == 'EXPECTED_TO_ARRIVE_AT'
        assert set(result['action'].value_counts().values) == {17, 16}

    def test_case_3(self):
        """
        The train is currently INCOMING_AT a station somewhere along the route.
        """
        trip_update = self.gtfs_r0.entity[32]
        vehicle_update = self.gtfs_r0.entity[33]
        result = processing.parse_message_into_action_log(trip_update, vehicle_update, None)
        assert len(result) == 13
        assert result['action'].iloc[0] == 'EXPECTED_TO_ARRIVE_AT'
        assert set(result['action'].value_counts().values) == {7, 6}

    def test_case_4(self):
        """
        The train is only preparing to start the journey.
        """
        trip_update = self.gtfs_r0.entity[108]
        vehicle_update = None
        result = processing.parse_message_into_action_log(trip_update, vehicle_update, None)
        assert len(result) == 44
        assert result['action'].iloc[0] == 'EXPECTED_TO_DEPART_AT'
        assert set(result['action'].value_counts().values) == {22}  # both 22

    def test_case_5(self):
        """
        The last record in the Trip Update message erroneously contains a departure.
        """
        trip_update = self.gtfs_r1.entity[207]
        vehicle_update = self.gtfs_r1.entity[208]
        result = processing.parse_message_into_action_log(trip_update, vehicle_update, None)
        assert len(result) == 1
        assert result['action'].iloc[0] == 'EXPECTED_TO_ARRIVE_AT'

    # TODO: Unit tests for more cases.
