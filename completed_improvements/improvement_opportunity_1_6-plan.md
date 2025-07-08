# Phase 1: Error Handling & Reliability Implementation Plan

## Section 6: Implement comprehensive structured logging

### Implementation Overview
This section replaces the current basic JSON logging with a comprehensive dual-output logging system that provides both human-readable console output and structured JSON file logging for better debugging and monitoring.

### Current State Analysis
The current code (riverlevel.py:23-58) has:
- Basic `JsonFormatter` class with limited fields
- Single console handler with JSON output
- No file logging capability
- Missing response time tracking
- No dual-format logging (console vs file)

### Implementation Steps

#### Step 1: Replace current logging setup (Lines 23-58)
**Current code to replace:**
```python
# Lines 23-58: Current JsonFormatter class and basic logging setup
```

**Replace with:**
```python
import logging
import logging.handlers
import json
import sys

def setup_logging():
    """Configure structured logging with both console and file output."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Remove default handlers to avoid duplicates
    logger.handlers.clear()
    
    # Console handler with simple format for human readability
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler with JSON format for structured logging
    file_handler = logging.handlers.RotatingFileHandler(
        'riverlevel.log', maxBytes=10485760, backupCount=5  # 10MB files, 5 backups
    )
    file_handler.setLevel(logging.DEBUG)
    
    class JSONFormatter(logging.Formatter):
        def format(self, record):
            log_entry = {
                'timestamp': self.formatTime(record, '%Y-%m-%d %H:%M:%S'),
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno
            }
            
            # Add exception info if present
            if record.exc_info:
                log_entry['exception'] = self.formatException(record.exc_info)
            
            # Add extra fields if present
            if hasattr(record, 'endpoint'):
                log_entry['endpoint'] = record.endpoint
            if hasattr(record, 'response_time'):
                log_entry['response_time'] = record.response_time
            if hasattr(record, 'status_code'):
                log_entry['status_code'] = record.status_code
            if hasattr(record, 'api_endpoint'):
                log_entry['api_endpoint'] = record.api_endpoint
            if hasattr(record, 'fallback_used'):
                log_entry['fallback_used'] = record.fallback_used
            if hasattr(record, 'error_type'):
                log_entry['error_type'] = record.error_type
            if hasattr(record, 'http_status'):
                log_entry['http_status'] = record.http_status
            if hasattr(record, 'startup_phase'):
                log_entry['startup_phase'] = record.startup_phase
                
            return json.dumps(log_entry)
    
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)
    
    return logger

# Initialize logging at startup
logger = setup_logging()
```

#### Step 2: Enhance make_api_call_with_retry function (Lines 483-519)
**Current function location:** riverlevel.py:483-519

**Required changes:**
1. Add response time tracking to log entries
2. Add structured logging with endpoint and URL context
3. Ensure all log messages include response_time field

**Updated function:**
```python
def make_api_call_with_retry(url, endpoint_name="unknown"):
    """Make API call with comprehensive logging including response time tracking."""
    logger.info(f"Making API call to {endpoint_name}", extra={'endpoint': endpoint_name, 'url': url})
    
    try:
        with api_call_context(endpoint_name):
            start_time = time.time()
            response = api_session.get(url, timeout=30)
            response_time = time.time() - start_time
            
            logger.info(f"API call completed for {endpoint_name}", 
                       extra={'endpoint': endpoint_name, 'response_time': response_time, 
                             'status_code': response.status_code})
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"HTTP {response.status_code} for {endpoint_name}",
                              extra={'endpoint': endpoint_name, 'status_code': response.status_code, 
                                    'url': url, 'response_time': response_time})
                return None
                
    except rq.exceptions.ConnectionError as e:
        logger.error(f"Connection error for {endpoint_name}: {e}",
                    extra={'endpoint': endpoint_name, 'url': url, 'error_type': 'connection_error'})
        return None
    except rq.exceptions.Timeout as e:
        logger.error(f"Request timeout for {endpoint_name}: {e}",
                    extra={'endpoint': endpoint_name, 'url': url, 'error_type': 'timeout'})
        return None
    except rq.exceptions.RequestException as e:
        logger.error(f"Request error for {endpoint_name}: {e}",
                    extra={'endpoint': endpoint_name, 'url': url, 'error_type': 'request_error'})
        return None
    except Exception as e:
        logger.error(f"Unexpected error for {endpoint_name}: {e}",
                    extra={'endpoint': endpoint_name, 'url': url, 'error_type': 'unexpected_error'}, exc_info=True)
        return None
```

#### Step 3: Update main() function (Lines 681-714)
**Current function location:** riverlevel.py:681-714

**Required changes:**
1. Add detailed configuration logging with structured extra fields
2. Add debug-level monitoring cycle logging
3. Improve exception handling with proper logging

