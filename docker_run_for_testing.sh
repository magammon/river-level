#! /bin/zsh
docker run -d -i \
--name riverlevelalpine \
-p 8897:8897 \
-e RIVER_MEASURE_API=https://environment.data.gov.uk/flood-monitoring/id/measures/531160-level-stage-i-15_min-mASD.json \
-e RIVER_STATION_API=https://environment.data.gov.uk/flood-monitoring/id/stations/531160.json \
-e RAIN_MEASURE_API=https://environment.data.gov.uk/flood-monitoring/id/measures/531160-level-stage-i-15_min-mASD.json \
-e RAIN_STATION_API=https://environment.data.gov.uk/flood-monitoring/id/stations/53107 \
magammon/riverlevel:alpine