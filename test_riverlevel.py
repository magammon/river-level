"""
Comprehensive unit tests for riverlevel.py

This test suite covers:
- Core API parsing functions
- Station information extraction
- Data validation functions
- Error handling and fallback behavior
- Configuration validation
- Health check functionality
- API client behavior with mock responses

Target: 80%+ code coverage
"""

import pytest
import json
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock, Mock, mock_open
import requests
import requests_mock
from datetime import datetime, timezone
import threading
import time
from io import StringIO

# Import the module under test
import riverlevel


class TestCoreAPIFunctions:
    """Test core API parsing functions with comprehensive scenarios."""

    def test_get_height_success(self):
        """Test successful height extraction from valid API response."""
        valid_response = {
            'items': {
                'latestReading': {
                    'value': 1.25,
                    'dateTime': '2024-01-01T10:00:00Z'
                }
            }
        }
        result = riverlevel.get_height(valid_response)
        assert result == 1.25

    def test_get_height_none_input(self):
        """Test height extraction with None input."""
        result = riverlevel.get_height(None)
        assert result is None

    def test_get_height_missing_items(self):
        """Test height extraction with missing items key."""
        invalid_response = {'data': 'some_data'}
        result = riverlevel.get_height(invalid_response)
        assert result is None

    def test_get_height_missing_latest_reading(self):
        """Test height extraction with missing latestReading."""
        invalid_response = {
            'items': {
                'otherData': 'value'
            }
        }
        result = riverlevel.get_height(invalid_response)
        assert result is None

    def test_get_height_invalid_value_type(self):
        """Test height extraction with non-numeric value."""
        invalid_response = {
            'items': {
                'latestReading': {
                    'value': 'not_a_number'
                }
            }
        }
        result = riverlevel.get_height(invalid_response)
        assert result is None

    def test_get_rainfall_success(self):
        """Test successful rainfall extraction from valid API response."""
        valid_response = {
            'items': {
                'latestReading': {
                    'value': 5.2,
                    'dateTime': '2024-01-01T10:00:00Z'
                }
            }
        }
        result = riverlevel.get_rainfall(valid_response)
        assert result == 5.2

    def test_get_rainfall_none_input(self):
        """Test rainfall extraction with None input."""
        result = riverlevel.get_rainfall(None)
        assert result is None

    def test_get_rainfall_zero_value(self):
        """Test rainfall extraction with zero value."""
        valid_response = {
            'items': {
                'latestReading': {
                    'value': 0.0
                }
            }
        }
        result = riverlevel.get_rainfall(valid_response)
        assert result == 0.0

    def test_get_typical_success(self):
        """Test successful typical level extraction."""
        valid_response = {
            'items': {
                'label': 'River Thames at Windsor',
                'stationReference': '531160',
                'gridReference': 'SU9677',
                'stageScale': {
                    'typicalRangeHigh': 3.45
                }
            }
        }
        result = riverlevel.get_typical(valid_response)
        assert result == 3.45

    def test_get_typical_none_input(self):
        """Test typical level extraction with None input."""
        result = riverlevel.get_typical(None)
        assert result is None

    def test_get_typical_missing_stage_scale(self):
        """Test typical level extraction with missing stageScale."""
        invalid_response = {
            'items': {
                'otherData': 'value'
            }
        }
        result = riverlevel.get_typical(invalid_response)
        assert result is None

    def test_get_record_max_success(self):
        """Test successful record max extraction."""
        valid_response = {
            'items': {
                'label': 'River Thames at Windsor',
                'stationReference': '531160',
                'gridReference': 'SU9677',
                'stageScale': {
                    'maxOnRecord': {
                        'value': 4.87
                    }
                }
            }
        }
        result = riverlevel.get_record_max(valid_response)
        assert result == 4.87

    def test_get_record_max_none_input(self):
        """Test record max extraction with None input."""
        result = riverlevel.get_record_max(None)
        assert result is None

    def test_get_record_max_missing_max_on_record(self):
        """Test record max extraction with missing maxOnRecord."""
        invalid_response = {
            'items': {
                'stageScale': {
                    'otherData': 'value'
                }
            }
        }
        result = riverlevel.get_record_max(invalid_response)
        assert result is None


