"""
This module takes environment agency water level and rainfall measure and station data 
from their API and converts to prometheus metrics published through a webserver.
"""
import os
import json
import time
import sys
import threading
from datetime import datetime, timezone
#import platform
import requests as rq
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
import re
from urllib.parse import urlparse
from http.server import BaseHTTPRequestHandler, HTTPServer
# Import Gauge and start_http_server from prometheus_client
from prometheus_client import Gauge, start_http_server, Counter, Histogram
from contextlib import contextmanager

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

# set read units. 1 = seconds, 60 = minutes, 3600 = hours, 86400 = days
READ_UNITS = 60

# set read interval of how many multiples of the read units between scrapes of the API
READ_INTERVAL = 1

# Configuration schema constants for maintainability
CONFIG_SCHEMA = {
    'required_env_vars': ['RIVER_MEASURE_API', 'RIVER_STATION_API', 
                          'RAIN_MEASURE_API', 'RAIN_STATION_API', 'METRICS_PORT'],
    'port_range': (1, 65535),
    'url_schemes': ['http', 'https'],
    'api_timeout': 30,  # seconds
    'max_response_size': 1024 * 1024  # 1MB
}

# Input validation functions
def validate_url_format(url):
    """Validate URL format and structure."""
    try:
        parsed = urlparse(url)
        # Check basic URL structure
        if not all([parsed.scheme, parsed.netloc]):
            return False
        # Ensure valid HTTP schemes
        if parsed.scheme not in CONFIG_SCHEMA['url_schemes']:
            return False
        # Prefer HTTPS for external APIs (security best practice)
        if parsed.scheme == 'http' and not parsed.netloc.startswith('localhost'):
            logger.warning(f"Using HTTP instead of HTTPS for external API: {parsed.netloc}")
        # Allow any domain but validate structure
        return True
    except Exception:
        return False

def validate_required_vars():
    """Validate presence of required environment variables."""
    required_vars = {
        'RIVER_MEASURE_API': 'River measurement API endpoint',
        'RIVER_STATION_API': 'River station API endpoint', 
        'RAIN_MEASURE_API': 'Rain measurement API endpoint',
        'RAIN_STATION_API': 'Rain station API endpoint',
        'METRICS_PORT': 'Prometheus metrics port'
    }
    
    missing_vars = []
    for var_name, description in required_vars.items():
        if not os.getenv(var_name):
            missing_vars.append(f"Missing {var_name} environment variable. Set it to your {description.lower()}.")
    
    return len(missing_vars) == 0, missing_vars

def validate_api_urls(vars_dict):
    """Validate API URL formats."""
    url_errors = []
    for var_name, value in vars_dict.items():
        if var_name.endswith('_API') and value:
            if not validate_url_format(value):
                url_errors.append(f"Invalid URL format for {var_name}: {value}")
    
    return len(url_errors) == 0, url_errors

def validate_metrics_port(port_str):
    """Validate metrics port configuration."""
    try:
        port = int(port_str)
        if not (CONFIG_SCHEMA['port_range'][0] <= port <= CONFIG_SCHEMA['port_range'][1]):
            return False, f"Port {port} out of valid range ({CONFIG_SCHEMA['port_range'][0]}-{CONFIG_SCHEMA['port_range'][1]})"
        return True, f"Port {port} is valid"
    except ValueError:
        return False, f"Port value '{port_str}' is not a valid integer"

