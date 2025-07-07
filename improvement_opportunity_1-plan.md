# Phase 1: Error Handling & Reliability Implementation Plan

## Current Issues Identified:
1. **Functions crash on API errors**: `get_height()` (line 44-47), `get_rainfall()` (line 69-72), and other parsing functions will raise exceptions if API responses are missing expected fields
2. **No retry logic**: API calls in `set_gauges()` (lines 77-79) and initialization (lines 110-111) have no retry mechanism
3. **Application crashes on failures**: Missing readings cause the entire application to crash instead of graceful degradation
4. **No input validation**: No validation of API responses or environment variables

## Proposed Implementation:

### 1. Add robust error handling to all API parsing functions

#### 1.1 Function-by-function error handling implementation:

**`get_height(obj)` (lines 44-47):**
- Current: `json.dumps(obj['items']['latestReading']['value'])` - crashes if any key missing
- New: Try/except with KeyError, TypeError, ValueError handling
- Fallback: Return `0.0` (float) when data unavailable
- Log: "Unable to parse river height from API response"

**`get_rainfall(obj)` (lines 69-72):**
- Current: `json.dumps(obj['items']['latestReading']['value'])` - crashes if any key missing
- New: Try/except with KeyError, TypeError, ValueError handling  
- Fallback: Return `0.0` (float) when data unavailable
- Log: "Unable to parse rainfall from API response"

**`get_station_name(obj)` (lines 39-42):**
- Current: `json.dumps(obj['items']['label'])` - crashes if keys missing
- New: Try/except with KeyError, TypeError handling
- Fallback: Return `"Unknown Station"` (string) when data unavailable
- Log: "Unable to parse station name from API response"

**`get_typical(obj)` (lines 49-52):**
- Current: `json.dumps(obj['items']['stageScale']['typicalRangeHigh'])` - crashes if nested keys missing
- New: Try/except with KeyError, TypeError, ValueError handling
- Fallback: Return `0.0` (float) when data unavailable
- Log: "Unable to parse typical range from API response"

**`get_record_max(obj)` (lines 54-57):**
- Current: `json.dumps(obj['items']['stageScale']['maxOnRecord']['value'])` - crashes if nested keys missing
- New: Try/except with KeyError, TypeError, ValueError handling
- Fallback: Return `0.0` (float) when data unavailable
- Log: "Unable to parse record max from API response"

**`get_station_grid_ref(obj)` (lines 59-62):**
- Current: `json.dumps(obj['items']['gridReference'])` - crashes if keys missing
- New: Try/except with KeyError, TypeError handling
- Fallback: Return `"UNKNOWN"` (string) when data unavailable
- Log: "Unable to parse grid reference from API response"

**`get_station_id(obj)` (lines 64-67):**
- Current: `json.dumps(obj['items']['stationReference'])` - crashes if keys missing
- New: Try/except with KeyError, TypeError handling
- Fallback: Return `"UNKNOWN"` (string) when data unavailable
- Log: "Unable to parse station ID from API response"

#### 1.2 Error handling pattern:
```python
def get_height(obj):
    """Function takes api output from EA API and returns river level as float."""
    if obj is None:
        return 0.0
    try:
        return float(obj['items']['latestReading']['value'])
    except (KeyError, TypeError, ValueError) as e:
        print(f"Unable to parse river height from API response: {e}")
        return 0.0
```

#### 1.3 Exception types to handle:
- **KeyError**: When expected JSON keys are missing
- **TypeError**: When obj is None or wrong type
- **ValueError**: When conversion to float fails
- **requests.exceptions.ConnectionError**: Network connection failures
- **requests.exceptions.Timeout**: Request timeout errors
- **requests.exceptions.RequestException**: General request errors

#### 1.4 Fallback values rationale:
- **Numeric values**: `0.0` - neutral value that won't break Prometheus metrics
- **String values**: Descriptive defaults (`"Unknown Station"`, `"UNKNOWN"`) - clearly indicate missing data
- **Maintains type consistency**: All functions return expected types even on error

#### 1.5 Testing approach for step 1:
- Test each function with `None` input
- Test with empty dictionary `{}`
- Test with partial data (missing nested keys)
- Test with wrong data types (strings where numbers expected)
- Verify fallback values are returned and logged appropriately

### 2. Implement retry logic with exponential backoff

#### 2.1 Enhanced API call function:
```python
def make_api_call_with_retry(url, max_retries=5):
    """Make API call with retry logic and exponential backoff."""
    import requests
    import time
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"HTTP {response.status_code} for {url}")
        except (requests.exceptions.ConnectionError, 
                requests.exceptions.Timeout,
                requests.exceptions.RequestException) as e:
            print(f"Network error (attempt {attempt+1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
    return None  # All retries failed
```

#### 2.2 Apply to all API calls:
- Replace direct `rq.get()` calls in `set_gauges()` (lines 77-79)
- Replace initialization API calls (lines 110-111)
- Add HTTP status code validation before JSON parsing

### 3. Add input validation
- Validate environment variables on startup
- Validate API response structure before parsing
- Add configuration validation logging

### 4. Add initialization error handling

#### 4.1 Critical issue:
The initialization code (lines 110-111) can crash the entire application if station APIs are unavailable:
```python
# Current vulnerable code:
initialise_river_gauge_station_response = rq.get(RIVER_STATION_API, timeout=30)
initialise_rain_gauge_station_response = rq.get(RAIN_STATION_API, timeout=30)
```

#### 4.2 Proposed solution:
- Use `make_api_call_with_retry()` for initialization API calls
- Provide fallback values for gauge labels if APIs fail
- Allow application to start even with missing station metadata

### 5. Graceful degradation
- Continue operation when individual metrics fail
- Skip metric updates on failures instead of crashing
- Maintain application uptime even with API issues
- Handle missing data in `set_gauges()` function

### 6. Improved logging
- Replace print statements with Python logging module
- Add structured logging for API failures and retries
- Include timestamps and error details

### 7. Additional improvements identified

#### 7.1 Inefficient JSON handling:
- Current code uses `json.dumps()` on already-parsed JSON objects
- Remove unnecessary `json.dumps()` calls and `.replace('"','')` operations
- Direct access to values is more efficient and cleaner

#### 7.2 Missing rain station API error handling:
- Plan should include error handling for rain station API calls in `set_gauges()`
- Rain measurement parsing needs same error handling as river measurements

## Files to modify:
- `riverlevel.py` - Main implementation
- No new files needed - all changes are enhancements to existing code

## Testing approach:
- Test with invalid API endpoints to verify graceful failure
- Test with malformed JSON responses
- Test retry logic with network timeouts
- Test initialization with unavailable station APIs
- Test HTTP error codes (404, 500, etc.)
- Test network connectivity issues
- Verify application continues running when individual metrics fail