import pandas as pd


def fetch_archival_gtfs_realtime_data(kind='gtfs', timestamp='2014-09-17-09-31'):
    """
    Returns archived GTFS data for a particular timestamp.

    Parameters
    ----------
    kind: {'gtfs', 'gtfs-l', 'gtfs-si'}
        Archival data is provided in these three rollups. The first one covers 1-6 and the S, the second covers the
        L, and the third, the Staten Island Railway.
    timestamp: str
        The timestamp associated with the data rollup. The files are time stamped at 01, 06, 11, 16, 21, 26, 31, 36,
        41, 46, 51, and 56 minutes after the hour, so only these times will be valid.
    """
    import requests
    from google.transit import gtfs_realtime_pb2

    feed = gtfs_realtime_pb2.FeedMessage()
    response = requests.get("https://datamine-history.s3.amazonaws.com/{0}-{1}".format(kind, timestamp))
    feed.ParseFromString(response.content)
    return feed


def parse_gtfs_into_action_log(feed):
    """
    Parses a GTFS-Realtime feed into a single pandas.DataFrame

    Parameters
    ----------
    feed, gtfs_realtime_pb2.FeedMessage object
        The feed being processed.
    """
    action_log = pd.DataFrame(columns=['trip_id', 'route_id', 'action', 'stop_id', 'timestamp'])

    # In the MTA case, alerts are provided at the end of the feed. Isolate those from the rest of the entries by
    # finding the breakpoint at which they appear. This is a harder process than one would expect due to the way that
    # the library is designed, hence the weirdness here.
    alert_breakpoint = None

    for i, entity in enumerate(reversed(feed.entity)):
        if str(entity.alert) == '':
            alert_breakpoint = len(feed.entity) - i
            break

    alerts = feed.entity[alert_breakpoint:] if alert_breakpoint else []

    # The rest of the entries are Trip Alert and Train Station entities.
    trips_breakpoint = alert_breakpoint if alert_breakpoint else len(feed.entity)

    for i in range(0, trips_breakpoint):
        message = feed.entity[i]

        if message.trip_update.trip.route_id == '':
            # This is a vehicle update message.
            # Since vehicle update messages always appear after trip update messages (is this true?),
            # we won't process them separately.
            pass
        else:
            # This is a trip update message.

            # To understand what this message means, we need to read information from the vehicle update also.
            # First, we need to verify that there is a vehicle update present at all.
            if alerts and i != alert_breakpoint - 1:
                has_associated_vehicle_update = feed.entity[i + 1].trip_update.trip.route_id == ''
            else:
                has_associated_vehicle_update = False
            trip_in_progress = has_associated_vehicle_update

            # Pass reading the actions into a helper function.
            if trip_in_progress:
                trip_update = feed.entity[i + 1]
                actions = parse_message_into_action_log(message, trip_update)
            else:
                actions = parse_message_into_action_log(message, None)

            action_log = action_log.append(actions)

    return action_log


