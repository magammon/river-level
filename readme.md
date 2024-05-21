# River Level
Docker based services that serves prometheus metrics of Environment Agency river level API data using the prometheus python client.

Available in AMD, and ARM builds.
## Why?
Theres already a tool to scrape json api data and load it into prometheus [JSON Exporter](https://github.com/prometheus-community/json_exporter). 
## Pre Reqs
- docker (including compose)

## Deploy
1. `cd` to the project folder
1. Copy `docker-compose-example.yml` to `docker-compose.yml`
1. Update the four environmental variables (water level station, water level measure, rainfall station, rainfall measure) in the compose file 
1. run `docker-compose up -d` to start the container
1. go to ipofmachine:8897 to check the prometheus guages are being published

## Finding a station and measure URL
- the documentation for the river-level api is available [here](https://environment.data.gov.uk/flood-monitoring/doc/reference) and for the rainfal api [here](https://environment.data.gov.uk/flood-monitoring/doc/rainfall).
- the simplest way to find stations and measures is to use the built in location function of the API.
- To find stations:
    - https://environment.data.gov.uk/flood-monitoring/id/stations.html?parameter=rainfall&lat=51.48&long=-2.77&dist=10 provides a list of rainfall stations within 10 km of portishead. Update the lat and long to your desired location to find local stations
    - https://environment.data.gov.uk/flood-monitoring/id/stations.html?parameter=level&lat=51.48&long=-2.77&dist=10 provides a list of water level stations within 10 km of portishead. Update the lat and long to your desired location to find local stations
    - Click on the link of the station you would like to use. Take the URL and update `.html` to `.json` to get the URL of the station to add to your `docker-compose.yml` file
- To find measures:
    - on your station page e.g. https://environment.data.gov.uk/flood-monitoring/id/stations/E72639.html the measures available at that station are listed below.
    - Click on the link of the measure you would like to use. Take the URL and update `.html` to `.json` to get the URL of the station to add to your `docker-compose.yml` file

## To Do
- if the reading is 0m then skip updating gauge
- set metrics port in python program using an environmental variable