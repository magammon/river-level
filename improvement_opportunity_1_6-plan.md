# Phase 1: Error Handling & Reliability Implementation Plan

## Section 6: Implement comprehensive structured logging

### 6.1 Configure logging with proper handlers and formatters:
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

### 6.2 Enhanced logging throughout the application:
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

### 6.3 Application lifecycle logging:
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