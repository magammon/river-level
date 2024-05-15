"""
This module takes environment agency river level and station data 
from their API and converts to prometheus metrics published through a webserver
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
    RAIN_MEASURE_API = "http://environment.data.gov.uk/flood-monitoring/id/measures/53107-rainfall-tipping_bucket_raingauge-t-15_min-mm"
    RAIN_STATION_API = "https://environment.data.gov.uk/flood-monitoring/id/stations/53107"

# define functions


def get_station_name(obj):
    """Function takes api output from EA API and returns name of station as string."""
    stationname = json.dumps(obj['items']['label'])
    return stationname.replace('"','')

def get_height(obj): #TODO update so that this fails gracefully if the API isn't working.
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

def get_station_grid_ref(obj):
    """Function takes api output from EA API and returns station grid ref."""
    station_grid_ref = json.dumps(obj['items']['gridReference'])
    return station_grid_ref.replace('"','')

def get_station_id(obj):
    """Function takes api output from EA API and returns station ID."""
    station_id = json.dumps(obj['items']['stationReference'])
    return station_id.replace('"','')

def get_rainfall(obj): #TODO update so that this fails gracefully if the API isn't working.
    """Function takes api output from EA API and returns river level as float."""
    rainfall = json.dumps(obj['items']['latestReading']['value'])
    return float(rainfall)

def set_gauges():
    """Function calls API, feeds to get_height and then sets prometheus guage."""
    ## get responses
    river_measure_response = rq.get(RIVER_MEASURE_API, timeout=30)
    river_station_response = rq.get(RIVER_STATION_API, timeout=30)
    rain_measure_response = rq.get(RAIN_MEASURE_API, timeout=30)

    ## set river guage river level to output of get_height function
    gauge_river_level.set(get_height(river_measure_response.json()))
    gauge_river_typical_level.set(get_typical(river_station_response.json()))
    gauge_river_max_record.set(get_record_max(river_station_response.json()))
    gauge_rainfall.set(get_rainfall(rain_measure_response.json()))

    time.sleep(READ_INTERVAL * READ_UNITS)


def main():
    """Function starts metrics webserver"""
    #expose metrics
    metrics_port = 8897
    start_http_server(metrics_port)
    print(f"Serving sensor metrics on :{metrics_port}")

    while True:
        set_gauges()

# initialise the gauges
## call the API to get the station JSON
initialise_river_gauge_station_response = rq.get(RIVER_STATION_API, timeout=30)
initialise_rain_gauge_station_response = rq.get(RAIN_STATION_API, timeout=30)

## get river station name for gauge labels
SN = get_station_name(initialise_river_gauge_station_response.json())

SN_UNDERSCORES = get_station_name(initialise_river_gauge_station_response.json()).replace(', ','_').lower()

## get rain station id and grid ref for gauge label
SID = get_station_id(initialise_rain_gauge_station_response.json())

SGRIDREF = get_station_grid_ref(initialise_rain_gauge_station_response.json()).replace(' ','_').upper()

## Actually initialise the gauges
gauge_river_level = Gauge(f'{SN_UNDERSCORES}_river_level', f'River level at {SN}')

gauge_river_typical_level = Gauge(f'{SN_UNDERSCORES}_typical_level', f'Typical max level at {SN}')

gauge_river_max_record = Gauge(f'{SN_UNDERSCORES}_max_record', f'max record level at {SN}')

gauge_rainfall = Gauge(f'rainfall_osgridref_{SGRIDREF}', f'Rainfall level at environment agency station ID {SID} OS Grid Reference ({SGRIDREF})')

if __name__ == "__main__":
    main()