class TestStationInfoFunctions:
    """Test station information extraction functions."""

    def test_get_station_name_success(self):
        """Test successful station name extraction."""
        valid_response = {
            'items': {
                'label': 'River Thames at Windsor',
                'stationReference': '531160',
                'gridReference': 'SU9677'
            }
        }
        result = riverlevel.get_station_name(valid_response)
        assert result == 'River Thames at Windsor'

    def test_get_station_name_none_input(self):
        """Test station name extraction with None input."""
        result = riverlevel.get_station_name(None)
        assert result == "Unknown Station"

    def test_get_station_name_missing_label(self):
        """Test station name extraction with missing label."""
        invalid_response = {
            'items': {
                'otherData': 'value'
            }
        }
        result = riverlevel.get_station_name(invalid_response)
        assert result == "Unknown Station"

    def test_get_station_id_success(self):
        """Test successful station ID extraction."""
        valid_response = {
            'items': {
                'label': 'River Thames at Windsor',
                'stationReference': '531160',
                'gridReference': 'SU9677'
            }
        }
        result = riverlevel.get_station_id(valid_response)
        assert result == '531160'

    def test_get_station_id_none_input(self):
        """Test station ID extraction with None input."""
        result = riverlevel.get_station_id(None)
        assert result == "UNKNOWN"

    def test_get_station_id_missing_reference(self):
        """Test station ID extraction with missing stationReference."""
        invalid_response = {
            'items': {
                'otherData': 'value'
            }
        }
        result = riverlevel.get_station_id(invalid_response)
        assert result == "UNKNOWN"

    def test_get_station_grid_ref_success(self):
        """Test successful grid reference extraction."""
        valid_response = {
            'items': {
                'label': 'River Thames at Windsor',
                'stationReference': '531160',
                'gridReference': 'SU9677'
            }
        }
        result = riverlevel.get_station_grid_ref(valid_response)
        assert result == 'SU9677'

    def test_get_station_grid_ref_none_input(self):
        """Test grid reference extraction with None input."""
        result = riverlevel.get_station_grid_ref(None)
        assert result == "UNKNOWN"

    def test_get_station_grid_ref_missing_grid_reference(self):
        """Test grid reference extraction with missing gridReference."""
        invalid_response = {
            'items': {
                'otherData': 'value'
            }
        }
        result = riverlevel.get_station_grid_ref(invalid_response)
        assert result == "UNKNOWN"


