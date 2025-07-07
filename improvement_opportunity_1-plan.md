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
    try:
        height = json.dumps(obj['items']['latestReading']['value'])
        return float(height)
    except (KeyError, TypeError, ValueError) as e:
        print(f"Unable to parse river height from API response: {e}")
        return 0.0
```

#### 1.3 Exception types to handle:
- **KeyError**: When expected JSON keys are missing
- **TypeError**: When obj is None or wrong type
- **ValueError**: When conversion to float fails
- **json.JSONDecodeError**: If JSON parsing fails (less likely since we're working with already parsed objects)

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