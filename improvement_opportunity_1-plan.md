# Phase 1: Error Handling & Reliability Implementation Plan

## Current Issues Identified:
1. **Functions crash on API errors**: `get_height()` (line 44-47), `get_rainfall()` (line 69-72), and other parsing functions will raise exceptions if API responses are missing expected fields
2. **No retry logic**: API calls in `set_gauges()` (lines 77-79) and initialization (lines 110-111) have no retry mechanism
3. **Application crashes on failures**: Missing readings cause the entire application to crash instead of graceful degradation
4. **No input validation**: No validation of API responses or environment variables

## Proposed Implementation:

### 1. Add robust error handling to all API parsing functions

#### 1.1 Function-by-function error handling implementation:

**`get_height(obj)` (lines 44-47):**
- Current: `json.dumps(obj['items']['latestReading']['value'])` - crashes if any key missing
- New: Try/except with KeyError, TypeError, ValueError handling
- Fallback: Return `None` when data unavailable (don't mislead with 0.0)
- Fix: Remove unnecessary `json.dumps()` - value is already parsed
- Log: "Unable to parse river height from API response"

**`get_rainfall(obj)` (lines 69-72):**
- Current: `json.dumps(obj['items']['latestReading']['value'])` - crashes if any key missing
- New: Try/except with KeyError, TypeError, ValueError handling  
- Fallback: Return `None` when data unavailable (don't mislead with 0.0)
- Fix: Remove unnecessary `json.dumps()` - value is already parsed
- Log: "Unable to parse rainfall from API response"

**`get_station_name(obj)` (lines 39-42):**
- Current: `json.dumps(obj['items']['label'])` - crashes if keys missing
- New: Try/except with KeyError, TypeError handling
- Fallback: Return `"Unknown Station"` (string) when data unavailable
- Fix: Remove unnecessary `json.dumps()` - value is already parsed
- Log: "Unable to parse station name from API response"

**`get_typical(obj)` (lines 49-52):**
- Current: `json.dumps(obj['items']['stageScale']['typicalRangeHigh'])` - crashes if nested keys missing
- New: Try/except with KeyError, TypeError, ValueError handling
- Fallback: Return `None` when data unavailable (don't mislead with 0.0)
- Fix: Remove unnecessary `json.dumps()` - value is already parsed
- Log: "Unable to parse typical range from API response"

**`get_record_max(obj)` (lines 54-57):**
- Current: `json.dumps(obj['items']['stageScale']['maxOnRecord']['value'])` - crashes if nested keys missing
- New: Try/except with KeyError, TypeError, ValueError handling
- Fallback: Return `None` when data unavailable (don't mislead with 0.0)
- Fix: Remove unnecessary `json.dumps()` - value is already parsed
- Log: "Unable to parse record max from API response"

**`get_station_grid_ref(obj)` (lines 59-62):**
- Current: `json.dumps(obj['items']['gridReference'])` - crashes if keys missing
- New: Try/except with KeyError, TypeError handling
- Fallback: Return `"UNKNOWN"` (string) when data unavailable
- Fix: Remove unnecessary `json.dumps()` - value is already parsed
- Log: "Unable to parse grid reference from API response"

**`get_station_id(obj)` (lines 64-67):**
- Current: `json.dumps(obj['items']['stationReference'])` - crashes if keys missing
- New: Try/except with KeyError, TypeError handling
- Fallback: Return `"UNKNOWN"` (string) when data unavailable
- Fix: Remove unnecessary `json.dumps()` - value is already parsed
- Log: "Unable to parse station ID from API response"

#### 1.2 Improved error handling pattern:
```python
def get_height(obj):
    """Function takes api output from EA API and returns river level as float or None."""
    if obj is None:
        return None
    try:
        return float(obj['items']['latestReading']['value'])
    except (KeyError, TypeError, ValueError) as e:
        logger.warning(f"Unable to parse river height from API response: {e}")
        return None  # Return None instead of 0.0 to avoid misleading metrics
```

#### 1.3 Exception types to handle:
- **KeyError**: When expected JSON keys are missing
- **TypeError**: When obj is None or wrong type
- **ValueError**: When conversion to float fails
- **requests.exceptions.ConnectionError**: Network connection failures
- **requests.exceptions.Timeout**: Request timeout errors
- **requests.exceptions.RequestException**: General request errors

#### 1.4 Improved fallback strategy - return None instead of misleading values:
- **Numeric values**: Return `None` instead of `0.0` to avoid misleading metrics
- **String values**: Return `None` for missing data, handle gracefully in calling code
- **Maintains type consistency**: Functions return expected types or None
- **Prevents misleading metrics**: Don't update Prometheus gauges with fake zero values

#### 1.5 Testing approach for step 1:
- Test each function with `None` input
- Test with empty dictionary `{}`
- Test with partial data (missing nested keys)
- Test with wrong data types (strings where numbers expected)
- Verify fallback values are returned and logged appropriately

### 2. Implement robust retry logic with proven libraries

#### 2.1 Use established retry libraries instead of custom implementation:
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create session with retry strategy
def create_robust_session():
    """Create requests session with retry strategy and error handling."""
    session = requests.Session()
    
    # Configure retry strategy using proven urllib3 implementation
    retry_strategy = Retry(
        total=5,                    # Maximum number of retries
        backoff_factor=1,           # Exponential backoff factor
        status_forcelist=[429, 500, 502, 503, 504],  # HTTP codes to retry
        method_whitelist=["GET"],   # Only retry GET requests
        raise_on_status=False       # Don't raise exceptions on HTTP errors
    )
    
    # Apply retry strategy to both HTTP and HTTPS
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

# Global session for reuse
api_session = create_robust_session()

def make_api_call_with_retry(url, endpoint_name="unknown"):
    """Make API call with retry logic and comprehensive error handling.
    
    Args:
        url: API endpoint URL
        endpoint_name: Name for logging and metrics (e.g., "river_measure", "rain_station")
    
    Returns:
        dict: Parsed JSON response or None if all retries failed
    """
    try:
        with api_call_context(endpoint_name):
            response = api_session.get(url, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"HTTP {response.status_code} for {endpoint_name}: {url}")
                api_error_counter.labels(endpoint=endpoint_name, error=f"http_{response.status_code}").inc()
                return None
                
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error for {endpoint_name}: {e}")
        api_error_counter.labels(endpoint=endpoint_name, error="connection_error").inc()
        return None
    except requests.exceptions.Timeout as e:
        logger.error(f"Request timeout for {endpoint_name}: {e}")
        api_error_counter.labels(endpoint=endpoint_name, error="timeout").inc()
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error for {endpoint_name}: {e}")
        api_error_counter.labels(endpoint=endpoint_name, error="request_error").inc()
        return None
    except Exception as e:
        logger.error(f"Unexpected error for {endpoint_name}: {e}")
        api_error_counter.labels(endpoint=endpoint_name, error="unexpected_error").inc()
        return None
```

#### 2.2 Add Prometheus metrics for API monitoring:
```python
from prometheus_client import Counter, Histogram, Gauge
from contextlib import contextmanager
import time

# Define API monitoring metrics
api_error_counter = Counter('api_request_failures_total', 
                           'Total API request failures', 
                           ['endpoint', 'error'])
api_request_duration = Histogram('api_request_duration_seconds', 
                                'API request duration in seconds', 
                                ['endpoint'])
api_success_counter = Counter('api_request_success_total',
                             'Total successful API requests',
                             ['endpoint'])
api_last_success_time = Gauge('api_last_success_timestamp',
                             'Timestamp of last successful API call',
                             ['endpoint'])

@contextmanager
def api_call_context(endpoint_name):
    """Context manager for API call monitoring."""
    start_time = time.time()
    try:
        yield
        api_success_counter.labels(endpoint=endpoint_name).inc()
        api_last_success_time.labels(endpoint=endpoint_name).set(time.time())
    except Exception as e:
        api_error_counter.labels(endpoint=endpoint_name, error=type(e).__name__).inc()
        raise
    finally:
        api_request_duration.labels(endpoint=endpoint_name).observe(time.time() - start_time)
```

#### 2.3 Apply to all API calls:

**2.3.1 Update `set_gauges()` function (lines 77-79):**
```python
# Current vulnerable code:
river_gauge_response = rq.get(RIVER_MEASURE_API, timeout=30)
rain_gauge_response = rq.get(RAIN_MEASURE_API, timeout=30)

# New robust code with proper endpoint naming:
river_gauge_response = make_api_call_with_retry(RIVER_MEASURE_API, "river_measure")
rain_gauge_response = make_api_call_with_retry(RAIN_MEASURE_API, "rain_measure")

# Skip metric updates instead of using misleading fallback values:
if river_gauge_response is not None:
    river_height = get_height(river_gauge_response)
    if river_height is not None:
        river_level_gauge.set(river_height)
    # Don't set gauge to 0.0 if data unavailable - preserve last known value
else:
    logger.warning("Skipping river level update - API data unavailable")

if rain_gauge_response is not None:
    rainfall = get_rainfall(rain_gauge_response)
    if rainfall is not None:
        rain_level_gauge.set(rainfall)
    # Don't set gauge to 0.0 if data unavailable - preserve last known value
else:
    logger.warning("Skipping rainfall update - API data unavailable")
```

**2.2.2 Update initialization API calls (lines 110-111):**
```python
# Current vulnerable code:
initialise_river_gauge_station_response = rq.get(RIVER_STATION_API, timeout=30)
initialise_rain_gauge_station_response = rq.get(RAIN_STATION_API, timeout=30)

# New robust code:
initialise_river_gauge_station_response = make_api_call_with_retry(RIVER_STATION_API)
initialise_rain_gauge_station_response = make_api_call_with_retry(RAIN_STATION_API)

# Add validation and fallback labels:
if initialise_river_gauge_station_response is None:
    print("Failed to fetch river station info - using default labels")
    river_station_label = "Unknown River Station"
    river_station_id = "UNKNOWN"
else:
    river_station_label = get_station_name(initialise_river_gauge_station_response)
    river_station_id = get_station_id(initialise_river_gauge_station_response)

if initialise_rain_gauge_station_response is None:
    print("Failed to fetch rain station info - using default labels")
    rain_station_label = "Unknown Rain Station"
    rain_station_id = "UNKNOWN"
else:
    rain_station_label = get_station_name(initialise_rain_gauge_station_response)
    rain_station_id = get_station_id(initialise_rain_gauge_station_response)
```

#### 2.3 Retry strategy rationale:

**2.3.1 Exponential backoff benefits:**
- **Prevents thundering herd**: Multiple clients don't retry simultaneously
- **Reduces API load**: Gives servers time to recover from high load
- **Increases success probability**: Temporary issues often resolve within minutes
- **Respects rate limits**: Longer delays help avoid triggering rate limiting

**2.3.2 Jitter implementation:**
- **Prevents retry synchronization**: Random component prevents all clients retrying at exact same time
- **Reduces server load spikes**: Spreads retry attempts across time
- **Industry best practice**: Recommended by AWS, Google, and other cloud providers

**2.3.3 HTTP status code handling:**
- **200**: Success - return data immediately
- **429**: Rate limited - always retry with backoff
- **5xx**: Server errors - retry as these are often temporary
- **4xx**: Client errors - don't retry (except 429) as these indicate configuration issues

#### 2.4 Configuration considerations:

**2.4.1 Retry parameters:**
- **max_retries=5**: Balances reliability vs. responsiveness (total ~2 minutes max)
- **base_delay=1**: Quick first retry for transient network issues
- **max_delay=60**: Prevents excessively long delays
- **timeout=30**: Existing timeout preserved for individual requests

**2.4.2 Total retry time calculation:**
With exponential backoff (1, 2, 4, 8, 16 seconds) plus jitter:
- **Minimum total time**: ~31 seconds (if all attempts fail quickly)
- **Maximum total time**: ~121 seconds (with full delays and 30s timeouts)
- **Typical failure time**: ~60-90 seconds (most realistic scenario)

#### 2.5 Environment Agency API considerations:

**2.5.1 API reliability patterns:**
- **Peak usage**: Higher failure rates during flood events when most needed
- **Rate limiting**: Unknown limits but retry logic helps avoid issues
- **Server maintenance**: Periodic maintenance windows require retry logic
- **Load balancing**: Multiple servers may have different availability

**2.5.2 Monitoring integration:**
- **Log all retry attempts**: Track API reliability patterns
- **Count failed requests**: Monitor for systematic issues
- **Track response times**: Identify performance degradation

#### 2.6 Testing approach for retry logic:

**2.6.1 Network condition simulation:**
- Test with unreachable endpoints (DNS failures)
- Test with connection timeouts
- Test with HTTP 500/502/503 errors
- Test with HTTP 429 rate limiting
- Test with intermittent connectivity

**2.6.2 Timing verification:**
- Verify exponential backoff delays
- Confirm jitter randomization
- Test maximum retry limits
- Verify graceful degradation when all retries fail

**2.6.3 Edge case handling:**
- Test with malformed JSON in successful responses
- Test with empty responses (HTTP 200 but no content)
- Test with very large response payloads
- Test with unexpected HTTP status codes

### 3. Add input validation
- Validate environment variables on startup
- Validate API response structure before parsing
- Add configuration validation logging

### 4. Add initialization error handling

#### 4.1 Critical issue:
The initialization code (lines 110-111) can crash the entire application if station APIs are unavailable:
```python
# Current vulnerable code:
initialise_river_gauge_station_response = rq.get(RIVER_STATION_API, timeout=30)
initialise_rain_gauge_station_response = rq.get(RAIN_STATION_API, timeout=30)
```

#### 4.2 Proposed solution:
- Use `make_api_call_with_retry()` for initialization API calls
- Provide fallback values for gauge labels if APIs fail
- Allow application to start even with missing station metadata

### 5. Graceful degradation
- Continue operation when individual metrics fail
- Skip metric updates on failures instead of crashing
- Maintain application uptime even with API issues
- Handle missing data in `set_gauges()` function

### 6. Implement comprehensive structured logging

#### 6.1 Configure logging with proper handlers and formatters:
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
    
    # Console handler with simple format
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
                
            return json.dumps(log_entry)
    
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)
    
    return logger

# Initialize logging at startup
logger = setup_logging()
```

#### 6.2 Enhanced logging throughout the application:
```python
def make_api_call_with_retry(url, endpoint_name="unknown"):
    """Make API call with comprehensive logging."""
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
                                    'url': url})
                return None
                
    except Exception as e:
        logger.error(f"API call failed for {endpoint_name}: {e}",
                    extra={'endpoint': endpoint_name, 'url': url}, exc_info=True)
        return None
```

#### 6.3 Application lifecycle logging:
```python
def main():
    """Main application entry point with comprehensive logging."""
    logger.info("Starting river level monitoring application")
    logger.info(f"Configuration: containerised={os.getenv('CONTAINERISED', 'NO')}")
    
    # Log configuration
    config_info = {
        'river_measure_api': RIVER_MEASURE_API,
        'river_station_api': RIVER_STATION_API,
        'rain_measure_api': RAIN_MEASURE_API,
        'rain_station_api': RAIN_STATION_API,
        'metrics_port': METRICS_PORT
    }
    logger.info("Application configuration loaded", extra=config_info)
    
    try:
        # Application initialization
        logger.info("Initializing Prometheus metrics server")
        start_http_server(METRICS_PORT)
        
        # Main monitoring loop
        while True:
            try:
                logger.debug("Starting monitoring cycle")
                set_gauges()
                logger.debug("Monitoring cycle completed successfully")
                time.sleep(60)
                
            except Exception as e:
                logger.error("Error in monitoring cycle", exc_info=True)
                time.sleep(30)  # Shorter delay on error
                
    except KeyboardInterrupt:
        logger.info("Received shutdown signal, stopping application")
    except Exception as e:
        logger.critical("Fatal error in application", exc_info=True)
        raise
```

### 7. Add circuit breaker pattern for cascading failure protection

#### 7.1 Implement circuit breaker to prevent cascading failures:
```python
import time
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open" # Testing if service recovered

class CircuitBreaker:
    """Circuit breaker pattern implementation for API calls."""
    
    def __init__(self, failure_threshold=5, recovery_timeout=60, expected_exception=Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker entering HALF_OPEN state")
            else:
                logger.warning(f"Circuit breaker OPEN - rejecting call")
                return None
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self):
        """Check if enough time has passed to attempt reset."""
        return (time.time() - self.last_failure_time) >= self.recovery_timeout
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            logger.info(f"Circuit breaker reset to CLOSED state")
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker OPEN - {self.failure_count} failures exceeded threshold")

# Create circuit breakers for each API endpoint
river_measure_cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
rain_measure_cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
river_station_cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
rain_station_cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
```

#### 7.2 Apply circuit breaker to API calls:
```python
def make_api_call_with_circuit_breaker(url, endpoint_name, circuit_breaker):
    """Make API call protected by circuit breaker."""
    def _api_call():
        return make_api_call_with_retry(url, endpoint_name)
    
    try:
        return circuit_breaker.call(_api_call)
    except Exception as e:
        logger.error(f"Circuit breaker protected call failed for {endpoint_name}: {e}")
        return None

# Usage in set_gauges():
def set_gauges():
    """Update gauge metrics with circuit breaker protection."""
    # Protected API calls
    river_gauge_response = make_api_call_with_circuit_breaker(
        RIVER_MEASURE_API, "river_measure", river_measure_cb
    )
    rain_gauge_response = make_api_call_with_circuit_breaker(
        RAIN_MEASURE_API, "rain_measure", rain_measure_cb
    )
    
    # Process responses only if available
    if river_gauge_response is not None:
        river_height = get_height(river_gauge_response)
        if river_height is not None:
            river_level_gauge.set(river_height)
    
    if rain_gauge_response is not None:
        rainfall = get_rainfall(rain_gauge_response)
        if rainfall is not None:
            rain_level_gauge.set(rainfall)
```

### 8. Add operational health and graceful shutdown

#### 8.1 Health check endpoint:
```python
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import json

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            health_status = {
                'status': 'healthy',
                'timestamp': time.time(),
                'circuit_breakers': {
                    'river_measure': river_measure_cb.state.value,
                    'rain_measure': rain_measure_cb.state.value,
                    'river_station': river_station_cb.state.value,
                    'rain_station': rain_station_cb.state.value
                },
                'last_successful_update': {
                    'river_measure': api_last_success_time.labels(endpoint='river_measure')._value._value,
                    'rain_measure': api_last_success_time.labels(endpoint='rain_measure')._value._value
                }
            }
            
            # Determine overall health
            if any(cb.state == CircuitState.OPEN for cb in [river_measure_cb, rain_measure_cb]):
                health_status['status'] = 'degraded'
                self.send_response(503)
            else:
                self.send_response(200)
                
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(health_status).encode())
        else:
            self.send_response(404)
            self.end_headers()

def start_health_server(port=8898):
    """Start health check server in separate thread."""
    server = HTTPServer(('', port), HealthCheckHandler)
    health_thread = threading.Thread(target=server.serve_forever, daemon=True)
    health_thread.start()
    logger.info(f"Health check server started on port {port}")
    return server
```

#### 8.2 Graceful shutdown handling:
```python
import signal
import sys

class GracefulShutdown:
    def __init__(self):
        self.shutdown_requested = False
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        logger.info(f"Received shutdown signal {signum}")
        self.shutdown_requested = True
        
    def should_shutdown(self):
        return self.shutdown_requested

# Usage in main loop:
def main():
    shutdown_handler = GracefulShutdown()
    health_server = start_health_server()
    
    try:
        while not shutdown_handler.should_shutdown():
            try:
                set_gauges()
                time.sleep(60)
            except Exception as e:
                logger.error("Error in monitoring cycle", exc_info=True)
                time.sleep(30)
                
    except Exception as e:
        logger.critical("Fatal error in application", exc_info=True)
        raise
    finally:
        logger.info("Shutting down gracefully")
        health_server.shutdown()
```

### 9. Additional improvements identified

#### 9.1 Inefficient JSON handling:
- Current code uses `json.dumps()` on already-parsed JSON objects
- Remove unnecessary `json.dumps()` calls and `.replace('"','')` operations
- Direct access to values is more efficient and cleaner

#### 9.2 Missing rain station API error handling:
- Plan should include error handling for rain station API calls in `set_gauges()`
- Rain measurement parsing needs same error handling as river measurements

## Files to modify:
- `riverlevel.py` - Main implementation
- No new files needed - all changes are enhancements to existing code

## Testing approach:
- Test with invalid API endpoints to verify graceful failure
- Test with malformed JSON responses
- Test retry logic with network timeouts
- Test initialization with unavailable station APIs
- Test HTTP error codes (404, 500, etc.)
- Test network connectivity issues
- Verify application continues running when individual metrics fail