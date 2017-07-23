"""
Tests the routines for generating action logs.

A single GTFS-Realtime update contains three types of messages: trip updates, vehicle updates, and alerts. In our
code, we use the former two message types to build "action logs"---a pandas DataFrame representing a set of
observations on the state of the system at some time.

Taking feed messages and producing action logs out of them is the first step in our processing pipeline.

This test suite ascertains that we correctly construct action logs for all of our possible trip construct cases.
"""

import unittest
from google.transit import gtfs_realtime_pb2

import sys; sys.path.append("../")
# noinspection PyUnresolvedReferences
import processing


class TestParsingMessagesIntoActionLog(unittest.TestCase):
    def setUp(self):
        # TODO: Verify that the statement below is actually true, in the case of gtfs_r1.
        # NB: Filenames are positions in a five-minute-resolution log sequence dating from 2014-09-18-09.
        # This same test sequence is used throughout the development notebooks.
        with open("./data/gtfs_realtime_pull_1.dat", "rb") as f:
            gtfs_r0 = gtfs_realtime_pb2.FeedMessage()
            gtfs_r0.ParseFromString(f.read())
        with open("./data/gtfs_realtime_pull_2.dat", "rb") as f:
            gtfs_r1 = gtfs_realtime_pb2.FeedMessage()
            gtfs_r1.ParseFromString(f.read())
        with open("./data/gtfs_realtime_pull_8.dat", "rb") as f:
            gtfs_r8 = gtfs_realtime_pb2.FeedMessage()
            gtfs_r8.ParseFromString(f.read())

        self.gtfs_r0 = gtfs_r0
        self.gtfs_r1 = gtfs_r1
        self.gtfs_r8 = gtfs_r8

    def test_case_1(self):
        """
        The train is STOPPED_AT a station somewhere along the route. Therefore, a vehicle update is also present. The
        train is not expected to skip any of the stops along the route. There should be a single STOPPED_AT entry in
        the first space in the action log. Every other station should get two entries, one each of
        EXPECTED_TO_ARRIVE_AT and EXPECTED_TO_DEPART_AT, except for the final station, which is only
        EXPECTED_TO_ARRIVE_AT.
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
        The train is currently IN_TRANSIT_TO a station somewhere along the route. Therefore, a vehicle update is
        also present. The train is not expected to skip any of the stops along the route. Every
        station except for the last has an EXPECTED_TO_ARRIVE_AT and EXPECTED_TO_DEPART_AT entry. The last only has
        an EXPECTED_TO_ARRIVE_AT entry."""
        trip_update = self.gtfs_r0.entity[24]
        vehicle_update = self.gtfs_r0.entity[25]
        result = processing.parse_message_into_action_log(trip_update, vehicle_update, None)
        assert len(result) == 33
        assert result['action'].iloc[0] == 'EXPECTED_TO_ARRIVE_AT'
        assert set(result['action'].value_counts().values) == {17, 16}

    def test_case_3(self):
        """
        The train is currently INCOMING_AT a station somewhere along the route. This case is treated the same was as
        the case above.
        """
        trip_update = self.gtfs_r0.entity[32]
        vehicle_update = self.gtfs_r0.entity[33]
        result = processing.parse_message_into_action_log(trip_update, vehicle_update, None)
        assert len(result) == 13
        assert result['action'].iloc[0] == 'EXPECTED_TO_ARRIVE_AT'
        assert set(result['action'].value_counts().values) == {7, 6}

    def test_case_4(self):
        """
        The train is preparing to start its trip. A vehicle update is not present. The train is not expected to skip
        any of the stops along the route. Every station except for the first and last has an EXPECTED_TO_ARRIVE_AT and
        EXPECTED_TO_DEPART_AT entry. The last only has an EXPECTED_TO_ARRIVE_AT entry. The first only has an
        EXPECTED_TO_DEPART_AT entry.
        """
        trip_update = self.gtfs_r0.entity[108]
        vehicle_update = None
        result = processing.parse_message_into_action_log(trip_update, vehicle_update, None)
        assert len(result) == 44
        assert result['action'].iloc[0] == 'EXPECTED_TO_DEPART_AT'
        assert set(result['action'].value_counts().values) == {22}  # both 22

    def test_case_5(self):
        """
        The train is currently IN_TRANSIT_TO the final stop on its route. A vehicle update is present. The only row
        has an EXPECTED_TO_ARRIVE_AT entry.
        """
        trip_update = self.gtfs_r0.entity[14]
        vehicle_update = self.gtfs_r0.entity[15]
        result = processing.parse_message_into_action_log(trip_update, vehicle_update, None)
        assert len(result) == 1
        assert result['action'].iloc[0] == 'EXPECTED_TO_ARRIVE_AT'

    def test_case_6(self):
        """
        The train is currently INCOMING_AT the final stop on its route. A vehicle update is present. The only row
        has an EXPECTED_TO_ARRIVE_AT entry.
        """
        trip_update = self.gtfs_r0.entity[14]
        vehicle_update = self.gtfs_r0.entity[15]
        vehicle_update.vehicle.current_status = 2  # IN_TRANSIT_TO -> INCOMING_AT
        result = processing.parse_message_into_action_log(trip_update, vehicle_update, None)
        assert len(result) == 1
        assert result['action'].iloc[0] == 'EXPECTED_TO_ARRIVE_AT'

    def test_case_7(self):
        """
        The train is currently STOPPED_AT the final stop on its route. A vehicle update is present. The only row
        has a STOPPED_AT entry.
        """
        trip_update = self.gtfs_r0.entity[14]
        vehicle_update = self.gtfs_r0.entity[15]
        vehicle_update.vehicle.current_status = 1  # IN_TRANSIT_TO -> STOPPED_AT

        result = processing.parse_message_into_action_log(trip_update, vehicle_update, None)
        assert len(result) == 1
        assert result['action'].iloc[0] == 'STOPPED_AT'

    def test_case_8(self):
        """
        The train is somewhere along its trip, and follows all of the same rules as the similar earlier test cases
        thereof. However, it is also expected to skip one or more stops along its route. Separately, make sure that
        such trips are correctly populated.

        There are actually two such cases. In the first case, we have an intermediate station with only a departure.
        In the second, an intermediate station with only an arrival.

        One hopes that there isn't some special meaning attached to the difference between the two.
        """
        # First subcase.
        trip_update = self.gtfs_r8.entity[99]
        vehicle_update = self.gtfs_r8.entity[100]

        result = processing.parse_message_into_action_log(trip_update, vehicle_update, None)
        assert len(result) == 54
        assert result.iloc[34]['action'] == 'EXPECTED_TO_SKIP'

        # Second subcase.
        trip_update = self.gtfs_r0.entity[109]
        vehicle_update = self.gtfs_r8.entity[110]

        result = processing.parse_message_into_action_log(trip_update, vehicle_update, None)
        assert len(result) == 38
        assert result.iloc[20]['action'] == 'EXPECTED_TO_SKIP'

    def test_case_error_1(self):
        """
        The last record in the Trip Update message erroneously contains a departure. This is an error in the
        GTFS-Realtime output that was found, by trail and error, to occur more than once.
        """
        trip_update = self.gtfs_r1.entity[207]
        vehicle_update = self.gtfs_r1.entity[208]
        result = processing.parse_message_into_action_log(trip_update, vehicle_update, None)
        assert len(result) == 1
        assert result['action'].iloc[0] == 'EXPECTED_TO_ARRIVE_AT'
