docker buildx build \
 --tag magammon/riverlevel:latest \
 --platform linux/arm/v7,linux/arm64/v8,linux/amd64,linux/arm64/v8 \
 --builder container \
 --push .