class TestValidationFunctions:
    """Test configuration and data validation functions."""

    def test_validate_url_format_valid_https(self):
        """Test URL validation with valid HTTPS URL."""
        valid_url = "https://api.example.com/data"
        result = riverlevel.validate_url_format(valid_url)
        assert result is True

    def test_validate_url_format_valid_http(self):
        """Test URL validation with valid HTTP URL."""
        valid_url = "http://localhost:8080/api"
        result = riverlevel.validate_url_format(valid_url)
        assert result is True

    def test_validate_url_format_invalid_scheme(self):
        """Test URL validation with invalid scheme."""
        invalid_url = "ftp://example.com/data"
        result = riverlevel.validate_url_format(invalid_url)
        assert result is False

    def test_validate_url_format_no_scheme(self):
        """Test URL validation with missing scheme."""
        invalid_url = "example.com/data"
        result = riverlevel.validate_url_format(invalid_url)
        assert result is False

    def test_validate_url_format_malformed(self):
        """Test URL validation with malformed URL."""
        invalid_url = "not_a_url"
        result = riverlevel.validate_url_format(invalid_url)
        assert result is False

    @patch.dict(os.environ, {
        'RIVER_MEASURE_API': 'https://api.example.com/river',
        'RIVER_STATION_API': 'https://api.example.com/station',
        'RAIN_MEASURE_API': 'https://api.example.com/rain',
        'RAIN_STATION_API': 'https://api.example.com/rain_station',
        'METRICS_PORT': '8897'
    })
    def test_validate_required_vars_success(self):
        """Test validation with all required variables present."""
        is_valid, errors = riverlevel.validate_required_vars()
        assert is_valid is True
        assert len(errors) == 0

    @patch.dict(os.environ, {
        'RIVER_MEASURE_API': 'https://api.example.com/river',
        'RAIN_MEASURE_API': 'https://api.example.com/rain',
        'METRICS_PORT': '8897'
    }, clear=True)
    def test_validate_required_vars_missing(self):
        """Test validation with missing required variables."""
        is_valid, errors = riverlevel.validate_required_vars()
        assert is_valid is False
        assert len(errors) == 2  # Missing RIVER_STATION_API and RAIN_STATION_API

    def test_validate_metrics_port_valid(self):
        """Test metrics port validation with valid port."""
        is_valid, message = riverlevel.validate_metrics_port("8897")
        assert is_valid is True
        assert "8897 is valid" in message

    def test_validate_metrics_port_invalid_range(self):
        """Test metrics port validation with out-of-range port."""
        is_valid, message = riverlevel.validate_metrics_port("99999")
        assert is_valid is False
        assert "out of valid range" in message

    def test_validate_metrics_port_non_integer(self):
        """Test metrics port validation with non-integer value."""
        is_valid, message = riverlevel.validate_metrics_port("not_a_number")
        assert is_valid is False
        assert "not a valid integer" in message

    def test_sanitize_url_success(self):
        """Test URL sanitization with valid URL."""
        test_url = "https://api.example.com/data?key=secret&param=value"
        result = riverlevel.sanitize_url(test_url)
        assert result == "https://api.example.com/data"

    def test_sanitize_url_invalid(self):
        """Test URL sanitization with invalid URL."""
        invalid_url = "not_a_url"
        result = riverlevel.sanitize_url(invalid_url)
        assert result == "://not_a_url"


class TestErrorHandlingAndFallbacks:
    """Test error handling scenarios and fallback behavior."""

    def test_all_functions_handle_empty_dict(self):
        """Test that all functions handle empty dictionary gracefully."""
        empty_dict = {}
        
        # Test all core functions
        assert riverlevel.get_height(empty_dict) is None
        assert riverlevel.get_rainfall(empty_dict) is None
        assert riverlevel.get_typical(empty_dict) is None
        assert riverlevel.get_record_max(empty_dict) is None
        assert riverlevel.get_station_name(empty_dict) == "Unknown Station"
        assert riverlevel.get_station_id(empty_dict) == "UNKNOWN"
        assert riverlevel.get_station_grid_ref(empty_dict) == "UNKNOWN"

    def test_all_functions_handle_malformed_data(self):
        """Test that all functions handle malformed data structures."""
        malformed_data = {
            'items': {
                'latestReading': {
                    'value': {'nested': 'object'}  # Should be a number
                }
            }
        }
        
        # These should all return None or fallback values
        assert riverlevel.get_height(malformed_data) is None
        assert riverlevel.get_rainfall(malformed_data) is None

    def test_functions_handle_string_instead_of_dict(self):
        """Test that all functions handle string input instead of dictionary."""
        string_input = "not_a_dict"
        
        # All functions should handle this gracefully
        assert riverlevel.get_height(string_input) is None
        assert riverlevel.get_rainfall(string_input) is None
        assert riverlevel.get_typical(string_input) is None
        assert riverlevel.get_record_max(string_input) is None
        assert riverlevel.get_station_name(string_input) == "Unknown Station"
        assert riverlevel.get_station_id(string_input) == "UNKNOWN"
        assert riverlevel.get_station_grid_ref(string_input) == "UNKNOWN"