def validate_environment_config():
    """Validate environment variables when containerised."""
    if os.getenv('CONTAINERISED') != 'YES':
        return True, []
    
    logger.info("Validating containerised environment configuration")
    
    # Validate required variables exist
    vars_valid, var_errors = validate_required_vars()
    if not vars_valid:
        return False, var_errors
    
    # Get environment variables for further validation
    env_vars = {
        'RIVER_MEASURE_API': os.getenv('RIVER_MEASURE_API'),
        'RIVER_STATION_API': os.getenv('RIVER_STATION_API'),
        'RAIN_MEASURE_API': os.getenv('RAIN_MEASURE_API'),
        'RAIN_STATION_API': os.getenv('RAIN_STATION_API'),
        'METRICS_PORT': os.getenv('METRICS_PORT')
    }
    
    # Validate URL formats
    urls_valid, url_errors = validate_api_urls(env_vars)
    
    # Validate port
    port_valid, port_msg = validate_metrics_port(env_vars['METRICS_PORT'])
    
    # Collect all validation results
    all_errors = []
    if not urls_valid:
        all_errors.extend(url_errors)
    if not port_valid:
        all_errors.append(port_msg)
    
    config_valid = vars_valid and urls_valid and port_valid
    
    # Log validation results
    if config_valid:
        logger.info("✓ Environment configuration validation passed")
        for var_name, value in env_vars.items():
            if var_name.endswith('_API'):
                logger.info(f"✓ {var_name}: {value}")
            else:
                logger.info(f"✓ {var_name}: {value}")
    else:
        for error in all_errors:
            logger.error(f"✗ Configuration error: {error}")
        logger.error("❌ Environment configuration validation failed")
        
    return config_valid, all_errors

def sanitize_url(url):
    """Sanitize URL for logging (remove sensitive parameters)."""
    try:
        parsed = urlparse(url)
        # Remove query parameters and fragments that might contain sensitive data
        sanitized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return sanitized
    except Exception:
        return "INVALID_URL"

def log_startup_configuration():
    """Log startup configuration for debugging and validation."""
    logger.info("=== River Level Monitor Starting ===")
    
    # Log environment detection
    containerised = os.getenv('CONTAINERISED', 'NO')
    logger.info(f"Environment mode: {'Containerised' if containerised == 'YES' else 'Standalone'}")
    
    # Log configuration values (sanitized)
    config_info = {
        'read_units': READ_UNITS,
        'read_interval': READ_INTERVAL,
        'containerised': containerised == 'YES'
    }
    
    if containerised == 'YES':
        # Log environment variable configuration
        config_info.update({
            'river_measure_api': sanitize_url(os.getenv('RIVER_MEASURE_API', 'NOT_SET')),
            'river_station_api': sanitize_url(os.getenv('RIVER_STATION_API', 'NOT_SET')),
            'rain_measure_api': sanitize_url(os.getenv('RAIN_MEASURE_API', 'NOT_SET')),
            'rain_station_api': sanitize_url(os.getenv('RAIN_STATION_API', 'NOT_SET')),
            'metrics_port': os.getenv('METRICS_PORT', 'NOT_SET')
        })
    else:
        # Log hardcoded configuration (will be set after this function)
        logger.info("Using hardcoded configuration values")
    
    # Log configuration
    for key, value in config_info.items():
        logger.info(f"Config {key}: {value}")
    
    # Validate configuration
    if containerised == 'YES':
        is_valid, errors = validate_environment_config()
        if not is_valid:
            logger.error("Configuration validation failed - application may not work correctly")
            for error in errors:
                logger.error(f"  - {error}")
            return False
    
    logger.info("✓ Configuration validation completed successfully")
    return True

def validate_config_on_startup():
    """Fail fast if configuration is invalid."""
    if not log_startup_configuration():
        logger.critical("Invalid configuration detected - application cannot start")
        sys.exit(1)

