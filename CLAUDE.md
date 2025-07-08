# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture

This project contains a single Python module that monitors UK Environment Agency flood monitoring APIs:

- **`riverlevel.py`**: Combined river level and rainfall monitoring application

The module follows this pattern:
1. **Initialization**: Validate configuration and setup logging, health checks, and signal handlers
2. **API Polling**: Poll Environment Agency APIs with robust retry logic and error handling
3. **Data Processing**: Extract readings using validated JSON parsing functions with fallback values
4. **Metrics Export**: Expose metrics via Prometheus HTTP server (default port 8897)
5. **Health Monitoring**: Provide health check endpoint on port 8898 for container orchestration
6. **Graceful Operation**: Handle failures gracefully with degraded mode and structured logging

### Key Features
- **Error Handling**: Comprehensive try/catch blocks with exponential backoff retry logic
- **Health Checks**: Dedicated health endpoint with detailed API status reporting
- **Structured Logging**: JSON-formatted logs with rotation and console output
- **Graceful Shutdown**: SIGTERM/SIGINT signal handling for clean shutdowns
- **Monitoring**: Extensive Prometheus metrics for API calls, errors, and application health
- **Configuration Validation**: Startup validation of environment variables and API endpoints
- **Degraded Mode**: Continues operating with partial functionality when APIs are unavailable

### Configuration Pattern

The module detects if running in a container via `CONTAINERISED=YES` environment variable:
- **Container mode**: Uses environment variables for API endpoints and metrics port with validation
- **Standalone mode**: Uses hardcoded values in the Python file

### Key Environment Variables (Container Mode)

- `RIVER_MEASURE_API`: River level measurement endpoint
- `RIVER_STATION_API`: River station info endpoint  
- `RAIN_MEASURE_API`: Rainfall measurement endpoint
- `RAIN_STATION_API`: Rainfall station info endpoint
- `METRICS_PORT`: Prometheus metrics port

### Configuration Validation

The application performs comprehensive validation on startup:
- **URL Format**: Validates API endpoint URLs and warns about HTTP vs HTTPS
- **Port Range**: Ensures metrics port is within valid range (1-65535)
- **Required Variables**: Checks all required environment variables are present
- **Fast Fail**: Application exits immediately if configuration is invalid
- **Sanitized Logging**: Logs configuration with sensitive data removed

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

### Health Check Access
- Health endpoint: `http://localhost:8898/health`
- Returns JSON with detailed application and API status
- Used by Docker health checks for container orchestration

### Docker Health Checks
The container includes automatic health checking:
```bash
# Check container health status
docker ps  # Look for "healthy" status

# View health check logs
docker inspect --format='{{json .State.Health}}' <container_name>

# Manual health check
curl http://localhost:8898/health
```

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

## Health Checks

The application provides a comprehensive health check endpoint for monitoring and container orchestration:

### Health Check Endpoint
- **URL**: `http://localhost:8898/health`
- **Method**: GET
- **Response Format**: JSON

### Health Status Levels
- **healthy**: All APIs operational and application fully functional
- **degraded**: Some APIs unavailable but service continues with partial functionality
- **unhealthy**: All APIs unavailable (returns HTTP 503)

