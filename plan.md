# Slovak Weather Station Data Fetcher - Implementation Plan

## Project Overview
A robust Python application to fetch real-time weather data from Slovak Automatic Weather Stations (SHMU) and transform it into an extended OpenWeatherMap-compatible JSON format with additional meteorological variables.

## Architecture Decision: Python
- **Primary Choice**: Python 3.12 (latest stable)
- **Rationale**:
  - Excellent JSON/HTTP handling
  - Rich datetime manipulation libraries
  - Simple async support for parallel station fetching
  - Familiar to the team
- **Key Dependencies**:
  - `requests` or `httpx` (async HTTP)
  - `python-dateutil` (timezone handling)
  - `pydantic` (data validation)

## Project Structure
```
imeteo-stations/
├── src/
│   ├── main.py                 # Entry point & CLI
│   ├── fetcher.py              # Data fetching with retry logic
│   ├── stations.py             # Station metadata & mappings
│   ├── transformer.py          # Data transformation engine
│   ├── weather_codes.py        # Weather condition mappings
│   ├── models.py               # Pydantic models for validation
│   └── utils/
│       ├── time_handler.py     # Timezone & time calculations
│       └── url_builder.py      # Dynamic URL generation
├── config/
│   ├── stations.json           # Station database
│   └── weather_mappings.json  # Weather code translations
├── tests/
│   ├── test_fetcher.py
│   ├── test_transformer.py
│   └── fixtures/
│       └── sample_data.json
├── requirements.txt
├── README.md
├── .env.example
└── .gitignore
```

## Enhanced Data Schema (Extended OpenWeatherMap Format)

### Standard OpenWeatherMap Fields
```json
{
  "coord": {
    "lon": 17.2,
    "lat": 48.171667
  },
  "weather": [{
    "id": 803,
    "main": "Clouds",
    "description": "broken clouds",
    "icon": "04d"
  }],
  "base": "stations",
  "main": {
    "temp": 6.32,
    "feels_like": 5.4,
    "temp_min": 5.43,
    "temp_max": 6.84,
    "pressure": 1036,
    "humidity": 59,
    "sea_level": 1036,
    "grnd_level": 1013,
    "temp_kf": null
  },
  "visibility": 10000,
  "wind": {
    "speed": 1.54,
    "deg": 50,
    "gust": 3.2
  },
  "clouds": {
    "all": 75
  },
  "rain": {
    "5m": 0.5,
    "1h_estimated": 6.0
  },
  "snow": {
    "1h": 0.0
  },
  "dt": 1738850283,
  "sys": {
    "type": 2,
    "id": 2044188,
    "country": "SK",
    "sunrise": 1738822365,
    "sunset": 1738857514
  },
  "timezone": 3600,
  "id": 11816,
  "name": "Bratislava - letisko",
  "cod": 200
}
```

### Extended Meteorological Fields
```json
{
  "extended": {
    "station": {
      "id": "11816",
      "elevation": 133,
      "type": "automatic",
      "last_update": "2025-09-16T18:35:00Z"
    },
    "atmosphere": {
      "dew_point": 2.1,
      "vapor_pressure": 7.2,
      "saturation_deficit": 2.8,
      "absolute_humidity": 5.4
    },
    "wind_detailed": {
      "speed_min": 0.5,
      "speed_max": 4.2,
      "speed_avg_scalar": 1.54,
      "speed_avg_vector": 1.45,
      "direction_at_max": 45,
      "direction_variability": 15,
      "beaufort_scale": 1,
      "wind_chill": 4.8
    },
    "radiation": {
      "global": 125.3,
      "uv_index": 0,
      "solar_elevation": 15.2,
      "gamma": 85.2
    },
    "precipitation": {
      "duration_seconds_5m": 120,
      "intensity": "light",
      "type": "rain",
      "accumulation_5m": 0.5,
      "accumulation_1h_estimated": 6.0,
      "note": "1h and 24h values require multiple file fetches"
    },
    "soil": {
      "temperatures": {
        "5cm": 5.8,
        "10cm": 6.2,
        "20cm": 7.1,
        "50cm": 8.3,
        "100cm": 9.5
      },
      "moisture": {
        "10cm": 28.5,
        "20cm": 31.2,
        "50cm": 33.8
      },
      "conductivity": {
        "10cm": 0.12,
        "20cm": 0.15,
        "50cm": 0.18
      }
    },
    "surface": {
      "ground_temp": 4.2,
      "snow_depth": 0.0,
      "ice_thickness": null,
      "surface_condition": "wet"
    },
    "sunshine": {
      "duration_seconds": 180,
      "percentage": 5
    },
    "phenomena": {
      "fog": false,
      "mist": true,
      "thunderstorm": false,
      "hail": false
    },
    "quality": {
      "completeness": 0.95,
      "sensors_active": 28,
      "sensors_total": 30,
      "missing_fields": ["ice_thickness", "uv_sensor"]
    }
  }
}
```

