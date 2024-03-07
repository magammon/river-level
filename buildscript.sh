# update tag to latest when doing final build. 
docker buildx build \
 --tag magammon/riverlevel:test \
 --platform linux/arm/v7,linux/arm64/v8,linux/amd64,linux/arm64/v8 \
 --builder container \
 --no-cache \
 --push .