### Health Check Response
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "apis": {
    "river_station": true,
    "rain_station": true
  },
  "initialization": {
    "river_station_initialized": true,
    "rain_station_initialized": true
  },
  "metrics": {
    "last_successful_river_update": 1704110400,
    "last_successful_rain_update": 1704110400
  }
}
```

### Docker Health Check
The Dockerfile includes a built-in health check that calls the health endpoint:
```bash
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import requests; requests.get('http://localhost:8898/health').raise_for_status()"
```

## Monitoring & Metrics

The application provides extensive monitoring capabilities through Prometheus metrics:

### Prometheus Metrics Port
- **Default**: `8897`
- **Configurable**: Via `METRICS_PORT` environment variable

### Core Sensor Metrics
- `{station_name}_river_level`: Current river level reading
- `{station_name}_typical_level`: Typical high water level for the station
- `{station_name}_max_record`: Maximum recorded level for the station
- `rainfall_osgridref_{grid_ref}`: Rainfall measurements by grid reference

### API Monitoring Metrics
- `api_request_failures_total`: Total API request failures by endpoint and error type
- `api_request_duration_seconds`: API request duration histogram by endpoint
- `api_request_success_total`: Total successful API requests by endpoint
- `api_last_success_timestamp`: Timestamp of last successful API call by endpoint

### Application Health Metrics
- `riverlevel_initialization_success_total`: Successful API initializations by type
- `riverlevel_initialization_failure_total`: Failed API initializations by type
- `riverlevel_startup_seconds`: Application startup time histogram
- `riverlevel_application_start_timestamp`: Application start timestamp
- `riverlevel_degraded_mode_active`: Whether application is in degraded mode (0/1)

## Logging

The application implements structured logging with both human-readable console output and machine-readable JSON file logging:

### Log Outputs
- **Console**: Human-readable format for real-time monitoring
- **File**: JSON format in `riverlevel.log` with rotation (10MB files, 5 backups)

### Log Levels
- **INFO**: General application flow and successful operations
- **WARNING**: Recoverable issues and fallback usage
- **ERROR**: API failures and retry attempts
- **DEBUG**: Detailed monitoring cycle information
- **CRITICAL**: Fatal errors requiring immediate attention

### Structured Log Fields
JSON log entries include:
- `timestamp`: ISO format timestamp
- `level`: Log level (INFO, WARNING, ERROR, etc.)
- `message`: Human-readable message
- `endpoint`: API endpoint being called
- `response_time`: API response time in seconds
- `status_code`: HTTP status code
- `error_type`: Classification of error (connection_error, timeout, etc.)
- `startup_phase`: Application startup phase
- `fallback_used`: Whether fallback values were used

### Log Rotation
- **Max Size**: 10MB per log file
- **Backup Count**: 5 files retained
- **Automatic**: Rotation handled by Python's RotatingFileHandler

## Deployment

The Docker image is built for AMD and ARM architectures and deployed via GitHub Actions workflows. The container runs as a single process with the Python application directly executing the monitoring loop.

### Container Features
- **Multi-architecture**: Supports both AMD64 and ARM64 architectures
- **Health checks**: Built-in Docker health checks with configurable intervals
- **Graceful shutdown**: Responds to SIGTERM/SIGINT signals for clean shutdowns
- **Logging**: Structured JSON logging with automatic rotation
- **Configuration validation**: Fast-fail startup validation prevents broken deployments

### Container Ports
- **8897**: Prometheus metrics endpoint (configurable via `METRICS_PORT`)
- **8898**: Health check endpoint (fixed port)

### Security Considerations
- **Syntax validation**: Docker build includes Python syntax validation to prevent deployment of broken code
- **Configuration validation**: Environment variables validated on startup
- **Health monitoring**: Continuous health checks enable rapid failure detection
- **Graceful degradation**: Application continues operating with partial functionality during API outages

### Production Deployment
The application is designed for production use with:
- **Robust error handling**: Comprehensive exception handling with fallback values
- **Monitoring integration**: Extensive Prometheus metrics for observability
- **Health checks**: Container orchestration compatible health endpoints
- **Structured logging**: Machine-readable logs for log aggregation systems
- **Configuration management**: Environment-based configuration with validation

## Completed Improvements

The following improvements have been successfully implemented:

### ✅ Error Handling & Reliability
- **Robust API parsing**: All functions (`get_height()`, `get_rainfall()`, etc.) now include comprehensive try/catch blocks with fallback values
- **Exponential backoff retry**: Implemented using urllib3.util.Retry with 5 retries and exponential backoff
- **Graceful degradation**: Application continues operating with partial functionality when APIs are unavailable
- **Input validation**: Environment variables and API responses are validated on startup and during operations

### ✅ Monitoring & Health
- **Health check endpoint**: `/health` endpoint on port 8898 with detailed API status reporting
- **Application metrics**: Extensive Prometheus metrics for API calls, errors, response times, and application health
- **Structured logging**: JSON-formatted logs with rotation, plus human-readable console output
- **Configuration validation**: Startup validation with detailed logging of configuration status

### ✅ Security & Deployment
- **Docker health checks**: Built-in HEALTHCHECK directive calling health endpoint
- **Graceful shutdown**: SIGTERM/SIGINT signal handling for clean shutdowns
- **Configuration validation**: Comprehensive startup validation with fast-fail approach

### ✅ Code Structure & Quality
- **Structured logging**: Python's logging module with JSON formatting and rotation
- **Static data caching**: Station info cached during initialization, only measurements fetched repeatedly
- **Configuration consistency**: Unified configuration pattern with comprehensive validation

## Remaining Improvement Opportunities

### Phase 1: Code Organization
**Current State**: Application is functional but could benefit from better organization
- **Refactor into classes**: Separate concerns (Configuration, APIClient, MetricsServer, HealthChecker)
- **Extract configuration management**: Create dedicated configuration class with validation
- **Modularize API clients**: Separate river and rain API clients

### Phase 2: Security & Deployment
**Current State**: Basic container security in place, but could be enhanced
- **Non-root user**: Docker container currently runs as root user
- **Container resource limits**: Add memory and CPU limits to container configuration
- **Security scanning**: Implement container vulnerability scanning in CI/CD

### Phase 3: Testing & Quality
**Current State**: No automated testing framework in place
- **Unit tests**: Add tests for core API parsing functions
- **Integration tests**: Test API integration with mock responses
- **Performance tests**: Validate application performance under load

### Phase 4: Optional Enhancements
**Future Improvements:**
- **Configuration files**: Support YAML/JSON configuration as alternative to environment variables
- **API rate limiting**: Implement respectful rate limiting for Environment Agency APIs
- **Monitoring dashboard**: Create Grafana dashboard examples for metrics visualization
- **Data persistence**: Optional local caching of historical data
- **Multi-station support**: Support monitoring multiple stations simultaneously

Each improvement builds on the existing robust foundation, ensuring the application remains reliable throughout enhancement.