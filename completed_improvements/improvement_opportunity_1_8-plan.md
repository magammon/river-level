# Phase 1: Error Handling & Reliability Implementation Plan

## Section 8: Add operational health and graceful shutdown

### REVISED IMPLEMENTATION PLAN

**Note: This plan has been updated to build upon existing infrastructure rather than duplicating functionality.**

### Analysis of Current State

The current codebase already includes:
- Health check server running on port 8898 (riverlevel.py:362-430)
- Comprehensive API monitoring with `api_last_success_time` metrics
- Structured logging system with JSON output
- Station initialization status tracking

### 8.1 Enhanced Health Check Endpoint

**Current Implementation (riverlevel.py:365-413)**
```python
def do_GET(self):
    """Handle GET requests for health checks."""
    if self.path == '/health':
        # Check if at least one API is working
        if (initialise_river_gauge_station_response is not None or 
            initialise_rain_gauge_station_response is not None):
            
            # Prepare detailed health status
            health_status = {
                'status': 'healthy',
                'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'apis': {
                    'river_station': initialise_river_gauge_station_response is not None,
                    'rain_station': initialise_rain_gauge_station_response is not None
                }
            }
            
            # Check if degraded
            if (initialise_river_gauge_station_response is None or 
                initialise_rain_gauge_station_response is None):
                health_status['status'] = 'degraded'
                health_status['message'] = 'Some APIs unavailable but service functional'
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(health_status).encode('utf-8'))
        else:
            # No APIs available
            error_status = {
                'status': 'unhealthy',
                'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'reason': 'No APIs available',
                'apis': {
                    'river_station': False,
                    'rain_station': False
                }
            }
            
            self.send_response(503)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(error_status).encode('utf-8'))
    else:
        # Not found
        self.send_response(404)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"error": "Not found"}')
```

**Enhanced Implementation**
Replace the entire `do_GET` method (lines 365-413) with:

```python
def do_GET(self):
    """Enhanced health check with detailed API and metrics status."""
    if self.path == '/health':
        # Base health status structure
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'apis': {
                'river_station': initialise_river_gauge_station_response is not None,
                'rain_station': initialise_rain_gauge_station_response is not None
            },
            'initialization': {
                'river_station_initialized': initialise_river_gauge_station_response is not None,
                'rain_station_initialized': initialise_rain_gauge_station_response is not None
            }
        }
        
        # Add metrics if available (with error handling)
        try:
            metrics_data = {}
            # Safely access Prometheus metrics
            if hasattr(api_last_success_time, 'labels'):
                try:
                    metrics_data['last_successful_river_update'] = api_last_success_time.labels(endpoint='river_measure')._value._value
                except (AttributeError, TypeError):
                    metrics_data['last_successful_river_update'] = 0
                
                try:
                    metrics_data['last_successful_rain_update'] = api_last_success_time.labels(endpoint='rain_measure')._value._value
                except (AttributeError, TypeError):
                    metrics_data['last_successful_rain_update'] = 0
                
                try:
                    metrics_data['last_successful_river_station_update'] = api_last_success_time.labels(endpoint='river_station')._value._value
                except (AttributeError, TypeError):
                    metrics_data['last_successful_river_station_update'] = 0
                
                try:
                    metrics_data['last_successful_rain_station_update'] = api_last_success_time.labels(endpoint='rain_station')._value._value
                except (AttributeError, TypeError):
                    metrics_data['last_successful_rain_station_update'] = 0
            
            health_status['metrics'] = metrics_data
        except Exception as e:
            # If metrics access fails, continue without metrics
            health_status['metrics'] = {'error': 'metrics_unavailable'}
        
        # Determine overall health based on API availability
        if (initialise_river_gauge_station_response is None and 
            initialise_rain_gauge_station_response is None):
            health_status['status'] = 'unhealthy'
            health_status['message'] = 'All APIs unavailable'
            self.send_response(503)
        elif (initialise_river_gauge_station_response is None or 
              initialise_rain_gauge_station_response is None):
            health_status['status'] = 'degraded'
            health_status['message'] = 'Some APIs unavailable but service functional'
            self.send_response(200)
        else:
            health_status['status'] = 'healthy'
            health_status['message'] = 'All systems operational'
            self.send_response(200)
            
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(health_status).encode('utf-8'))
    else:
        self.send_response(404)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"error": "Not found"}')
```

### 8.2 Graceful Shutdown Handling

**Step 1: Add signal import**
The `signal` import is already present at line 8 (via `sys`), but we need to add the explicit import.

**At line 8, change:**
```python
import sys
```

**To:**
```python
import sys
import signal
```

**Step 2: Add signal handler function**
Add this function after the existing logging setup and before the configuration constants (around line 95):

```python
def setup_signal_handlers():
    """Setup graceful shutdown handlers."""
    def signal_handler(signum, frame):
        logger.info(f"Received shutdown signal {signum}")
        logger.info("Initiating graceful shutdown...")
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    logger.info("Signal handlers registered for graceful shutdown")
```

**Step 3: Modify main function**
In the `main()` function, **add this line after line 741** (after `validate_config_on_startup()`):

```python
# Setup signal handlers for graceful shutdown
setup_signal_handlers()
```