# API response validation functions
def validate_measurement_response(response_data, response_type="measurement"):
    """Validate API response has expected structure for measurement data."""
    if response_data is None:
        return False, "Response data is None"
    
    if not isinstance(response_data, dict):
        return False, "Response is not a dictionary"
    
    # Check for required top-level structure
    if 'items' not in response_data:
        return False, "Missing 'items' key in response"
    
    items = response_data['items']
    if not isinstance(items, dict):
        return False, "'items' is not a dictionary"
    
    # Validate measurement-specific structure
    if response_type == "measurement":
        if 'latestReading' not in items:
            return False, "Missing 'latestReading' in items"
        
        latest_reading = items['latestReading']
        if not isinstance(latest_reading, dict):
            return False, "'latestReading' is not a dictionary"
        
        if 'value' not in latest_reading:
            return False, "Missing 'value' in latestReading"
        
        # Validate value can be converted to float
        try:
            float(latest_reading['value'])
        except (ValueError, TypeError):
            return False, f"Cannot convert value to float: {latest_reading['value']}"
    
    # Validate station-specific structure
    elif response_type == "station":
        required_fields = ['label', 'stationReference', 'gridReference']
        for field in required_fields:
            if field not in items:
                return False, f"Missing '{field}' in station response"
        
        # Validate stageScale for river stations
        if 'stageScale' in items:
            stage_scale = items['stageScale']
            if not isinstance(stage_scale, dict):
                return False, "'stageScale' is not a dictionary"
    
    return True, "Response structure is valid"

def validate_station_response(response_data):
    """Validate API response for station data."""
    return validate_measurement_response(response_data, "station")

def assess_functionality_status():
    """Assess and log current functionality status."""
    status = {
        'river_api_available': initialise_river_gauge_station_response is not None,
        'rain_api_available': initialise_rain_gauge_station_response is not None,
        'degraded_mode': False
    }
    
    if not status['river_api_available'] and not status['rain_api_available']:
        status['degraded_mode'] = True
        logger.error("CRITICAL: All APIs unavailable - running in severely degraded mode", 
                    extra={'startup_phase': 'assessment'})
        degraded_mode_active.set(1)
    elif not status['river_api_available']:
        status['degraded_mode'] = True
        logger.warning("River API unavailable - partial functionality only", 
                      extra={'startup_phase': 'assessment'})
        degraded_mode_active.set(1)
    elif not status['rain_api_available']:
        status['degraded_mode'] = True
        logger.warning("Rain API unavailable - partial functionality only", 
                      extra={'startup_phase': 'assessment'})
        degraded_mode_active.set(1)
    else:
        logger.info("All APIs available - full functionality", 
                   extra={'startup_phase': 'assessment'})
        degraded_mode_active.set(0)
    
    return status