def parse_message_into_action_log(message, vehicle_update):
    # If we are passed a vehicle update, then the trip must already be in progress.
    trip_in_progress = bool(vehicle_update)

    # The base of the log entry is the same for all possible entries.
    base = {
        'trip_id': message.trip_update.trip.trip_id,
        'route_id': message.trip_update.trip.route_id,
        'action': None,
        'stop_id': None,
        'timestamp': None
    }

    action_log = pd.DataFrame(columns=['trip_id', 'route_id', 'action', 'stop_id', 'timestamp'])

    # Hash map for current status enums to current status strings.
    vehicle_status_dict = {
        0: 'INCOMING_AT',
        1: 'STOPPED_AT',
        2: 'IN_TRANSIT_TO'
    }

    if trip_in_progress:
        vehicle_status = vehicle_status_dict[vehicle_update.vehicle.current_status]
        vehicle_status_poi = vehicle_update.vehicle.stop_id
    n_stops = len(message.trip_update.stop_time_update)

    for s_i, stop_time_update in enumerate(message.trip_update.stop_time_update):

        # If we do have one, we may continue.
        # Weirdness with detecting if we have arrival/departure times.
        has_arrival_time = str(stop_time_update.arrival) != ''
        has_departure_time = str(stop_time_update.departure) != ''
        stop_time_update_poi = stop_time_update.stop_id
        if trip_in_progress:
            stop_is_next_stop = stop_time_update_poi == vehicle_status_poi

        # If the trip is not in progress, and we are at the first index, then we will have only a planned
        # departure to account for.
        if not trip_in_progress and s_i == 0:
            assert not has_arrival_time
            assert has_departure_time

            struct = base.copy()
            struct.update({'action': 'EXPECTED_TO_DEPART_AT',
                           'stop_id': stop_time_update.stop_id,
                           'timestamp': stop_time_update.departure.time})
            action_log = action_log.append(struct, ignore_index=True)

        # If the trip is not in progress, and we are not at the first index nor the last index, then we will
        # have both types to account for.
        elif not trip_in_progress and s_i != 0 and n_stops != s_i + 1:
            assert has_arrival_time
            assert has_departure_time

            # Arrival.
            struct = base.copy()
            struct.update({'action': 'EXPECTED_TO_ARRIVE_AT',
                           'stop_id': stop_time_update.stop_id,
                           'timestamp': stop_time_update.arrival.time})
            action_log = action_log.append(struct, ignore_index=True)

            # Departure.
            struct = base.copy()
            struct.update({'action': 'EXPECTED_TO_DEPART_AT',
                           'stop_id': stop_time_update.stop_id,
                           'timestamp': stop_time_update.departure.time})
            action_log = action_log.append(struct, ignore_index=True)

        # If we are at the last index, then we will have only an arrival to account for.
        elif n_stops == s_i + 1:
            assert has_arrival_time
            assert not has_departure_time

            struct = base.copy()
            struct.update({'action': 'EXPECTED_TO_ARRIVE_AT',
                           'stop_id': stop_time_update.stop_id,
                           'timestamp': stop_time_update.arrival.time})
            action_log = action_log.append(struct, ignore_index=True)

        # If the trip is in progress, we have an arrival time, and we have an INCOMING_AT or IN_TRANSIT_TO
        # vehicle update, and the vehicle update and stop update in question are talking about the same
        # station, then we know that we are en route to a station, but haven't arrived there yet.
        elif trip_in_progress and vehicle_status in ['INCOMING_AT', 'IN_TRANSIT_TO'] and stop_is_next_stop:
            try:
                assert has_arrival_time
                assert has_departure_time
            except:
                import pdb; pdb.set_trace()
                pass

            # Arrival.
            struct = base.copy()
            struct.update({'action': 'EXPECTED_TO_ARRIVE_AT',
                           'stop_id': stop_time_update.stop_id,
                           'timestamp': stop_time_update.arrival.time})
            action_log = action_log.append(struct, ignore_index=True)

            # Departure.
            struct = base.copy()
            struct.update({'action': 'EXPECTED_TO_DEPART_AT',
                           'stop_id': stop_time_update.stop_id,
                           'timestamp': stop_time_update.departure.time})
            action_log = action_log.append(struct, ignore_index=True)

        # If the trip is in progress, we are STOPPED_AT, we are at the first station in the line, and the vehicle
        # update and stop update in question are talking about the same station, then we are currently stopped at the
        #  first station in the line, and will only have a departure time.
        elif trip_in_progress and vehicle_status == 'STOPPED_AT' and s_i == 0 and not has_arrival_time:
            assert has_departure_time

            struct = base.copy()
            struct.update({'action': 'STOPPED_AT',
                           'stop_id': stop_time_update.stop_id,
                           'timestamp': stop_time_update.arrival.time})
            action_log = action_log.append(struct, ignore_index=True)

        # If the trip is in progress, we are STOPPED_AT, and the vehicle update and stop update in question are
        # talking about the same station, then that arrival time should be the time at which this train arrived at
        # this station.
        elif trip_in_progress and vehicle_status == 'STOPPED_AT' and stop_is_next_stop:
            assert has_arrival_time
            assert has_departure_time

            struct = base.copy()
            struct.update({'action': 'STOPPED_AT',
                           'stop_id': stop_time_update.stop_id,
                           'timestamp': stop_time_update.arrival.time})
            action_log = action_log.append(struct, ignore_index=True)

        # If the trip is in progress, the vehicle update and stop update in question are not talking about the
        # same station, and the message is not the last one in the sequence, and both an arrival and
        # departure are present in the struct, then we have a forward estimate on when this train will arrive
        # at some other station further down the line (but not at the very end).
        #
        # We actually do the same thing in this case as in the first case, but to keep the logic neat let's
        # just replicate the code.
        elif trip_in_progress and not stop_is_next_stop and not n_stops == s_i + 1 and has_departure_time:
            assert has_arrival_time

            # Arrival.
            struct = base.copy()
            struct.update({'action': 'EXPECTED_TO_ARRIVE_AT',
                           'stop_id': stop_time_update.stop_id,
                           'timestamp': stop_time_update.arrival.time})
            action_log = action_log.append(struct, ignore_index=True)

            # Departure.
            struct = base.copy()
            struct.update({'action': 'EXPECTED_TO_DEPART_AT',
                           'stop_id': stop_time_update.stop_id,
                           'timestamp': stop_time_update.departure.time})
            action_log = action_log.append(struct, ignore_index=True)

        # If the vehicle update and stop update in question are not talking about the same station,
        # and the message is the last one in the sequence, then we have a forward estimate on when
        # this train will arrive at its endpoint station.
        elif trip_in_progress and not stop_is_next_stop and n_stops == s_i + 1 and not has_departure_time:
            assert has_arrival_time

            struct.update({'action': 'EXPECTED_TO_END_AT',
                           'stop_id': stop_time_update.stop_id,
                           'timestamp': stop_time_update.arrival.time})
            action_log = action_log.append(struct, ignore_index=True)

        # If the trip is in progress the vehicle update and stop update in question are not talking about the
        # same station, and the message is not the last one in the sequence, and only an arrival is present in
        # the struct, then we have a forward estimate on when this train will arrive at some other station
        # further down the line (but not at the very end), but at which it *will not stop*. In other words,
        # this indicates that this train is going to skip this stop in its service!
        elif trip_in_progress and not stop_is_next_stop and not n_stops == s_i + 1 and not has_departure_time:
            assert has_arrival_time

            struct = base.copy()
            struct.update({'action': 'EXPECTED_TO_SKIP',
                           'stop_id': stop_time_update.stop_id,
                           'timestamp': stop_time_update.arrival.time})
            action_log = action_log.append(struct, ignore_index=True)

        else:
            import pdb; pdb.set_trace()
            raise ValueError

    return action_log