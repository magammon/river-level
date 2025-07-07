# Phase 1: Error Handling & Reliability Implementation Plan

## Section 3: Add input validation

### 3.1 Environment Variable Validation (riverlevel.py:32-46)

**Current Issue:**
The application uses environment variables when `CONTAINERISED=YES` but doesn't validate them:
```python
# Current vulnerable code:
RIVER_MEASURE_API = os.environ['RIVER_MEASURE_API']
RIVER_STATION_API = os.environ['RIVER_STATION_API']
RAIN_MEASURE_API = os.environ['RAIN_MEASURE_API']
RAIN_STATION_API = os.environ['RAIN_STATION_API']
```

**Proposed Solution:**
```python
import re
from urllib.parse import urlparse

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
        if not (1 <= port <= 65535):
            return False, f"Port {port} out of valid range (1-65535)"
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

def validate_url_format(url):
    """Validate URL format and structure."""
    try:
        parsed = urlparse(url)
        # Check basic URL structure
        if not all([parsed.scheme, parsed.netloc]):
            return False
        # Ensure valid HTTP schemes
        if parsed.scheme not in ['http', 'https']:
            return False
        # Prefer HTTPS for external APIs (security best practice)
        if parsed.scheme == 'http' and not parsed.netloc.startswith('localhost'):
            logger.warning(f"Using HTTP instead of HTTPS for external API: {parsed.netloc}")
        # Allow any domain but validate structure
        return True
    except Exception:
        return False
```

### 3.2 API Response Structure Validation (riverlevel.py:140-208)

**Current Issue:**
API parsing functions access JSON keys directly without validating response structure:
```python
# Current vulnerable code:
return float(obj['items']['latestReading']['value'])
```

**Proposed Solution:**
```python
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

# Updated parsing functions with validation
def get_height(obj):
    """Function takes api output from EA API and returns river level as float or None."""
    if obj is None:
        return None
    
    # Validate response structure before parsing
    is_valid, error_msg = validate_measurement_response(obj, "measurement")
    if not is_valid:
        # Separate validation from logging - let caller decide logging level
        return None
    
    try:
        return float(obj['items']['latestReading']['value'])
    except (KeyError, TypeError, ValueError) as e:
        # Log parsing errors separately from validation errors
        return None
```

### 3.3 Configuration Validation Logging (startup)

**Implementation:**
```python
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
        # Log hardcoded configuration
        config_info.update({
            'river_measure_api': sanitize_url(RIVER_MEASURE_API),
            'river_station_api': sanitize_url(RIVER_STATION_API),
            'rain_measure_api': sanitize_url(RAIN_MEASURE_API),
            'rain_station_api': sanitize_url(RAIN_STATION_API),
            'metrics_port': 8897
        })
    
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

def sanitize_url(url):
    """Sanitize URL for logging (remove sensitive parameters)."""
    try:
        parsed = urlparse(url)
        # Remove query parameters and fragments that might contain sensitive data
        sanitized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return sanitized
    except Exception:
        return "INVALID_URL"

# Integration into main application
def validate_config_on_startup():
    """Fail fast if configuration is invalid."""
    if not log_startup_configuration():
        logger.critical("Invalid configuration detected - application cannot start")
        sys.exit(1)

def main():
    """Main application entry point with configuration validation."""
    # Validate configuration first - fail fast approach
    validate_config_on_startup()
    
    # Continue with normal startup...
```

### 3.4 Testing Approach for Input Validation

**Test Cases:**
1. **Environment Variable Testing:**
   - Test with missing required environment variables
   - Test with invalid URL formats
   - Test with invalid port numbers
   - Test with non-integer port values

2. **API Response Validation Testing:**
   - Test with malformed JSON responses
   - Test with missing required keys
   - Test with wrong data types
   - Test with empty responses

3. **Configuration Logging Testing:**
   - Verify all configuration values are logged
   - Test URL sanitization
   - Verify validation error reporting

4. **Integration Testing:**
   - Test validation with real Environment Agency API responses
   - Test complete startup process with various configurations
   - Verify graceful degradation when validation fails

5. **Performance Testing:**
   - Ensure validation doesn't significantly impact startup time
   - Test validation with large JSON responses
   - Verify minimal overhead for repeated validations

6. **Edge Case Testing:**
   - Test with completely malformed JSON responses
   - Test with circular reference scenarios
   - Test with extremely large response payloads

**Implementation Steps:**
1. Add modular validation functions to `riverlevel.py`
2. Update parsing functions to use validation (separated from logging)
3. Add fail-fast configuration validation to startup
4. Implement actionable error messages
5. Test with various invalid configurations
6. Add performance benchmarks for validation functions
7. Verify graceful error handling and appropriate logging levels

**Configuration Schema Addition:**
```python
# Add configuration constants for maintainability
CONFIG_SCHEMA = {
    'required_env_vars': ['RIVER_MEASURE_API', 'RIVER_STATION_API', 
                          'RAIN_MEASURE_API', 'RAIN_STATION_API', 'METRICS_PORT'],
    'port_range': (1, 65535),
    'url_schemes': ['http', 'https'],
    'api_timeout': 30,  # seconds
    'max_response_size': 1024 * 1024  # 1MB
}
```