## Robust File Fetching Strategy

### Primary Approach: Smart Latest File Discovery
```python
class SmartFetcher:
    """
    Intelligent file fetcher that handles multiple scenarios:
    1. Try current 5-minute window
    2. Fall back to previous windows (up to 15 minutes)
    3. Cache successful patterns
    4. Learn from failures
    """

    def fetch_latest(self):
        strategies = [
            self.try_current_window,      # Expected latest
            self.try_previous_window,      # 5 minutes ago
            self.try_window_cascade,       # Up to 15 min back
            self.try_cached_pattern,       # Last known good
            self.discover_available        # Probe for any recent
        ]

        for strategy in strategies:
            result = strategy()
            if result:
                return result

        raise DataUnavailableError()
```

### File Availability Handling

#### Time Window Calculation
```python
def calculate_time_windows(now_utc):
    """
    Generate list of possible file timestamps
    accounting for CEST/CET and publication delays
    """
    cest_now = now_utc + timedelta(hours=2)  # Summer time
    cet_now = now_utc + timedelta(hours=1)   # Winter time

    windows = []
    for tz_now in [cest_now, cet_now]:
        # Round down to 5-minute interval
        minute = (tz_now.minute // 5) * 5
        window = tz_now.replace(minute=minute, second=0)

        # Generate cascade: 0, -5, -10, -15 minutes
        for offset in range(0, 20, 5):
            windows.append(window - timedelta(minutes=offset))

    return windows
```

#### URL Pattern Generation
```python
def build_urls(timestamp):
    """
    Generate multiple URL patterns for robustness
    """
    base = "https://opendata.shmu.sk/meteorology/climate/now/data"
    date_str = timestamp.strftime("%Y%m%d")
    time_str = timestamp.strftime("%Y-%m-%d %H-%M-%S")

    patterns = [
        f"{base}/{date_str}/aws1min - {time_str}-000.json",
        f"{base}/{date_str}/aws1min - {time_str}-264.json",
        f"{base}/{date_str}/aws1min-{time_str}.json",
    ]

    return patterns
```

### Fallback Mechanisms

1. **Retry with Exponential Backoff**
   ```python
   @retry(stop=stop_after_attempt(3),
          wait=wait_exponential(multiplier=1, min=2, max=10))
   def fetch_with_retry(url):
       response = requests.get(url, timeout=30)
       response.raise_for_status()
       return response.json()
   ```

2. **Parallel URL Testing**
   ```python
   async def fetch_first_available(urls):
       async with httpx.AsyncClient() as client:
           tasks = [client.get(url) for url in urls]
           for coro in asyncio.as_completed(tasks):
               try:
                   response = await coro
                   if response.status_code == 200:
                       return response.json()
               except:
                   continue
   ```

3. **Cache Last Known Good**
   ```python
   class URLCache:
       def __init__(self):
           self.last_good_pattern = None
           self.last_fetch_time = None

       def update(self, url, timestamp):
           self.last_good_pattern = self.extract_pattern(url)
           self.last_fetch_time = timestamp
   ```

## Data Aggregation & Selection Strategy

### CRITICAL: Working with 1-minute data within 5-minute files

Each JSON file contains **5 minutes of 1-minute resolution data** for each station. The aggregation strategy must:

1. **Stay within single file boundaries** - Never aggregate across multiple JSON files
2. **Select appropriate minute** - Choose the most recent or most representative minute
3. **Handle accumulative vs instantaneous** - Different strategies for different measurements

#### Data Selection Strategies