**Updated main function:**
```python
def main():
    """Main application entry point with comprehensive logging."""
    logger.info("Starting river level monitoring application")
    logger.info(f"Configuration: containerised={os.getenv('CONTAINERISED', 'NO')}")
    
    # Log configuration with structured data
    config_info = {
        'river_measure_api': RIVER_MEASURE_API,
        'river_station_api': RIVER_STATION_API,
        'rain_measure_api': RAIN_MEASURE_API,
        'rain_station_api': RAIN_STATION_API,
        'metrics_port': int(metrics_port) if 'metrics_port' in locals() else 8897
    }
    logger.info("Application configuration loaded", extra=config_info)
    
    startup_start_time = time.time()
    
    # Validate configuration first - fail fast approach
    validate_config_on_startup()
    
    # Start health check server
    health_server = start_health_server()
    
    # Function starts metrics webserver
    try:
        if os.environ['CONTAINERISED'] == 'YES':
            logger.info("Module containerised, using environment values for metrics port.")
            metrics_port = os.environ['METRICS_PORT']
        else:
            logger.info("Module not containerised, using hard coded values for metrics API.")
            metrics_port = 8897
    except KeyError:
        logger.info("Module not containerised, using hard coded values for metrics API.")
        metrics_port = 8897

    try:
        # Application initialization
        logger.info("Initializing Prometheus metrics server")
        start_http_server(int(metrics_port))
        logger.info(f"Serving sensor metrics on :{metrics_port}")
        
        # Record startup metrics
        startup_duration = time.time() - startup_start_time
        startup_time.observe(startup_duration)
        application_start_time.set(time.time())
        
        logger.info(f"Application startup completed in {startup_duration:.2f} seconds", 
                   extra={'startup_phase': 'complete', 'startup_duration': startup_duration})

        # Main monitoring loop with debug logging
        while True:
            try:
                logger.debug("Starting monitoring cycle")
                set_gauges()
                logger.debug("Monitoring cycle completed successfully")
                
            except Exception as e:
                logger.error("Error in monitoring cycle", exc_info=True)
                time.sleep(30)  # Shorter delay on error
                
    except KeyboardInterrupt:
        logger.info("Received shutdown signal, stopping application")
    except Exception as e:
        logger.critical("Fatal error in application", exc_info=True)
        raise
```

#### Step 4: Update set_gauges() function (Lines 642-678)
**Current function location:** riverlevel.py:642-678

**Required changes:**
1. Add debug logging for monitoring cycle steps
2. Remove the `time.sleep()` call (should be in main loop)

**Updated set_gauges function:**
```python
def set_gauges():
    """Function calls API, feeds to get_height and then sets prometheus gauge."""
    logger.debug("Fetching API responses")
    
    # get responses with robust retry logic
    river_measure_response = make_api_call_with_retry(RIVER_MEASURE_API, "river_measure")
    river_station_response = make_api_call_with_retry(RIVER_STATION_API, "river_station")
    rain_measure_response = make_api_call_with_retry(RAIN_MEASURE_API, "rain_measure")

    logger.debug("Processing API responses and updating metrics")
    
    # set river gauge river level to output of get_height function
    if river_measure_response is not None:
        river_height = get_height(river_measure_response)
        if river_height is not None:
            gauge_river_level.set(river_height)
            logger.debug(f"Updated river level metric: {river_height}")
    else:
        logger.warning("Skipping river level update - API data unavailable")

    if river_station_response is not None:
        typical_level = get_typical(river_station_response)
        if typical_level is not None:
            gauge_river_typical_level.set(typical_level)
            logger.debug(f"Updated typical level metric: {typical_level}")
        
        max_record = get_record_max(river_station_response)
        if max_record is not None:
            gauge_river_max_record.set(max_record)
            logger.debug(f"Updated max record metric: {max_record}")
    else:
        logger.warning("Skipping river station metrics update - API data unavailable")

    if rain_measure_response is not None:
        rainfall = get_rainfall(rain_measure_response)
        if rainfall is not None:
            gauge_rainfall.set(rainfall)
            logger.debug(f"Updated rainfall metric: {rainfall}")
    else:
        logger.warning("Skipping rainfall update - API data unavailable")
    
    logger.debug("Metrics update cycle completed")
```

### Implementation Checklist
- [ ] Replace lines 23-58 with new setup_logging() function
- [ ] Update make_api_call_with_retry() to include response time logging
- [ ] Update main() function with structured configuration logging
- [ ] Update set_gauges() with debug logging and remove time.sleep()
- [ ] Test console output shows simple format
- [ ] Test file logging creates riverlevel.log with JSON format
- [ ] Test log rotation works with 10MB files
- [ ] Verify response time is logged for all API calls
- [ ] Verify debug messages appear in file but not console

### Testing the Implementation
1. **Console output test**: Run application and verify console shows human-readable format
2. **File logging test**: Check riverlevel.log is created with JSON entries
3. **Log rotation test**: Generate >10MB logs and verify rotation
4. **Response time test**: Verify API calls log response_time field
5. **Debug logging test**: Verify debug messages appear in file only

### Benefits of This Implementation
1. **Dual output formats**: Human-readable console + structured file logging
2. **Response time tracking**: Monitor API performance
3. **Log rotation**: Prevent disk space issues
4. **Debug logging**: Detailed monitoring cycle information
5. **Structured data**: All log entries contain contextual information
6. **Exception handling**: Comprehensive error logging with stack traces