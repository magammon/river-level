# Phase 1: Error Handling & Reliability Implementation Plan

## Section 7: Add circuit breaker pattern for cascading failure protection

### 7.1 Implement circuit breaker to prevent cascading failures:
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

### 7.2 Apply circuit breaker to API calls:
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