```python
class DataSelector:
    """
    Handles selection of appropriate data points from 5-minute window
    Each file contains exactly 5 measurements per station (one per minute)
    """

    def select_from_window(self, station_data: List[dict], measurement_type: str):
        """
        Select appropriate value based on measurement type
        station_data: List of 5 minute records for one station
        """
        if not station_data:
            return None

        # Sort by timestamp to ensure proper ordering
        sorted_data = sorted(station_data, key=lambda x: x['minuta'])

        if measurement_type == 'instantaneous':
            # For temp, pressure, humidity: use LAST (most recent) minute
            return sorted_data[-1]

        elif measurement_type == 'accumulative':
            # For precipitation, sunshine: SUM all 5 minutes
            return self.sum_accumulative(sorted_data)

        elif measurement_type == 'wind':
            # For wind: calculate vector average or use last minute
            return self.process_wind(sorted_data)

        elif measurement_type == 'extreme':
            # For min/max values: scan all 5 minutes
            return self.find_extremes(sorted_data)
```

#### Aggregation Rules by Parameter Type

```python
AGGREGATION_RULES = {
    # Instantaneous measurements - use LAST minute (most recent)
    't': 'last',                    # Air temperature
    'tprz': 'last',                 # Ground temperature
    'tlak': 'last',                 # Pressure
    'vlh_rel': 'last',              # Relative humidity
    'dohl': 'last',                 # Visibility
    'sneh_pokr': 'last',            # Snow depth
    't_pod*': 'last',               # Soil temperatures
    'vlh_pod*': 'last',             # Soil moisture
    'el_vod_pod*': 'last',          # Soil conductivity

    # Accumulative measurements - SUM all 5 minutes
    'zra_uhrn': 'sum',              # Precipitation amount
    'zra_trv': 'sum',               # Precipitation duration (seconds)
    'sln_trv': 'sum',               # Sunshine duration (seconds)

    # Average measurements - MEAN of 5 minutes
    'zglo': 'mean',                 # Global radiation
    'zgama': 'mean',                # Gamma radiation

    # Wind - special handling
    'vie_pr_rych': 'last',          # Scalar average wind speed (use last)
    'vie_vp_rych': 'vector_avg',   # Vector average (recalculate)
    'vie_min_rych': 'min',          # Minimum across 5 minutes
    'vie_max_rych': 'max',          # Maximum across 5 minutes
    'vie_pr_smer': 'circular_avg',  # Circular average for direction

    # Weather state - use LAST or MOST FREQUENT
    'stav_poc': 'last_or_mode',    # Weather condition code
}
```

#### Implementation Examples

```python
def process_station_data(json_data: dict, station_id: str) -> dict:
    """
    Process data for a single station from one 5-minute JSON file
    """
    # Filter data for specific station
    station_records = [
        record for record in json_data['data']
        if record['ind_kli'] == station_id
    ]

    if len(station_records) != 5:
        logger.warning(f"Expected 5 records for station {station_id}, got {len(station_records)}")

    # Sort by timestamp
    station_records.sort(key=lambda x: x['minuta'])

    # Get the last (most recent) record for instantaneous values
    latest_record = station_records[-1] if station_records else {}

    # Calculate aggregates that need all 5 minutes
    result = {
        # Instantaneous (from last minute)
        'temp': latest_record.get('t'),
        'pressure': latest_record.get('tlak'),
        'humidity': latest_record.get('vlh_rel'),

        # Accumulative (sum of 5 minutes)
        'rain_5min': sum(r.get('zra_uhrn', 0) for r in station_records),
        'sunshine_seconds': sum(r.get('sln_trv', 0) for r in station_records),

        # Extremes (across 5 minutes)
        'temp_min': min((r.get('t', float('inf')) for r in station_records if r.get('t') is not None), default=None),
        'temp_max': max((r.get('t', float('-inf')) for r in station_records if r.get('t') is not None), default=None),

        # Wind (complex handling)
        'wind_speed': latest_record.get('vie_pr_rych'),
        'wind_gust': max((r.get('vie_max_rych', 0) for r in station_records), default=None),

        # Timestamp of measurement
        'measurement_time': latest_record.get('minuta'),
        'data_window': f"{station_records[0].get('minuta')} to {station_records[-1].get('minuta')}"
    }

    return result
```

#### Important Considerations for Aggregations

