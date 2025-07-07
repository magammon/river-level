# Phase 1: Error Handling & Reliability Implementation Plan

## Section 8: Add operational health and graceful shutdown

### 8.1 Health check endpoint:
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

### 8.2 Graceful shutdown handling:
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