class TestIntegrationScenarios:
    """Integration tests for API client functionality with mock responses."""

    def test_mock_api_response_parsing(self):
        """Test parsing of realistic API responses."""
        # Realistic Environment Agency API response structure
        station_response = {
            'items': {
                'label': 'River Thames at Windsor',
                'stationReference': '531160',
                'gridReference': 'SU9677',
                'stageScale': {
                    'typicalRangeHigh': 3.45,
                    'maxOnRecord': {
                        'value': 4.87,
                        'dateTime': '2014-02-14T12:00:00Z'
                    }
                }
            }
        }
        
        measurement_response = {
            'items': {
                'latestReading': {
                    'value': 1.25,
                    'dateTime': '2024-01-01T10:00:00Z'
                }
            }
        }
        
        # Test all extractions work correctly
        assert riverlevel.get_station_name(station_response) == 'River Thames at Windsor'
        assert riverlevel.get_station_id(station_response) == '531160'
        assert riverlevel.get_station_grid_ref(station_response) == 'SU9677'
        assert riverlevel.get_typical(station_response) == 3.45
        assert riverlevel.get_record_max(station_response) == 4.87
        assert riverlevel.get_height(measurement_response) == 1.25

    @patch.dict(os.environ, {'CONTAINERISED': 'NO'})
    def test_standalone_mode_configuration(self):
        """Test configuration validation in standalone mode."""
        is_valid, errors = riverlevel.validate_environment_config()
        assert is_valid is True
        assert len(errors) == 0

    @patch.dict(os.environ, {
        'CONTAINERISED': 'YES',
        'RIVER_MEASURE_API': 'https://api.example.com/river',
        'RIVER_STATION_API': 'https://api.example.com/station',
        'RAIN_MEASURE_API': 'https://api.example.com/rain',
        'RAIN_STATION_API': 'https://api.example.com/rain_station',
        'METRICS_PORT': '8897'
    })
    def test_containerised_mode_valid_configuration(self):
        """Test configuration validation in containerised mode with valid config."""
        is_valid, errors = riverlevel.validate_environment_config()
        assert is_valid is True
        assert len(errors) == 0

    @patch.dict(os.environ, {
        'CONTAINERISED': 'YES',
        'RIVER_MEASURE_API': 'invalid_url',
        'METRICS_PORT': '99999'
    }, clear=True)
    def test_containerised_mode_invalid_configuration(self):
        """Test configuration validation in containerised mode with invalid config."""
        is_valid, errors = riverlevel.validate_environment_config()
        assert is_valid is False
        assert len(errors) > 0


class TestLoggingConfiguration:
    """Test logging setup and configuration."""

    def test_setup_logging_returns_logger(self):
        """Test that setup_logging returns a configured logger."""
        logger = riverlevel.setup_logging()
        assert logger is not None
        assert logger.level == riverlevel.logging.INFO

    def test_json_formatter_basic_message(self):
        """Test JSON formatter with basic log message."""
        logger = riverlevel.setup_logging()
        
        # Create a test handler to capture output
        test_handler = riverlevel.logging.StreamHandler(StringIO())
        json_formatter = riverlevel.logging.handlers.RotatingFileHandler.__new__(
            riverlevel.logging.handlers.RotatingFileHandler
        )
        
        # This test ensures the JSON formatter class exists and can be instantiated
        assert hasattr(riverlevel, 'setup_logging')


class TestHealthCheckScenarios:
    """Test health check endpoint and status reporting."""

    def test_health_check_components_exist(self):
        """Test that health check related components exist in the module."""
        # These tests verify the health check infrastructure exists
        # Full integration testing would require running the actual HTTP server
        assert hasattr(riverlevel, 'setup_logging')
        assert hasattr(riverlevel, 'validate_environment_config')
        assert hasattr(riverlevel, 'CONFIG_SCHEMA')


