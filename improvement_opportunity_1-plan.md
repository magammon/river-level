# Phase 1: Error Handling & Reliability Implementation Plan

## Current Issues Identified:
1. **Functions crash on API errors**: `get_height()` (line 44-47), `get_rainfall()` (line 69-72), and other parsing functions will raise exceptions if API responses are missing expected fields
2. **No retry logic**: API calls in `set_gauges()` (lines 77-79) and initialization (lines 110-111) have no retry mechanism
3. **Application crashes on failures**: Missing readings cause the entire application to crash instead of graceful degradation
4. **No input validation**: No validation of API responses or environment variables

## Proposed Implementation:

### 1. Add robust error handling to all API parsing functions
- Wrap all JSON parsing in try/except blocks
- Return default/fallback values when data is missing
- Add logging for debugging failed API calls
- Functions to fix: `get_height()`, `get_rainfall()`, `get_station_name()`, `get_typical()`, `get_record_max()`, `get_station_grid_ref()`, `get_station_id()`

### 2. Implement retry logic with exponential backoff
- Create a `make_api_call_with_retry()` function
- Use exponential backoff (1s, 2s, 4s, 8s, 16s max)
- Maximum 5 retry attempts
- Apply to all API calls in `set_gauges()` and initialization

### 3. Add input validation
- Validate environment variables on startup
- Validate API response structure before parsing
- Add configuration validation logging

### 4. Graceful degradation
- Continue operation when individual metrics fail
- Skip metric updates on failures instead of crashing
- Maintain application uptime even with API issues

### 5. Improved logging
- Replace print statements with Python logging module
- Add structured logging for API failures and retries
- Include timestamps and error details

## Files to modify:
- `riverlevel.py` - Main implementation
- No new files needed - all changes are enhancements to existing code

## Testing approach:
- Test with invalid API endpoints to verify graceful failure
- Test with malformed JSON responses
- Test retry logic with network timeouts