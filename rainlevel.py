"""
This module takes environment agency river level and station data 
from their API and converts to prometheus metrics published through a webserver
"""
# keynsham station http://environment.data.gov.uk/flood-monitoring/id/stations/53107
# measure http://environment.data.gov.uk/flood-monitoring/id/measures/53107-rainfall-tipping_bucket_raingauge-t-15_min-mm

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
        MEASURE_API = os.environ['MEASURE_API']
        STATION_API = os.environ['STATION_API']

## If error raised use hardcoded values
except KeyError:
    print("Module not containerised, using hard coded values for measure and station APIs.")
    MEASURE_API = "https://environment.data.gov.uk/flood-monitoring/id/measures/531160-level-stage-i-15_min-mASD.json"
    STATION_API = "https://environment.data.gov.uk/flood-monitoring/id/stations/53107"

# define functions
def get_station_name(obj):
    """Function takes api output from EA API and returns name of station as string."""
    stationname = json.dumps(obj['items']['label'])
    return stationname.replace('"','')

def get_rainfall(obj): #TODO update so that this fails gracefully if the API isn't working.
    """Function takes api output from EA API and returns river level as float."""
    rainfall = json.dumps(obj['items']['latestReading']['value'])
    return float(rainfall)

def set_gauge():
    """Function calls API, feeds to get_rainfall and then sets prometheus guage."""
    ## get responses
    measure_response = rq.get(MEASURE_API, timeout=30)

    ## set river guage river level to output of get_rainfall function
    gauge_river_level.set(get_rainfall(measure_response.json()))

    time.sleep(READ_INTERVAL * READ_UNITS)

# initialise the gauges
## call the API to get the station JSON
initialise_gauge_station_response = rq.get(STATION_API, timeout=30)

## use get_station_name function to extract station name 'label'
SN = get_station_name(initialise_gauge_station_response.json())

SN_UNDERSCORES = get_station_name(initialise_gauge_station_response.json()).replace(', ','_').lower()

gauge_river_level = Gauge(f'{SN_UNDERSCORES}_river_level', f'River level at {SN}')

gauge_typical_level = Gauge(f'{SN_UNDERSCORES}_typical_level', f'Typical max level at {SN}')

gauge_max_record = Gauge(f'{SN_UNDERSCORES}_max_record', f'max record level at {SN}')

if __name__ == "__main__":
    #expose metrics
    METRICS_PORT = 8897
    start_http_server(METRICS_PORT)
    print(f"Serving sensor metrics on :{METRICS_PORT}")

    while True:
        set_gauge()