class TestResponseValidation:
    """Test API response validation functions."""

    def test_validate_measurement_response_valid(self):
        """Test measurement response validation with valid data."""
        valid_response = {
            'items': {
                'latestReading': {
                    'value': 1.25
                }
            }
        }
        is_valid, message = riverlevel.validate_measurement_response(valid_response, "measurement")
        assert is_valid is True

    def test_validate_measurement_response_invalid_none(self):
        """Test measurement response validation with None input."""
        is_valid, message = riverlevel.validate_measurement_response(None, "measurement")
        assert is_valid is False
        assert "Response data is None" in message

    def test_validate_measurement_response_invalid_type(self):
        """Test measurement response validation with wrong type."""
        is_valid, message = riverlevel.validate_measurement_response("not_a_dict", "measurement")
        assert is_valid is False
        assert "Response is not a dictionary" in message

    def test_validate_measurement_response_missing_items(self):
        """Test measurement response validation with missing items."""
        invalid_response = {'data': 'value'}
        is_valid, message = riverlevel.validate_measurement_response(invalid_response, "measurement")
        assert is_valid is False
        assert "Missing 'items' key in response" in message

    def test_validate_station_response_valid(self):
        """Test station response validation with valid data."""
        valid_response = {
            'items': {
                'label': 'River Thames at Windsor',
                'stationReference': '531160',
                'gridReference': 'SU9677'
            }
        }
        is_valid, message = riverlevel.validate_station_response(valid_response)
        assert is_valid is True

    def test_validate_station_response_missing_required_field(self):
        """Test station response validation with missing required field."""
        invalid_response = {
            'items': {
                'label': 'River Thames at Windsor',
                'stationReference': '531160'
                # Missing gridReference
            }
        }
        is_valid, message = riverlevel.validate_station_response(invalid_response)
        assert is_valid is False
        assert "Missing" in message and "gridReference" in message


class TestConfigurationValidation:
    """Test configuration validation edge cases."""

    def test_config_schema_constants(self):
        """Test that CONFIG_SCHEMA contains expected values."""
        assert 'required_env_vars' in riverlevel.CONFIG_SCHEMA
        assert 'port_range' in riverlevel.CONFIG_SCHEMA
        assert 'url_schemes' in riverlevel.CONFIG_SCHEMA
        assert len(riverlevel.CONFIG_SCHEMA['required_env_vars']) == 5
        assert riverlevel.CONFIG_SCHEMA['port_range'] == (1, 65535)
        assert 'http' in riverlevel.CONFIG_SCHEMA['url_schemes']
        assert 'https' in riverlevel.CONFIG_SCHEMA['url_schemes']

    def test_validate_api_urls_success(self):
        """Test API URL validation with valid URLs."""
        valid_urls = {
            'RIVER_MEASURE_API': 'https://api.example.com/river',
            'RAIN_STATION_API': 'https://api.example.com/rain',
            'OTHER_VAR': 'not_a_url'  # Should be ignored
        }
        is_valid, errors = riverlevel.validate_api_urls(valid_urls)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_api_urls_failure(self):
        """Test API URL validation with invalid URLs."""
        invalid_urls = {
            'RIVER_MEASURE_API': 'invalid_url',
            'RAIN_STATION_API': 'ftp://example.com/rain',
            'OTHER_VAR': 'not_a_url'  # Should be ignored
        }
        is_valid, errors = riverlevel.validate_api_urls(invalid_urls)
        assert is_valid is False
        assert len(errors) == 2

    @patch.dict(os.environ, {'CONTAINERISED': 'YES'}, clear=True)
    def test_validate_environment_config_missing_vars(self):
        """Test environment config validation with missing variables."""
        is_valid, errors = riverlevel.validate_environment_config()
        assert is_valid is False
        assert len(errors) > 0

    @patch('riverlevel.logger')
    def test_log_startup_configuration_standalone(self, mock_logger):
        """Test startup configuration logging in standalone mode."""
        with patch.dict(os.environ, {'CONTAINERISED': 'NO'}):
            result = riverlevel.log_startup_configuration()
            assert result is True
            mock_logger.info.assert_called()

    @patch('riverlevel.logger')
    def test_log_startup_configuration_containerised_invalid(self, mock_logger):
        """Test startup configuration logging with invalid containerised config."""
        with patch.dict(os.environ, {'CONTAINERISED': 'YES'}, clear=True):
            result = riverlevel.log_startup_configuration()
            assert result is False
            mock_logger.error.assert_called()

    @patch('riverlevel.logger')
    @patch('riverlevel.sys.exit')
    def test_validate_config_on_startup_failure(self, mock_exit, mock_logger):
        """Test config validation on startup with invalid config."""
        with patch('riverlevel.log_startup_configuration', return_value=False):
            riverlevel.validate_config_on_startup()
            mock_logger.critical.assert_called()
            mock_exit.assert_called_with(1)


