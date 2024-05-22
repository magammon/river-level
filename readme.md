# River Level 🏞️
Docker based services that serves prometheus metrics of Environment Agency river level & rainfal API data using the prometheus python client.

Available in AMD, and ARM builds.
## Why?
Theres already a tool to scrape json api data and load it into prometheus [JSON Exporter](https://github.com/prometheus-community/json_exporter) but I couldn't get it to work. Because of this i thought it would be a good beginner's challenge to write a python program to do the same and then containerise it so i could run it on my home server.

## Deploy
### Running as a docker image
#### Docker Compose
1. `cd` to the project folder
1. Copy `docker-compose-example.yml` to `docker-compose.yml`
1. Update the four environmental variables (water level station, water level measure, rainfall station, rainfall measure) in the compose file 
1. Run `docker-compose up -d` to start the container
1. go to ipofmachine:8897 to check the prometheus guages are being published
#### Docker
In the terminal run:
```
docker run -d -i \
--name riverleveltest \
-p 8897:8897 \
-e RIVER_MEASURE_API=https://environment.data.gov.uk/flood-monitoring/id/measures/examplemeasure.json \
-e RIVER_STATION_API=https://environment.data.gov.uk/flood-monitoring/id/stations/examplestation.json \
-e RAIN_MEASURE_API=https://environment.data.gov.uk/flood-monitoring/id/measures/examplemeasure.json \
-e RAIN_STATION_API=https://environment.data.gov.uk/flood-monitoring/id/stations/examplestation \
-e METRICS_PORT=8897 \
magammon/riverlevel:latest
```
Ensure that you update the station, measure and metrics port environmental variables.

### Running the python program
 `riverlevel.py` will run outside of the docker container:
 1. Use pip to install the dependencies in `requirements.txt`
 2. Update the four variables (water level station, water level measure, rainfall station, rainfall measure) in `riverlevel.py`
 3. Run `python riverlevel.py`

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

## Setting your `prometheus.yml` file
To get prometheus to scrape the published gauges you need to update your `prometheus.yml` file i.e.

```
- job_name: 'json_export_river'
  scrape_interval: 60s
  honor_labels: true
  metrics_path: /probe
  static_configs:
    - targets:
      - 192.168.1.999:8897 # set to IP of the machine running the container. 8897 is the default port.
```

## To Do
- if the reading is 0m then skip updating gauge