class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler for health check endpoint."""
    
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
    
    def log_message(self, format, *args):
        """Override to use structured logging."""
        logger.info(f"Health check: {format % args}", extra={'component': 'health_server'})

def start_health_server():
    """Start the health check server in a separate thread."""
    try:
        health_server = HTTPServer(('', 8898), HealthHandler)
        health_thread = threading.Thread(target=health_server.serve_forever)
        health_thread.daemon = True
        health_thread.start()
        logger.info("Health check server started on port 8898", extra={'startup_phase': 'health_server'})
        return health_server
    except Exception as e:
        logger.error(f"Failed to start health server: {e}", extra={'startup_phase': 'health_server'})
        return None

# set api uris.
## Try if environment variable has been set (e.g. that module running in container)
try:
    if os.environ['CONTAINERISED'] == 'YES':
        logger.info("Module containerised, using environment values for measure and station APIs", 
                   extra={'startup_phase': 'configuration'})
        RIVER_MEASURE_API = os.environ['RIVER_MEASURE_API']
        RIVER_STATION_API = os.environ['RIVER_STATION_API']
        RAIN_MEASURE_API = os.environ['RAIN_MEASURE_API']
        RAIN_STATION_API = os.environ['RAIN_STATION_API']

## If error raised use hardcoded values
except KeyError:
    logger.info("Module not containerised, using hard coded values for measure and station APIs", 
               extra={'startup_phase': 'configuration'})
    RIVER_MEASURE_API = "https://environment.data.gov.uk/flood-monitoring/id/measures/531160-level-stage-i-15_min-mASD.json"
    RIVER_STATION_API = "https://environment.data.gov.uk/flood-monitoring/id/stations/531160.json"
    RAIN_MEASURE_API = "http://environment.data.gov.uk/flood-monitoring/id/measures/53107-rainfall-tipping_bucket_raingauge-t-15_min-mm.json"
    RAIN_STATION_API = "https://environment.data.gov.uk/flood-monitoring/id/stations/53107.json"

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

# Define initialization metrics
initialization_success = Counter('riverlevel_initialization_success_total', 
                                'Number of successful API initializations',
                                ['api_type'])
initialization_failure = Counter('riverlevel_initialization_failure_total',
                                'Number of failed API initializations', 
                                ['api_type'])
startup_time = Histogram('riverlevel_startup_seconds',
                        'Time taken for application startup')
application_start_time = Gauge('riverlevel_application_start_timestamp',
                              'Timestamp when application started')
degraded_mode_active = Gauge('riverlevel_degraded_mode_active',
                           'Whether application is running in degraded mode')

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

# Create session with retry strategy
def create_robust_session():
    """Create requests session with retry strategy and error handling."""
    session = rq.Session()
    
    # Configure retry strategy using proven urllib3 implementation
    retry_strategy = Retry(
        total=5,                    # Maximum number of retries
        backoff_factor=1,           # Exponential backoff factor
        status_forcelist=[429, 500, 502, 503, 504],  # HTTP codes to retry
        allowed_methods=["GET"],   # Only retry GET requests
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

# define functions

def get_station_name(obj):
    """Function takes api output from EA API and returns name of station as string."""
    if obj is None:
        return "Unknown Station"
    
    # Validate response structure before parsing
    is_valid, error_msg = validate_station_response(obj)
    if not is_valid:
        logger.warning(f"Invalid station response structure: {error_msg}")
        return "Unknown Station"
    
    try:
        return str(obj['items']['label'])
    except (KeyError, TypeError) as e:
        logger.warning(f"Unable to parse station name from API response: {e}")
        return "Unknown Station"

def get_height(obj):
    """Function takes api output from EA API and returns river level as float or None."""
    if obj is None:
        return None
    
    # Validate response structure before parsing
    is_valid, error_msg = validate_measurement_response(obj, "measurement")
    if not is_valid:
        logger.warning(f"Invalid measurement response structure: {error_msg}")
        return None
    
    try:
        return float(obj['items']['latestReading']['value'])
    except (KeyError, TypeError, ValueError) as e:
        logger.warning(f"Unable to parse river height from API response: {e}")
        return None

def get_typical(obj):
    """Function takes api output from EA API and returns information about station."""
    if obj is None:
        return None
    
    # Validate response structure before parsing
    is_valid, error_msg = validate_station_response(obj)
    if not is_valid:
        logger.warning(f"Invalid station response structure: {error_msg}")
        return None
    
    try:
        return float(obj['items']['stageScale']['typicalRangeHigh'])
    except (KeyError, TypeError, ValueError) as e:
        logger.warning(f"Unable to parse typical range from API response: {e}")
        return None

def get_record_max(obj):
    """Function takes api output from EA API and returns information about station."""
    if obj is None:
        return None
    
    # Validate response structure before parsing
    is_valid, error_msg = validate_station_response(obj)
    if not is_valid:
        logger.warning(f"Invalid station response structure: {error_msg}")
        return None
    
    try:
        return float(obj['items']['stageScale']['maxOnRecord']['value'])
    except (KeyError, TypeError, ValueError) as e:
        logger.warning(f"Unable to parse record max from API response: {e}")
        return None

def get_station_grid_ref(obj):
    """Function takes api output from EA API and returns station grid ref."""
    if obj is None:
        return "UNKNOWN"
    
    # Validate response structure before parsing
    is_valid, error_msg = validate_station_response(obj)
    if not is_valid:
        logger.warning(f"Invalid station response structure: {error_msg}")
        return "UNKNOWN"
    
    try:
        return str(obj['items']['gridReference'])
    except (KeyError, TypeError) as e:
        logger.warning(f"Unable to parse grid reference from API response: {e}")
        return "UNKNOWN"

def get_station_id(obj):
    """Function takes api output from EA API and returns station ID."""
    if obj is None:
        return "UNKNOWN"
    
    # Validate response structure before parsing
    is_valid, error_msg = validate_station_response(obj)
    if not is_valid:
        logger.warning(f"Invalid station response structure: {error_msg}")
        return "UNKNOWN"
    
    try:
        return str(obj['items']['stationReference'])
    except (KeyError, TypeError) as e:
        logger.warning(f"Unable to parse station ID from API response: {e}")
        return "UNKNOWN"

def get_rainfall(obj):
    """Function takes api output from EA API and returns rainfall as float or None."""
    if obj is None:
        return None
    
    # Validate response structure before parsing
    is_valid, error_msg = validate_measurement_response(obj, "measurement")
    if not is_valid:
        logger.warning(f"Invalid measurement response structure: {error_msg}")
        return None
    
    try:
        return float(obj['items']['latestReading']['value'])
    except (KeyError, TypeError, ValueError) as e:
        logger.warning(f"Unable to parse rainfall from API response: {e}")
        return None

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
    time.sleep(READ_INTERVAL * READ_UNITS)


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

# initialise the gauges
## call the API to get the station JSON with robust retry logic
initialise_river_gauge_station_response = make_api_call_with_retry(RIVER_STATION_API, "river_station")
initialise_rain_gauge_station_response = make_api_call_with_retry(RAIN_STATION_API, "rain_station")

## get river station name for gauge labels with validation and fallback
if initialise_river_gauge_station_response is None:
    logger.warning("Failed to fetch river station info - using default labels", 
                   extra={'api_endpoint': RIVER_STATION_API, 'fallback_used': True, 'startup_phase': 'initialization'})
    initialization_failure.labels(api_type='river_station').inc()
    SN = "Unknown River Station"
    SN_UNDERSCORES = "unknown_river_station"
else:
    SN = get_station_name(initialise_river_gauge_station_response)
    if SN is None:
        SN = "Unknown River Station"
    SN_UNDERSCORES = SN.replace(', ','_').lower()
    initialization_success.labels(api_type='river_station').inc()
    logger.info(f"River station initialized: {SN}", extra={'startup_phase': 'initialization'})

## get rain station id and grid ref for gauge label with validation and fallback
if initialise_rain_gauge_station_response is None:
    logger.warning("Failed to fetch rain station info - using default labels", 
                   extra={'api_endpoint': RAIN_STATION_API, 'fallback_used': True, 'startup_phase': 'initialization'})
    initialization_failure.labels(api_type='rain_station').inc()
    SID = "UNKNOWN"
    SGRIDREF = "UNKNOWN"
else:
    SID = get_station_id(initialise_rain_gauge_station_response)
    if SID is None:
        SID = "UNKNOWN"
    
    SGRIDREF = get_station_grid_ref(initialise_rain_gauge_station_response)
    if SGRIDREF is None:
        SGRIDREF = "UNKNOWN"
    else:
        SGRIDREF = SGRIDREF.replace(' ','_').upper()
    initialization_success.labels(api_type='rain_station').inc()
    logger.info(f"Rain station initialized: ID={SID}, GridRef={SGRIDREF}", extra={'startup_phase': 'initialization'})

## Actually initialise the gauges
gauge_river_level = Gauge(f'{SN_UNDERSCORES}_river_level', f'River level at {SN}')

gauge_river_typical_level = Gauge(f'{SN_UNDERSCORES}_typical_level', f'Typical max level at {SN}')

gauge_river_max_record = Gauge(f'{SN_UNDERSCORES}_max_record', f'max record level at {SN}')

gauge_rainfall = Gauge(f'rainfall_osgridref_{SGRIDREF}', f'Rainfall level at environment agency station ID {SID} OS Grid Reference ({SGRIDREF})')

# Assess functionality status after initialization
functionality_status = assess_functionality_status()

if __name__ == "__main__":
    main()
