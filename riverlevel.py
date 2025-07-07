"""
This module takes environment agency water level and rainfall measure and station data 
from their API and converts to prometheus metrics published through a webserver.
"""
import os
import json
import time
#import platform
import requests as rq
# Import Gauge and start_http_server from prometheus_client
from prometheus_client import Gauge, start_http_server

# set read units. 1 = seconds, 60 = minutes, 3600 = hours, 86400 = days
READ_UNITS = 60

# set read interval of how many multiples of the read units between scrapes of the API
READ_INTERVAL = 1

# set api uris.
## Try if environment variable has been set (e.g. that module running in container)
try:
    if os.environ['CONTAINERISED'] == 'YES':
        print("Module containerised, using environment values for measure and station APIs.")
        RIVER_MEASURE_API = os.environ['RIVER_MEASURE_API']
        RIVER_STATION_API = os.environ['RIVER_STATION_API']
        RAIN_MEASURE_API = os.environ['RAIN_MEASURE_API']
        RAIN_STATION_API = os.environ['RAIN_STATION_API']

## If error raised use hardcoded values
except KeyError:
    print("Module not containerised, using hard coded values for measure and station APIs.")
    RIVER_MEASURE_API = "https://environment.data.gov.uk/flood-monitoring/id/measures/531160-level-stage-i-15_min-mASD.json"
    RIVER_STATION_API = "https://environment.data.gov.uk/flood-monitoring/id/stations/531160.json"
    RAIN_MEASURE_API = "http://environment.data.gov.uk/flood-monitoring/id/measures/53107-rainfall-tipping_bucket_raingauge-t-15_min-mm.json"
    RAIN_STATION_API = "https://environment.data.gov.uk/flood-monitoring/id/stations/53107.json"

# define functions

def get_station_name(obj):
    """Function takes api output from EA API and returns name of station as string."""
    if obj is None:
        return "Unknown Station"
    try:
        return str(obj['items']['label'])
    except (KeyError, TypeError) as e:
        print(f"Unable to parse station name from API response: {e}")
        return "Unknown Station"

def get_height(obj):
    """Function takes api output from EA API and returns river level as float."""
    if obj is None:
        return 0.0
    try:
        return float(obj['items']['latestReading']['value'])
    except (KeyError, TypeError, ValueError) as e:
        print(f"Unable to parse river height from API response: {e}")
        return 0.0

def get_typical(obj):
    """Function takes api output from EA API and returns information about station."""
    if obj is None:
        return 0.0
    try:
        return float(obj['items']['stageScale']['typicalRangeHigh'])
    except (KeyError, TypeError, ValueError) as e:
        print(f"Unable to parse typical range from API response: {e}")
        return 0.0

def get_record_max(obj):
    """Function takes api output from EA API and returns information about station."""
    if obj is None:
        return 0.0
    try:
        return float(obj['items']['stageScale']['maxOnRecord']['value'])
    except (KeyError, TypeError, ValueError) as e:
        print(f"Unable to parse record max from API response: {e}")
        return 0.0

def get_station_grid_ref(obj):
    """Function takes api output from EA API and returns station grid ref."""
    if obj is None:
        return "UNKNOWN"
    try:
        return str(obj['items']['gridReference'])
    except (KeyError, TypeError) as e:
        print(f"Unable to parse grid reference from API response: {e}")
        return "UNKNOWN"

def get_station_id(obj):
    """Function takes api output from EA API and returns station ID."""
    if obj is None:
        return "UNKNOWN"
    try:
        return str(obj['items']['stationReference'])
    except (KeyError, TypeError) as e:
        print(f"Unable to parse station ID from API response: {e}")
        return "UNKNOWN"

def get_rainfall(obj):
    """Function takes api output from EA API and returns rainfall as float."""
    if obj is None:
        return 0.0
    try:
        return float(obj['items']['latestReading']['value'])
    except (KeyError, TypeError, ValueError) as e:
        print(f"Unable to parse rainfall from API response: {e}")
        return 0.0

