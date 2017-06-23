class TripSet:
    def __init__(self, line=None, service=None, trip_planned=None, trip_executed=None, alerts=None,
                 current_vehicle_update=None):
        """
        Parameters
        ----------
        line, str
            The line ("1", "A", "7", so on) on which this tripset occurs. Since trains occassionally get
            rerouted from one line onto another for part of their journey, it's best to think of the line as
            the decal on the train. In the gtfs-realtime parlance this is known as "route_short_name".
        service, Trip
            The route assigned to this line at the time that this tripset took place. Routes change in
            a number of circumstances: when the system gets updated, for example, or when regularly scheduled
            weekend service change kicks in.
        trip_planned, Trip or None
            The trip that was planned. Often, this will be exactly the same as the service.
        trip_executed, Trip or None
            The trip that was executed.
        alerts, list of Alert objects
            A list of alerts tied to this line in the period in question.
        """
        alerts = alerts if alerts else []

        self.line = line
        self.service = service
        self.trip_planned = trip_planned
        self.trip_executed = trip_executed
        self.alerts = alerts
        self.current_vehicle_update = current_vehicle_update

    def to_json(self):
        """
        Serialize to JSON.
        """
        return {
            'line': self.line,
            'service': self.service.to_json() if self.service else None,
            'trip_planned': self.trip_planned.to_json() if self.trip_planned else None,
            'trip_executed': self.trip_executed.to_json() if self.trip_planned else None,
            'alerts': [alert.to_json() for alert in self.alerts]
        }


class Trip():
    def __init__(self, id=None, stops=None, alerts=None):
        """
        Parameters
        ----------
        id, str or None
            The ID assigned to the trip in the MTA schema.
        stops, list of Stop objects
            The stops that this trip occurs along, in the order in which they occur.
        alerts, list of Alert objects
            A list of Alert objects corresponding with what alerts were active along what parts of the line.
        """
        self.id = id
        self.stops = stops if stops else []
        self.alerts = alerts if alerts else []

    def to_json(self):
        json_repr = dict(stops=[], alerts=[], id=self.id)
        for stop in self.stops:
            json_repr['stops'].append(stop.to_json())
        for alert in self.alerts:
            json_repr['alerts'].append(alert.to_json())
        return json_repr


class Stop():
    def __init__(self, id=None, name=None, coordinates=None, arrival_time=None, departure_time=None):
        """
        Parameters
        ----------
        id, str
        name, str
        latitude, float
        longitude, float
        arrival_time, str
        departure_time, str
        """
        self.id = id
        self.name = name
        self.coordinates = coordinates
        self.arrival_time = arrival_time
        self.departure_time = departure_time

    def to_json(self):
        return vars(self)


class Alert():
    def __init__(self, time_interval, text, sources):
        """
        Parameters
        ----------
        time_interval, list of two str objects
            Two ISO time strings corresponding with the best known start and end time for the alert being active.
        text, str
            The alert text.
        sources, list of str objects
            The sources for this alert. There are two sources that we are interested in, GTFS-Realtime and the
            MTA Alerts service. Examination shows that the MTA Alerts are reserved for widescale disruptions,
            while GTFS-Realtime also captures smaller events. Hence the need to track and distinguish. Options
            are "GTFS-Realtime" and "MTA Alerts".
        """
        self.time_interval = time_interval
        self.text = text
        self.sources = sources

    def to_json(self):
        return vars(self)


# Methods looking up data for routes.

def map_route_id_to_line(route_id):
    """FYI: What I'm calling a 'route' is a route_short_name in the GTFS-Realtime lexicon."""
    import pandas as pd
    route_id = str(route_id)
    return pd.read_csv("../data/gtfs/routes.txt").query('route_id == @route_id').iloc[0]['route_short_name']


def to_tripsets(feed):
    """
    Load GTFS-Realtime data into a list of TripSet entities.

    Parameters
    ----------
    feed, gtfs_realtime_pb2.FeedMessage object
        The FeedMessage parsed out of the GTFS-Realtime stream.
    """

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
    tripsets = []

    for i in range(0, trips_breakpoint):
        message = feed.entity[i]

        if message.trip_update.trip.route_id == '':
            # This is a vehicle update message.
            # This message contains a position and a projected arrival time.
            for tripset in tripsets:
                if message.vehicle.trip.trip_id == tripset.trip_planned.id:
                    tripset.current_vehicle_update = message

            # TODO: What happens when you don't find an exact match this way?
        else:
            # This is a trip update message.
            realtime_tripset = TripSet(
                line=map_route_id_to_line(message.trip_update.trip.route_id),
                service=None,  # knowing the service requires performing a match.
                trip_planned=map_trip_update_message_to_trip(message),
                trip_executed=None,
                alerts=None  # will be populated shortly
            )
            tripsets.append(realtime_tripset)

    return tripsets


def map_trip_update_message_to_trip(message):
    """
    Load a trip update message from GTFS-Realtime into a Trip.
    """
    trip_id = message.trip_update.trip.trip_id
    stops = []
    for stop in message.trip_update.stop_time_update:
        stops.append(Stop(id=stop.stop_id,
                          # name=[...], coordinates=[...],
                          arrival_time=stop.arrival.time, departure_time=stop.departure.time))
    return Trip(id=trip_id, stops=stops, alerts=[])
