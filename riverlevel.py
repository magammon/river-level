import json
import time
import requests as rq
# Import Gauge and start_http_server from prometheus_client
from prometheus_client import Gauge, start_http_server

## set read interval
READ_INTERVAL = 1

## set read interval units. 1 = seconds, 60 = minutes, 3600 = hours, 86400 = days
READ_UNITS = 60

## set api uri
API_URI = "https://environment.data.gov.uk/flood-monitoring/id/measures/531160-level-stage-i-15_min-mASD.json"

## initialise the gauges

gauge_river_level = Gauge('keynsham_river_level', 'River level at Keynsham Rivermeads')

## define function jprint which makes the json output look pretty and easy to understand
def jprint(obj):
    """Function takes api output from EA API and returns river level as float."""
    height = json.dumps(obj['items']['latestReading']['value'])
    return float(height)

## define function getheight. Function calls API and then sets prometheus guage
def getheight():
    """Function calls API, feeds to jprint and then sets prometheus guage."""
    ## get response
    response = rq.get(API_URI)
    ## set river guage river level to output of jprint function
    gauge_river_level.set(jprint(response.json()))
    print(gauge_river_level)
    time.sleep(READ_INTERVAL * READ_UNITS)

if __name__ == "__main__":
    #expose metrics
    METRICS_PORT = 8897
    start_http_server(METRICS_PORT)
    print("Serving sensor metrics on :{}".format(METRICS_PORT))

    while True:
        getheight()
