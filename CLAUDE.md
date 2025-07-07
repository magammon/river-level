# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture

This project contains a single Python module that monitors UK Environment Agency flood monitoring APIs:

- **`riverlevel.py`**: Combined river level and rainfall monitoring application

The module follows this pattern:
1. Poll Environment Agency APIs for river/rainfall data
2. Extract readings using JSON parsing functions
3. Expose metrics via Prometheus HTTP server (default port 8897)
4. Run in infinite loop with configurable intervals

### Configuration Pattern

The module detects if running in a container via `CONTAINERISED=YES` environment variable:
- **Container mode**: Uses environment variables for API endpoints and metrics port
- **Standalone mode**: Uses hardcoded values in the Python file

### Key Environment Variables (Container Mode)

- `RIVER_MEASURE_API`: River level measurement endpoint
- `RIVER_STATION_API`: River station info endpoint  
- `RAIN_MEASURE_API`: Rainfall measurement endpoint
- `RAIN_STATION_API`: Rainfall station info endpoint
- `METRICS_PORT`: Prometheus metrics port

## Common Commands

### Running Locally
```bash
# Install dependencies
pip install -r requirements.txt

# Run application
python riverlevel.py
```

### Docker Operations
```bash
# Build image (includes Python syntax validation)
docker build -t riverlevel .
```
**Note**: The Docker build process includes automatic Python syntax validation using `py_compile`. Builds will fail if there are syntax errors in `riverlevel.py`, preventing deployment of broken code.

```bash
# Run container with environment variables
docker run -d -p 8897:8897 \
  -e RIVER_MEASURE_API=https://environment.data.gov.uk/flood-monitoring/id/measures/example.json \
  -e RIVER_STATION_API=https://environment.data.gov.uk/flood-monitoring/id/stations/example.json \
  -e RAIN_MEASURE_API=https://environment.data.gov.uk/flood-monitoring/id/measures/example.json \
  -e RAIN_STATION_API=https://environment.data.gov.uk/flood-monitoring/id/stations/example.json \
  -e METRICS_PORT=8897 \
  riverlevel

# Use docker-compose
cp docker-compose-example.yml docker-compose.yml
# Edit environment variables in docker-compose.yml
docker-compose up -d
```

### Metrics Access
- View metrics: `http://localhost:8897`
- Metrics are exposed in Prometheus format with station-specific labels

## API Integration

The project integrates with Environment Agency flood monitoring APIs:
- Station info: `https://environment.data.gov.uk/flood-monitoring/id/stations/{id}.json`
- Measurements: `https://environment.data.gov.uk/flood-monitoring/id/measures/{id}.json`

Functions extract specific fields:
- `get_height()`: River level readings
- `get_rainfall()`: Rainfall measurements  
- `get_station_name()`: Station labels for metrics
- `get_station_id()`: Station reference IDs
- `get_typical()`: Typical high water levels
- `get_record_max()`: Maximum recorded levels

## Deployment

The Docker image is built for AMD and ARM architectures and deployed via GitHub Actions workflows. The container runs as a single process with the Python application directly executing the monitoring loop.

## Improvement Opportunities

### Phase 1: Error Handling & Reliability
**Current Issues:**
1. Functions like `get_height()` and `get_rainfall()` will crash on API errors or missing data
2. No retry logic for failed API calls
3. Missing readings cause application crashes instead of graceful degradation

**Proposed Solutions:**
4. Add try/catch blocks to all API parsing functions with fallback values
5. Implement exponential backoff retry logic for API calls
6. Add input validation for environment variables and API responses
7. Skip metric updates on failures instead of crashing the application

### Phase 2: Code Structure & Quality
**Current Issues:**
8. Hardcoded station URLs embedded in code
9. Configuration inconsistency between container and standalone modes
10. Basic print statements instead of structured logging
11. Station info fetched every cycle when it's static data

**Proposed Solutions:**
12. Refactor into classes separating concerns (Configuration, APIClient, MetricsServer)
13. Move all hardcoded values to configuration files or environment variables
14. Replace print statements with Python's logging module
15. Cache static station info, only fetch dynamic measurements
16. Add configuration validation on startup

### Phase 3: Monitoring & Health
**Current Issues:**
17. No health check endpoint for container orchestration
18. No application metrics (only sensor data)
19. No observability into API call success/failure rates
20. Missing structured logging for debugging

**Proposed Solutions:**
21. Add `/health` endpoint for container health checks
22. Add Prometheus metrics for API call success/failure rates and response times
23. Implement structured JSON logging format
24. Add startup configuration validation logging

### Phase 4: Security & Deployment
**Current Issues:**
25. Docker container runs as root user
26. No health checks in Docker configuration
27. No graceful shutdown handling
28. Missing container resource limits

**Proposed Solutions:**
29. Create non-root user in Docker container
30. Add HEALTHCHECK directive to Dockerfile
31. Implement graceful shutdown signal handling
32. Add memory and CPU limits to container configuration

### Phase 5: Optional Enhancements
**Future Improvements:**
33. Add unit tests for core API parsing functions
34. Support configuration files (YAML/JSON) as alternative to environment variables
35. Add application health metrics to Prometheus output
36. Implement API rate limiting to respect Environment Agency limits
37. Add monitoring dashboard examples for Grafana

Each phase builds on the previous one, ensuring the application remains functional throughout the improvement process.