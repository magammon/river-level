"""
This module takes environment agency river level and station data 
from their API and converts to prometheus metrics published through a webserver
"""
import os
import json
import time
import requests as rq
# Import Gauge and start_http_server from prometheus_client
from prometheus_client import Gauge, start_http_server

# set read units. 1 = seconds, 60 = minutes, 3600 = hours, 86400 = days
READ_UNITS = 60

# set read interval of how many multiples of the read units between scrapes of the API
READ_INTERVAL = 1

# set api uris. These are set as docker environment variables
##MEASURE_API = os.environ['MEASURE_API']

##STATION_API = os.environ['STATION_API']

# set api uris for testing. comment out when building

MEASURE_API = "https://environment.data.gov.uk/flood-monitoring/id/measures/531160-level-stage-i-15_min-mASD.json"

STATION_API = "https://environment.data.gov.uk/flood-monitoring/id/stations/531160.json"

# define functions
def get_station_name(obj):
    """Function takes api output from EA API and returns name of station as string."""
    stationname = json.dumps(obj['items']['label'])
    return stationname.replace('"','')

def get_height(obj):
    """Function takes api output from EA API and returns river level as float."""
    height = json.dumps(obj['items']['latestReading']['value'])
    return float(height)

def get_typical(obj):
    """Function takes api output from EA API and returns information about station."""
    typical = json.dumps(obj['items']['stageScale']['typicalRangeHigh'])
    return float(typical)

def get_record_max(obj):
    """Function takes api output from EA API and returns information about station."""
    recordmax = json.dumps(obj['items']['stageScale']['maxOnRecord']['value'])
    return float(recordmax)

def set_gauge():
    """Function calls API, feeds to get_height and then sets prometheus guage."""
    ## get responses
    measure_response = rq.get(MEASURE_API, timeout=30)
    station_response = rq.get(STATION_API, timeout=30)

    ## set river guage river level to output of get_height function
    gauge_river_level.set(get_height(measure_response.json()))
    gauge_typical_level.set(get_typical(station_response.json()))
    gauge_max_record.set(get_record_max(station_response.json()))

    time.sleep(READ_INTERVAL * READ_UNITS)

# initialise the gauges
## call the API to get the station JSON
initialise_gauge_station_response = rq.get(STATION_API, timeout=30)

## use get_station_name function to extract station name 'label'
STATION_NAME = get_station_name(initialise_gauge_station_response.json())

gauge_river_level = Gauge('river_level', f'River level at {STATION_NAME}')

gauge_typical_level = Gauge('typical_level', f'Typical max level at {STATION_NAME}')

gauge_max_record = Gauge('max_record', f'max record level at {STATION_NAME}')

if __name__ == "__main__":
    #expose metrics
    METRICS_PORT = 8897
    start_http_server(METRICS_PORT)
    print(f"Serving sensor metrics on :{METRICS_PORT}")

    while True:
        set_gauge()
