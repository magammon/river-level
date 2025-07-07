# Phase 1: Error Handling & Reliability Implementation Plan

## Section 2: Implement robust retry logic with proven libraries

### 2.1 Use established retry libraries instead of custom implementation:
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

### 2.2 Add Prometheus metrics for API monitoring:
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

### 2.3 Apply to all API calls:

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

### 2.4 Retry strategy rationale:

**2.4.1 Exponential backoff benefits:**
- **Prevents thundering herd**: Multiple clients don't retry simultaneously
- **Reduces API load**: Gives servers time to recover from high load
- **Increases success probability**: Temporary issues often resolve within minutes
- **Respects rate limits**: Longer delays help avoid triggering rate limiting

**2.4.2 Jitter implementation:**
- **Prevents retry synchronization**: Random component prevents all clients retrying at exact same time
- **Reduces server load spikes**: Spreads retry attempts across time
- **Industry best practice**: Recommended by AWS, Google, and other cloud providers

**2.4.3 HTTP status code handling:**
- **200**: Success - return data immediately
- **429**: Rate limited - always retry with backoff
- **5xx**: Server errors - retry as these are often temporary
- **4xx**: Client errors - don't retry (except 429) as these indicate configuration issues

### 2.5 Configuration considerations:

**2.5.1 Retry parameters:**
- **max_retries=5**: Balances reliability vs. responsiveness (total ~2 minutes max)
- **base_delay=1**: Quick first retry for transient network issues
- **max_delay=60**: Prevents excessively long delays
- **timeout=30**: Existing timeout preserved for individual requests

**2.5.2 Total retry time calculation:**
With exponential backoff (1, 2, 4, 8, 16 seconds) plus jitter:
- **Minimum total time**: ~31 seconds (if all attempts fail quickly)
- **Maximum total time**: ~121 seconds (with full delays and 30s timeouts)
- **Typical failure time**: ~60-90 seconds (most realistic scenario)

### 2.6 Environment Agency API considerations:

**2.6.1 API reliability patterns:**
- **Peak usage**: Higher failure rates during flood events when most needed
- **Rate limiting**: Unknown limits but retry logic helps avoid issues
- **Server maintenance**: Periodic maintenance windows require retry logic
- **Load balancing**: Multiple servers may have different availability

**2.6.2 Monitoring integration:**
- **Log all retry attempts**: Track API reliability patterns
- **Count failed requests**: Monitor for systematic issues
- **Track response times**: Identify performance degradation

### 2.7 Testing approach for retry logic:

**2.7.1 Network condition simulation:**
- Test with unreachable endpoints (DNS failures)
- Test with connection timeouts
- Test with HTTP 500/502/503 errors
- Test with HTTP 429 rate limiting
- Test with intermittent connectivity

**2.7.2 Timing verification:**
- Verify exponential backoff delays
- Confirm jitter randomization
- Test maximum retry limits
- Verify graceful degradation when all retries fail

**2.7.3 Edge case handling:**
- Test with malformed JSON in successful responses
- Test with empty responses (HTTP 200 but no content)
- Test with very large response payloads
- Test with unexpected HTTP status codes