1. **Precipitation Handling**
   - `zra_uhrn` is already per minute, so sum for 5-minute total
   - For hourly rate: would need to fetch 12 consecutive files (error-prone!)
   - Solution: Report 5-minute accumulation and extrapolate carefully

2. **Wind Vector Averaging**
   ```python
   def vector_average_wind(records):
       """Calculate true vector average for wind"""
       u_components = []
       v_components = []

       for record in records:
           speed = record.get('vie_vp_rych', 0)
           direction = record.get('vie_vp_smer', 0)

           # Convert to u,v components
           u = -speed * math.sin(math.radians(direction))
           v = -speed * math.cos(math.radians(direction))

           u_components.append(u)
           v_components.append(v)

       # Average components
       avg_u = sum(u_components) / len(u_components)
       avg_v = sum(v_components) / len(v_components)

       # Convert back to speed and direction
       avg_speed = math.sqrt(avg_u**2 + avg_v**2)
       avg_dir = math.degrees(math.atan2(-avg_u, -avg_v)) % 360

       return avg_speed, avg_dir
   ```

3. **Data Quality Flags**
   ```python
   def assess_data_quality(station_records):
       """Assess quality of 5-minute window"""
       return {
           'complete': len(station_records) == 5,
           'minutes_available': len(station_records),
           'has_gaps': not all(
               (records[i+1]['minuta'] - records[i]['minuta']).seconds == 60
               for i in range(len(records)-1)
           ),
           'null_percentage': calculate_null_percentage(station_records)
       }
   ```

## Data Transformation Logic

### Core Transformations

#### Temperature & Feels Like
```python
def calculate_feels_like(temp, wind_speed, humidity):
    """
    Wind chill for cold, heat index for warm conditions
    """
    if temp <= 10 and wind_speed > 1.3:
        # Wind chill formula
        return 13.12 + 0.6215 * temp - 11.37 * (wind_speed * 3.6) ** 0.16 + \
               0.3965 * temp * (wind_speed * 3.6) ** 0.16
    elif temp >= 27:
        # Heat index simplified
        return temp + 0.5 * (humidity - 40)
    return temp
```

#### Cloud Coverage Estimation
```python
def estimate_cloud_cover(radiation, max_possible, weather_code):
    """
    Estimate cloud coverage from multiple sources
    """
    if radiation and max_possible:
        # Based on solar radiation
        ratio = radiation / max_possible
        return int((1 - ratio) * 100)
    elif weather_code:
        # Based on weather code mappings
        return WEATHER_CODE_TO_CLOUDS.get(weather_code, 50)
    else:
        # Default assumption
        return None
```

#### Weather Condition Mapping
```python
WEATHER_CONDITIONS = {
    # Clear
    0: {"id": 800, "main": "Clear", "description": "clear sky", "icon": "01"},

    # Clouds
    1: {"id": 801, "main": "Clouds", "description": "few clouds", "icon": "02"},
    2: {"id": 802, "main": "Clouds", "description": "scattered clouds", "icon": "03"},
    3: {"id": 803, "main": "Clouds", "description": "broken clouds", "icon": "04"},
    4: {"id": 804, "main": "Clouds", "description": "overcast clouds", "icon": "04"},

    # Fog/Mist
    5: {"id": 701, "main": "Mist", "description": "mist", "icon": "50"},
    6: {"id": 741, "main": "Fog", "description": "fog", "icon": "50"},

    # Precipitation
    10: {"id": 500, "main": "Rain", "description": "light rain", "icon": "10"},
    11: {"id": 501, "main": "Rain", "description": "moderate rain", "icon": "10"},
    12: {"id": 502, "main": "Rain", "description": "heavy rain", "icon": "10"},

    # Snow
    20: {"id": 600, "main": "Snow", "description": "light snow", "icon": "13"},
    21: {"id": 601, "main": "Snow", "description": "snow", "icon": "13"},

    # Thunderstorm
    30: {"id": 200, "main": "Thunderstorm", "description": "thunderstorm", "icon": "11"}
}
```

### Advanced Calculations

