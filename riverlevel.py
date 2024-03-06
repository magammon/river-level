import json
import time
import requests as rq
# Import Gauge and start_http_server from prometheus_client
from prometheus_client import Gauge, start_http_server

## set read interval
READ_INTERVAL = 1

## set read interval units. 1 = seconds, 60 = minutes, 3600 = hours, 86400 = days
READ_UNITS = 60

## set api uris
MEASURE_API = "https://environment.data.gov.uk/flood-monitoring/id/measures/531160-level-stage-i-15_min-mASD.json"

STATION_API = "https://environment.data.gov.uk/flood-monitoring/id/stations/531160.json"

## initialise the gauges

gauge_river_level = Gauge('keynsham_river_level', 'River level at Keynsham Rivermeads')

gauge_typical_level = Gauge('keynsham_typical_level', 'Typical max level at Keynsham Rivermeads')

gauge_max_record = Gauge('keynsham_max_record', 'max record level at Keynsham Rivermeads')

## define function getHeight which makes the json output look pretty and easy to understand
def getHeight(obj):
    """Function takes api output from EA API and returns river level as float."""
    height = json.dumps(obj['items']['latestReading']['value'])
    return float(height)

## define function getTypical which makes the json output look pretty and easy to understand
def getTypical(obj):
    """Function takes api output from EA API and returns information about station."""
    typical = json.dumps(obj['items']['stageScale']['typicalRangeHigh'])
    return float(typical)

## define function getTypical which makes the json output look pretty and easy to understand
def getRecordMax(obj):
    """Function takes api output from EA API and returns information about station."""
    recordmax = json.dumps(obj['items']['stageScale']['maxOnRecord']['value'])
    return float(recordmax)

## define function setGauge. Function calls API and then sets prometheus guage
def setGauge():
    """Function calls API, feeds to getHeight and then sets prometheus guage."""
    ## get responses
    measure_response = rq.get(MEASURE_API)
    station_response = rq.get(STATION_API)

    ## set river guage river level to output of getHeight function
    gauge_river_level.set(getHeight(measure_response.json()))
    gauge_typical_level.set(getTypical(station_response.json()))
    gauge_max_record.set(getRecordMax(station_response.json()))

    time.sleep(READ_INTERVAL * READ_UNITS)

if __name__ == "__main__":
    #expose metrics
    METRICS_PORT = 8897
    start_http_server(METRICS_PORT)
    print(f"Serving sensor metrics on :{METRICS_PORT}")

    while True:
        setGauge()
