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
- Fallback: Return `None` when data unavailable (don't mislead with 0.0)
- Fix: Remove unnecessary `json.dumps()` - value is already parsed
- Log: "Unable to parse river height from API response"

**`get_rainfall(obj)` (lines 69-72):**
- Current: `json.dumps(obj['items']['latestReading']['value'])` - crashes if any key missing
- New: Try/except with KeyError, TypeError, ValueError handling  
- Fallback: Return `None` when data unavailable (don't mislead with 0.0)
- Fix: Remove unnecessary `json.dumps()` - value is already parsed
- Log: "Unable to parse rainfall from API response"

**`get_station_name(obj)` (lines 39-42):**
- Current: `json.dumps(obj['items']['label'])` - crashes if keys missing
- New: Try/except with KeyError, TypeError handling
- Fallback: Return `"Unknown Station"` (string) when data unavailable
- Fix: Remove unnecessary `json.dumps()` - value is already parsed
- Log: "Unable to parse station name from API response"

**`get_typical(obj)` (lines 49-52):**
- Current: `json.dumps(obj['items']['stageScale']['typicalRangeHigh'])` - crashes if nested keys missing
- New: Try/except with KeyError, TypeError, ValueError handling
- Fallback: Return `None` when data unavailable (don't mislead with 0.0)
- Fix: Remove unnecessary `json.dumps()` - value is already parsed
- Log: "Unable to parse typical range from API response"

**`get_record_max(obj)` (lines 54-57):**
- Current: `json.dumps(obj['items']['stageScale']['maxOnRecord']['value'])` - crashes if nested keys missing
- New: Try/except with KeyError, TypeError, ValueError handling
- Fallback: Return `None` when data unavailable (don't mislead with 0.0)
- Fix: Remove unnecessary `json.dumps()` - value is already parsed
- Log: "Unable to parse record max from API response"

**`get_station_grid_ref(obj)` (lines 59-62):**
- Current: `json.dumps(obj['items']['gridReference'])` - crashes if keys missing
- New: Try/except with KeyError, TypeError handling
- Fallback: Return `"UNKNOWN"` (string) when data unavailable
- Fix: Remove unnecessary `json.dumps()` - value is already parsed
- Log: "Unable to parse grid reference from API response"

**`get_station_id(obj)` (lines 64-67):**
- Current: `json.dumps(obj['items']['stationReference'])` - crashes if keys missing
- New: Try/except with KeyError, TypeError handling
- Fallback: Return `"UNKNOWN"` (string) when data unavailable
- Fix: Remove unnecessary `json.dumps()` - value is already parsed
- Log: "Unable to parse station ID from API response"

#### 1.2 Improved error handling pattern:
```python
def get_height(obj):
    """Function takes api output from EA API and returns river level as float or None."""
    if obj is None:
        return None
    try:
        return float(obj['items']['latestReading']['value'])
    except (KeyError, TypeError, ValueError) as e:
        logger.warning(f"Unable to parse river height from API response: {e}")
        return None  # Return None instead of 0.0 to avoid misleading metrics
```

#### 1.3 Exception types to handle:
- **KeyError**: When expected JSON keys are missing
- **TypeError**: When obj is None or wrong type
- **ValueError**: When conversion to float fails
- **requests.exceptions.ConnectionError**: Network connection failures
- **requests.exceptions.Timeout**: Request timeout errors
- **requests.exceptions.RequestException**: General request errors

#### 1.4 Improved fallback strategy - return None instead of misleading values:
- **Numeric values**: Return `None` instead of `0.0` to avoid misleading metrics
- **String values**: Return `None` for missing data, handle gracefully in calling code
- **Maintains type consistency**: Functions return expected types or None
- **Prevents misleading metrics**: Don't update Prometheus gauges with fake zero values

#### 1.5 Testing approach for step 1:
- Test each function with `None` input
- Test with empty dictionary `{}`
- Test with partial data (missing nested keys)
- Test with wrong data types (strings where numbers expected)
- Verify fallback values are returned and logged appropriately

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