#### Atmospheric Calculations
```python
def calculate_atmospheric_properties(temp, humidity, pressure):
    """
    Calculate dew point, vapor pressure, absolute humidity
    """
    # Magnus formula for dew point
    a, b = 17.27, 237.7
    alpha = ((a * temp) / (b + temp)) + math.log(humidity / 100)
    dew_point = (b * alpha) / (a - alpha)

    # Vapor pressure (hPa)
    vapor_pressure = 6.112 * math.exp((17.67 * dew_point) / (dew_point + 243.5))

    # Absolute humidity (g/m³)
    absolute_humidity = (vapor_pressure * 100) / (461.5 * (temp + 273.15))

    return {
        "dew_point": round(dew_point, 1),
        "vapor_pressure": round(vapor_pressure, 1),
        "absolute_humidity": round(absolute_humidity, 1)
    }
```

## CLI Interface

```bash
# Fetch single station
python -m imeteo_stations --station "Bratislava - letisko"

# Fetch by coordinates (nearest station)
python -m imeteo_stations --lat 48.17 --lon 17.20

# Fetch multiple stations
python -m imeteo_stations --stations "Bratislava,Košice,Žilina"

# Fetch all stations
python -m imeteo_stations --all

# Output options
python -m imeteo_stations --station "Bratislava" --output weather.json
python -m imeteo_stations --station "Bratislava" --format extended

# Continuous mode (updates every 5 minutes)
python -m imeteo_stations --station "Bratislava" --continuous

# Debug mode (verbose logging)
python -m imeteo_stations --station "Bratislava" --debug
```

## Error Handling & Monitoring

### Comprehensive Error Types
```python
class WeatherFetchError(Exception): pass
class DataUnavailableError(WeatherFetchError): pass
class StationNotFoundError(WeatherFetchError): pass
class TransformationError(WeatherFetchError): pass
class TimeoutError(WeatherFetchError): pass
```

### Logging Strategy
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('weather_fetch.log'),
        logging.StreamHandler()
    ]
)
```

### Health Monitoring
```python
class HealthMonitor:
    def __init__(self):
        self.last_successful_fetch = None
        self.consecutive_failures = 0
        self.sensor_availability = {}

    def check_health(self):
        return {
            "status": "healthy" if self.consecutive_failures < 3 else "degraded",
            "last_success": self.last_successful_fetch,
            "failures": self.consecutive_failures,
            "sensor_status": self.sensor_availability
        }
```

## Performance Optimizations

1. **Concurrent Station Fetching**
   ```python
   async def fetch_all_stations(station_ids):
       async with httpx.AsyncClient() as client:
           tasks = [fetch_station(client, sid) for sid in station_ids]
           return await asyncio.gather(*tasks, return_exceptions=True)
   ```

2. **Response Caching**
   - Cache successful responses for 4 minutes
   - Serve from cache if fresh fetch fails

3. **Connection Pooling**
   - Reuse HTTP connections
   - Configure appropriate timeouts

## Testing Strategy

### Unit Tests
- Time calculation accuracy
- URL generation patterns
- Data transformation correctness
- Error handling paths

### Integration Tests
- Live API connectivity
- Full data pipeline
- Multiple station scenarios

### Load Testing
- Concurrent requests handling
- Memory usage under load
- Cache effectiveness

## Deployment Considerations

### Docker Support
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "imeteo_stations", "--continuous"]
```

### Environment Variables
```env
SHMU_BASE_URL=https://opendata.shmu.sk
FETCH_TIMEOUT=30
RETRY_ATTEMPTS=3
LOG_LEVEL=INFO
CACHE_TTL=240
```

## Future Enhancements

1. **Historical Data Support**
   - Fetch and store historical measurements
   - Trend analysis capabilities

2. **Alerting System**
   - Configurable weather alerts
   - Email/webhook notifications

3. **Data Persistence**
   - TimescaleDB for time-series storage
   - InfluxDB integration

4. **API Server Mode**
   - FastAPI wrapper for REST access
   - WebSocket for real-time updates

5. **Machine Learning**
   - Short-term forecasting from patterns
   - Anomaly detection for sensor issues

## Success Criteria

- ✅ Fetches latest available data reliably
- ✅ Handles all time zone complexities
- ✅ Gracefully manages missing data
- ✅ Transforms to OpenWeatherMap format
- ✅ Includes extended meteorological data
- ✅ Supports multiple stations
- ✅ Provides robust error handling
- ✅ Logs operations for debugging
- ✅ Performs efficiently under load