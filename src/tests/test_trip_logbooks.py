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