"""
Tests the synthetic routing routines.

This a very simple theoretical algorithm, so it's possible to prove its correctness with just a little bit of work.
"""

import unittest

import sys; sys.path.append("../")
# noinspection PyUnresolvedReferences
import processing


class TestSynthesizeStationLists(unittest.TestCase):
    def test_concatenated_route(self):
        result = processing.synthesize_station_lists(['A', 'B', 'C'], ['D', 'E', 'F'])
        assert result == ['A', 'B', 'C', 'D', 'E', 'F']

    def test_pivoted_route(self):
        result = processing.synthesize_station_lists(['A', 'B', 'D'], ['C', 'D', 'E'])
        assert result == ['A', 'B', 'D', 'E']

    def test_same_route(self):
        result = processing.synthesize_station_lists(['A', 'B', 'C'], ['A', 'B', 'C'])
        assert result == ['A', 'B', 'C']

    def test_empty_route(self):
        result = processing.synthesize_station_lists([], ['A', 'B', 'C'])
        assert result == ['A', 'B', 'C']

        result = processing.synthesize_station_lists(['A', 'B', 'C'], [])
        assert result == ['A', 'B', 'C']

    def test_doubly_empty_route(self):
        result = processing.synthesize_station_lists([], [])
        assert result == []


class TestExtractSyntheticRouteFromStationLists(unittest.TestCase):
    def test_it_works(self):
        result = processing.extract_synthetic_route_from_station_lists([['A', 'B', 'C'], ['D', 'E', 'F'], ['G', 'H']])
        assert result == ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']


class TestTripWiseExtract(unittest.TestCase):
    def test_it_works(self):
        import pandas as pd
        tripwise_1 = pd.read_csv("./data/S02R_tripwise_action_log_1.csv")
        tripwise_2 = pd.read_csv("./data/S02R_tripwise_action_log_2.csv")
        result = processing.extract_synthetic_route_from_tripwise_action_logs([tripwise_1, tripwise_2])
        assert result == ['137S', '138S', '139S', '140S']