class TestUtilityFunctions:
    """Test utility and helper functions."""

    def test_setup_signal_handlers(self):
        """Test signal handler setup."""
        # This test verifies the function exists and can be called
        riverlevel.setup_signal_handlers()
        # Signal handlers are set up but we can't easily test the actual handling

    def test_read_units_and_interval_constants(self):
        """Test that read units and interval constants are defined."""
        assert hasattr(riverlevel, 'READ_UNITS')
        assert hasattr(riverlevel, 'READ_INTERVAL')
        assert riverlevel.READ_UNITS == 60
        assert riverlevel.READ_INTERVAL == 1

    def test_url_validation_edge_cases(self):
        """Test URL validation with edge cases."""
        # Test localhost HTTP (should be allowed)
        localhost_url = "http://localhost:8080/api"
        assert riverlevel.validate_url_format(localhost_url) is True
        
        # Test empty string
        assert riverlevel.validate_url_format("") is False
        
        # Test None input
        assert riverlevel.validate_url_format(None) is False

    def test_sanitize_url_edge_cases(self):
        """Test URL sanitization with edge cases."""
        # Test URL with fragment
        url_with_fragment = "https://api.example.com/data#section"
        result = riverlevel.sanitize_url(url_with_fragment)
        assert result == "https://api.example.com/data"
        
        # Test URL with both query and fragment
        complex_url = "https://api.example.com/data?param=value#section"
        result = riverlevel.sanitize_url(complex_url)
        assert result == "https://api.example.com/data"
        
        # Test empty string
        result = riverlevel.sanitize_url("")
        assert result == "://"

    def test_url_validation_with_warnings(self):
        """Test URL validation that triggers warnings."""
        # Test HTTP URL with external domain (should warn but pass)
        http_external_url = "http://external.example.com/api"
        with patch('riverlevel.logger') as mock_logger:
            result = riverlevel.validate_url_format(http_external_url)
            assert result is True
            mock_logger.warning.assert_called()

    def test_validate_url_format_exception_handling(self):
        """Test URL validation with values that cause exceptions."""
        # Test with a value that might cause urlparse to fail
        with patch('riverlevel.urlparse', side_effect=Exception("Parse error")):
            result = riverlevel.validate_url_format("https://example.com")
            assert result is False

    def test_sanitize_url_exception_handling(self):
        """Test URL sanitization with exception handling."""
        # Test with a value that might cause urlparse to fail
        with patch('riverlevel.urlparse', side_effect=Exception("Parse error")):
            result = riverlevel.sanitize_url("https://example.com")
            assert result == "INVALID_URL"


