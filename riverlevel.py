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

## set read units. 1 = seconds, 60 = minutes, 3600 = hours, 86400 = days
READ_UNITS = 60

## set read interval of how many multiples of the read units between scrapes of the API
READ_INTERVAL = 1

## set api uris. These are set as docker environment variables
MEASURE_API = os.environ['MEASURE_API']

STATION_API = os.environ['STATION_API']

## initialise the gauges

gauge_river_level = Gauge('keynsham_river_level', 'River level at Keynsham Rivermeads')

gauge_typical_level = Gauge('keynsham_typical_level', 'Typical max level at Keynsham Rivermeads')

gauge_max_record = Gauge('keynsham_max_record', 'max record level at Keynsham Rivermeads')

## define function get_height which makes the json output look pretty and easy to understand
def get_height(obj):
    """Function takes api output from EA API and returns river level as float."""
    height = json.dumps(obj['items']['latestReading']['value'])
    return float(height)

## define function get_typical which makes the json output look pretty and easy to understand
def get_typical(obj):
    """Function takes api output from EA API and returns information about station."""
    typical = json.dumps(obj['items']['stageScale']['typicalRangeHigh'])
    return float(typical)

## define function get_typical which makes the json output look pretty and easy to understand
def get_record_max(obj):
    """Function takes api output from EA API and returns information about station."""
    recordmax = json.dumps(obj['items']['stageScale']['maxOnRecord']['value'])
    return float(recordmax)

## define function set_gauge. Function calls API and then sets prometheus guage
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

if __name__ == "__main__":
    #expose metrics
    METRICS_PORT = 8897
    start_http_server(METRICS_PORT)
    print(f"Serving sensor metrics on :{METRICS_PORT}")

    while True:
        set_gauge()