**Step 4: Update exception handling**
Replace the existing try/except block starting at line 773 with:

```python
try:
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
    logger.info("Received keyboard interrupt, stopping application")
except SystemExit:
    logger.info("Received system exit signal, stopping application")
except Exception as e:
    logger.critical("Fatal error in application", exc_info=True)
    raise
finally:
    logger.info("Application shutdown complete")
```

### 8.3 Docker Health Check Integration

**File: Dockerfile**
Add this line after line 3 (after `EXPOSE 8897`):

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD /env/bin/python3 -c "import requests; requests.get('http://localhost:8898/health').raise_for_status()" || exit 1
```

**Note:** The `requests` library is already installed via requirements.txt, so no additional dependencies are needed.

### 8.4 Implementation Steps

**Step-by-Step Implementation:**

1. **Backup current file:**
   ```bash
   cp riverlevel.py riverlevel.py.backup
   ```

2. **Add signal import (Line 8):**
   - Change `import sys` to `import sys` and add `import signal` on the next line

3. **Add signal handler function (After line 95):**
   - Insert the `setup_signal_handlers()` function

4. **Modify main function (Line 741):**
   - Add `setup_signal_handlers()` call after `validate_config_on_startup()`

5. **Update exception handling (Line 773):**
   - Replace the existing try/except block with the enhanced version

6. **Replace health check method (Lines 365-413):**
   - Replace the entire `do_GET` method in the `HealthHandler` class

7. **Update Dockerfile (After line 3):**
   - Add the HEALTHCHECK directive

8. **Test the implementation:**
   - Run the application locally
   - Test health endpoint: `curl http://localhost:8898/health`
   - Test graceful shutdown: `kill -TERM <pid>`

### 8.5 Testing Commands

**Local Testing:**
```bash
# Start application
python riverlevel.py

# Test health check (should return 200)
curl -i http://localhost:8898/health

# Test graceful shutdown (in another terminal)
kill -TERM $(pgrep -f riverlevel.py)

# Verify logs show graceful shutdown message
tail -f riverlevel.log
```

**Docker Testing:**
```bash
# Build image
docker build -t riverlevel .

# Run container
docker run -d --name riverlevel-test -p 8897:8897 -p 8898:8898 \
  -e RIVER_MEASURE_API=https://example.com/river.json \
  -e RIVER_STATION_API=https://example.com/river-station.json \
  -e RAIN_MEASURE_API=https://example.com/rain.json \
  -e RAIN_STATION_API=https://example.com/rain-station.json \
  -e METRICS_PORT=8897 \
  riverlevel

# Test health check
curl -i http://localhost:8898/health

# Test Docker health check
docker inspect riverlevel-test | grep -A 10 -B 10 Health

# Test graceful shutdown
docker kill -s TERM riverlevel-test

# Check logs
docker logs riverlevel-test
```

**API Failure Simulation:**
```bash
# To test degraded mode, use invalid URLs for some APIs
docker run -d --name riverlevel-degraded -p 8897:8897 -p 8898:8898 \
  -e RIVER_MEASURE_API=https://invalid-url.com/river.json \
  -e RIVER_STATION_API=https://invalid-url.com/river-station.json \
  -e RAIN_MEASURE_API=https://environment.data.gov.uk/flood-monitoring/id/measures/53107-rainfall-tipping_bucket_raingauge-t-15_min-mm.json \
  -e RAIN_STATION_API=https://environment.data.gov.uk/flood-monitoring/id/stations/53107.json \
  -e METRICS_PORT=8897 \
  riverlevel

# Health check should return 'degraded' status
curl -i http://localhost:8898/health
```

### 8.6 Rollback Plan

**If issues occur during implementation:**

1. **Restore backup:**
   ```bash
   cp riverlevel.py.backup riverlevel.py
   ```

2. **Revert Docker changes:**
   ```bash
   git checkout Dockerfile
   ```

3. **Test original functionality:**
   ```bash
   python riverlevel.py
   curl http://localhost:8898/health
   ```

### 8.7 Troubleshooting

**Common Issues:**

1. **Health check returns 500 error:**
   - Check logs for Python traceback
   - Verify all variables (`initialise_river_gauge_station_response`, etc.) are accessible
   - Ensure `datetime` and `json` imports are available

2. **Metrics not appearing in health check:**
   - This is expected if `api_last_success_time` hasn't been populated yet
   - Check that the application has run at least one monitoring cycle

3. **Signal handler not working:**
   - Verify signal import is correct
   - Check that `setup_signal_handlers()` is called in main()
   - Test with `kill -TERM <pid>` instead of `kill -9`

4. **Docker health check failing:**
   - Ensure port 8898 is exposed and accessible
   - Check that the application has fully started (use `--start-period=5s`)
   - Verify `requests` library is installed in container

**Expected Behavior:**
- Health endpoint returns JSON with status, timestamp, and API availability
- Graceful shutdown logs appear when SIGTERM/SIGINT received
- Docker health check passes when at least one API is available
- Application continues to function even if some APIs are unavailable

This implementation maintains the existing robust architecture while adding operational health monitoring and graceful shutdown capabilities needed for production deployment.