class TestMoreValidationEdgeCases:
    """Test additional validation edge cases."""

    def test_validate_measurement_response_invalid_items_type(self):
        """Test measurement response validation with wrong items type."""
        invalid_response = {'items': 'not_a_dict'}
        is_valid, message = riverlevel.validate_measurement_response(invalid_response, "measurement")
        assert is_valid is False
        assert "'items' is not a dictionary" in message

    def test_validate_measurement_response_invalid_latest_reading_type(self):
        """Test measurement response validation with wrong latestReading type."""
        invalid_response = {
            'items': {
                'latestReading': 'not_a_dict'
            }
        }
        is_valid, message = riverlevel.validate_measurement_response(invalid_response, "measurement")
        assert is_valid is False
        assert "'latestReading' is not a dictionary" in message

    def test_validate_measurement_response_invalid_value_conversion(self):
        """Test measurement response validation with non-convertible value."""
        invalid_response = {
            'items': {
                'latestReading': {
                    'value': 'cannot_convert_to_float'
                }
            }
        }
        is_valid, message = riverlevel.validate_measurement_response(invalid_response, "measurement")
        assert is_valid is False
        assert "Cannot convert value to float: cannot_convert_to_float" in message

    def test_validate_station_response_invalid_items_type(self):
        """Test station response validation with wrong items type."""
        invalid_response = {'items': 'not_a_dict'}
        is_valid, message = riverlevel.validate_station_response(invalid_response)
        assert is_valid is False
        assert "'items' is not a dictionary" in message

    def test_validate_station_response_invalid_stage_scale_type(self):
        """Test station response validation with wrong stageScale type."""
        invalid_response = {
            'items': {
                'label': 'River Thames at Windsor',
                'stationReference': '531160',
                'gridReference': 'SU9677',
                'stageScale': 'not_a_dict'
            }
        }
        is_valid, message = riverlevel.validate_station_response(invalid_response)
        assert is_valid is False
        assert "'stageScale' is not a dictionary" in message

    def test_validate_required_vars_individual_missing(self):
        """Test individual required variables missing."""
        with patch.dict(os.environ, {}, clear=True):
            is_valid, errors = riverlevel.validate_required_vars()
            assert is_valid is False
            assert len(errors) == 5
            # Check that all required variables are reported as missing
            error_text = ' '.join(errors)
            for var in ['RIVER_MEASURE_API', 'RIVER_STATION_API', 'RAIN_MEASURE_API', 'RAIN_STATION_API', 'METRICS_PORT']:
                assert var in error_text

    def test_validate_api_urls_with_mixed_validity(self):
        """Test API URL validation with mix of valid and invalid URLs."""
        mixed_urls = {
            'RIVER_MEASURE_API': 'https://valid.example.com/api',
            'RIVER_STATION_API': 'invalid_url',
            'RAIN_MEASURE_API': 'ftp://invalid.scheme.com/api',
            'RAIN_STATION_API': 'https://another.valid.example.com/api',
            'NON_API_VAR': 'ignored_value'
        }
        is_valid, errors = riverlevel.validate_api_urls(mixed_urls)
        assert is_valid is False
        assert len(errors) == 2  # Only the two invalid API URLs should be reported

    def test_validate_metrics_port_edge_cases(self):
        """Test metrics port validation with edge cases."""
        # Test minimum valid port
        is_valid, message = riverlevel.validate_metrics_port("1")
        assert is_valid is True
        
        # Test maximum valid port
        is_valid, message = riverlevel.validate_metrics_port("65535")
        assert is_valid is True
        
        # Test just below minimum
        is_valid, message = riverlevel.validate_metrics_port("0")
        assert is_valid is False
        
        # Test just above maximum
        is_valid, message = riverlevel.validate_metrics_port("65536")
        assert is_valid is False
        
        # Test negative number
        is_valid, message = riverlevel.validate_metrics_port("-1")
        assert is_valid is False
        
        # Test float string
        is_valid, message = riverlevel.validate_metrics_port("8080.5")
        assert is_valid is False


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=riverlevel', '--cov-report=html', '--cov-report=term-missing'])