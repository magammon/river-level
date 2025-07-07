"""
This module takes environment agency water level and rainfall measure and station data 
from their API and converts to prometheus metrics published through a webserver.
"""
import os
import json
import time
import sys
#import platform
import requests as rq
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
import re
from urllib.parse import urlparse
# Import Gauge and start_http_server from prometheus_client
from prometheus_client import Gauge, start_http_server, Counter, Histogram
from contextlib import contextmanager

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

# set api uris.
## Try if environment variable has been set (e.g. that module running in container)
try:
    if os.environ['CONTAINERISED'] == 'YES':
        print("Module containerised, using environment values for measure and station APIs.")
        RIVER_MEASURE_API = os.environ['RIVER_MEASURE_API']
        RIVER_STATION_API = os.environ['RIVER_STATION_API']
        RAIN_MEASURE_API = os.environ['RAIN_MEASURE_API']
        RAIN_STATION_API = os.environ['RAIN_STATION_API']

## If error raised use hardcoded values
except KeyError:
    print("Module not containerised, using hard coded values for measure and station APIs.")
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
                
    except rq.exceptions.ConnectionError as e:
        logger.error(f"Connection error for {endpoint_name}: {e}")
        api_error_counter.labels(endpoint=endpoint_name, error="connection_error").inc()
        return None
    except rq.exceptions.Timeout as e:
        logger.error(f"Request timeout for {endpoint_name}: {e}")
        api_error_counter.labels(endpoint=endpoint_name, error="timeout").inc()
        return None
    except rq.exceptions.RequestException as e:
        logger.error(f"Request error for {endpoint_name}: {e}")
        api_error_counter.labels(endpoint=endpoint_name, error="request_error").inc()
        return None
    except Exception as e:
        logger.error(f"Unexpected error for {endpoint_name}: {e}")
        api_error_counter.labels(endpoint=endpoint_name, error="unexpected_error").inc()
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
    """Function calls API, feeds to get_height and then sets prometheus guage."""
    ## get responses with robust retry logic
    river_measure_response = make_api_call_with_retry(RIVER_MEASURE_API, "river_measure")
    river_station_response = make_api_call_with_retry(RIVER_STATION_API, "river_station")
    rain_measure_response = make_api_call_with_retry(RAIN_MEASURE_API, "rain_measure")

    ## set river guage river level to output of get_height function
    # Skip metric updates instead of using misleading fallback values
    if river_measure_response is not None:
        river_height = get_height(river_measure_response)
        if river_height is not None:
            gauge_river_level.set(river_height)
        # Don't set gauge to 0.0 if data unavailable - preserve last known value
    else:
        logger.warning("Skipping river level update - API data unavailable")

    if river_station_response is not None:
        typical_level = get_typical(river_station_response)
        if typical_level is not None:
            gauge_river_typical_level.set(typical_level)
        
        max_record = get_record_max(river_station_response)
        if max_record is not None:
            gauge_river_max_record.set(max_record)
    else:
        logger.warning("Skipping river station metrics update - API data unavailable")

    if rain_measure_response is not None:
        rainfall = get_rainfall(rain_measure_response)
        if rainfall is not None:
            gauge_rainfall.set(rainfall)
        # Don't set gauge to 0.0 if data unavailable - preserve last known value
    else:
        logger.warning("Skipping rainfall update - API data unavailable")

    time.sleep(READ_INTERVAL * READ_UNITS)


def main():
    """Main application entry point with configuration validation."""
    # Validate configuration first - fail fast approach
    validate_config_on_startup()
    
    # Function starts metrics webserver
    #expose metrics
    try:
        if os.environ['CONTAINERISED'] == 'YES':
            logger.info("Module containerised, using environment values for metrics port.")
            metrics_port = os.environ['METRICS_PORT']

    except KeyError:
        logger.info("Module not containerised, using hard coded values for metrics API.")
        metrics_port = 8897

    start_http_server(int(metrics_port))
    logger.info(f"Serving sensor metrics on :{metrics_port}")

    while True:
        set_gauges()

# initialise the gauges
## call the API to get the station JSON with robust retry logic
initialise_river_gauge_station_response = make_api_call_with_retry(RIVER_STATION_API, "river_station")
initialise_rain_gauge_station_response = make_api_call_with_retry(RAIN_STATION_API, "rain_station")

## get river station name for gauge labels with validation and fallback
if initialise_river_gauge_station_response is None:
    print("Failed to fetch river station info - using default labels")
    SN = "Unknown River Station"
    SN_UNDERSCORES = "unknown_river_station"
else:
    SN = get_station_name(initialise_river_gauge_station_response)
    if SN is None:
        SN = "Unknown River Station"
    SN_UNDERSCORES = SN.replace(', ','_').lower()

## get rain station id and grid ref for gauge label with validation and fallback
if initialise_rain_gauge_station_response is None:
    print("Failed to fetch rain station info - using default labels")
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

## Actually initialise the gauges
gauge_river_level = Gauge(f'{SN_UNDERSCORES}_river_level', f'River level at {SN}')

gauge_river_typical_level = Gauge(f'{SN_UNDERSCORES}_typical_level', f'Typical max level at {SN}')

gauge_river_max_record = Gauge(f'{SN_UNDERSCORES}_max_record', f'max record level at {SN}')

gauge_rainfall = Gauge(f'rainfall_osgridref_{SGRIDREF}', f'Rainfall level at environment agency station ID {SID} OS Grid Reference ({SGRIDREF})')

if __name__ == "__main__":
    main()