def set_gauges():
    """Function calls API, feeds to get_height and then sets prometheus guage."""
    try:
        ## get responses
        river_measure_response = rq.get(RIVER_MEASURE_API, timeout=30)
        river_station_response = rq.get(RIVER_STATION_API, timeout=30)
        rain_measure_response = rq.get(RAIN_MEASURE_API, timeout=30)

        ## check response status codes
        if river_measure_response.status_code != 200:
            print(f"Error fetching river measure data: HTTP {river_measure_response.status_code}")
        else:
            gauge_river_level.set(get_height(river_measure_response.json()))

        if river_station_response.status_code != 200:
            print(f"Error fetching river station data: HTTP {river_station_response.status_code}")
        else:
            gauge_river_typical_level.set(get_typical(river_station_response.json()))
            gauge_river_max_record.set(get_record_max(river_station_response.json()))

        if rain_measure_response.status_code != 200:
            print(f"Error fetching rain measure data: HTTP {rain_measure_response.status_code}")
        else:
            gauge_rainfall.set(get_rainfall(rain_measure_response.json()))

    except rq.exceptions.ConnectionError as e:
        print(f"Network connection error when fetching API data: {e}")
    except rq.exceptions.Timeout as e:
        print(f"Request timeout when fetching API data: {e}")
    except rq.exceptions.RequestException as e:
        print(f"Network error when fetching API data: {e}")
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
    except Exception as e:
        print(f"Unexpected error in set_gauges: {e}")

    time.sleep(READ_INTERVAL * READ_UNITS)


def main():
    """Function starts metrics webserver"""
    #expose metrics
    try:
        if os.environ['CONTAINERISED'] == 'YES':
            print("Module containerised, using environment values for metrics port.")
            metrics_port = os.environ['METRICS_PORT']

    except KeyError:
        print("Module not containerised, using hard coded values for metrics API.")
        metrics_port = 8897

    start_http_server(int(metrics_port))
    print(f"Serving sensor metrics on :{metrics_port}")

    while True:
        set_gauges()

# initialise the gauges
## call the API to get the station JSON
try:
    initialise_river_gauge_station_response = rq.get(RIVER_STATION_API, timeout=30)
    initialise_rain_gauge_station_response = rq.get(RAIN_STATION_API, timeout=30)

    ## get river station name for gauge labels
    SN = get_station_name(initialise_river_gauge_station_response.json())

    SN_UNDERSCORES = get_station_name(initialise_river_gauge_station_response.json()).replace(', ','_').lower()

    ## get rain station id and grid ref for gauge label
    SID = get_station_id(initialise_rain_gauge_station_response.json())

    SGRIDREF = get_station_grid_ref(initialise_rain_gauge_station_response.json()).replace(' ','_').upper()

except rq.exceptions.ConnectionError as e:
    print(f"Network connection error during initialization: {e}")
    print("Using fallback values for gauge initialization")
    SN = "Unknown Station"
    SN_UNDERSCORES = "unknown_station"
    SID = "UNKNOWN"
    SGRIDREF = "UNKNOWN"
except rq.exceptions.Timeout as e:
    print(f"Request timeout during initialization: {e}")
    print("Using fallback values for gauge initialization")
    SN = "Unknown Station"
    SN_UNDERSCORES = "unknown_station"
    SID = "UNKNOWN"
    SGRIDREF = "UNKNOWN"
except rq.exceptions.RequestException as e:
    print(f"Network error during initialization: {e}")
    print("Using fallback values for gauge initialization")
    SN = "Unknown Station"
    SN_UNDERSCORES = "unknown_station"
    SID = "UNKNOWN"
    SGRIDREF = "UNKNOWN"
except Exception as e:
    print(f"Unexpected error during initialization: {e}")
    print("Using fallback values for gauge initialization")
    SN = "Unknown Station"
    SN_UNDERSCORES = "unknown_station"
    SID = "UNKNOWN"
    SGRIDREF = "UNKNOWN"

## Actually initialise the gauges
gauge_river_level = Gauge(f'{SN_UNDERSCORES}_river_level', f'River level at {SN}')

gauge_river_typical_level = Gauge(f'{SN_UNDERSCORES}_typical_level', f'Typical max level at {SN}')

gauge_river_max_record = Gauge(f'{SN_UNDERSCORES}_max_record', f'max record level at {SN}')

gauge_rainfall = Gauge(f'rainfall_osgridref_{SGRIDREF}', f'Rainfall level at environment agency station ID {SID} OS Grid Reference ({SGRIDREF})')

if __name__ == "__main__":
    main()
