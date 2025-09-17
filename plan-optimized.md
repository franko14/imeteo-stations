# Slovak Weather Station Data Fetcher - Implementation Guide

## CRITICAL CONSTRAINTS (READ FIRST!)

### Data Structure Reality Check
- **Each JSON file = 5 minutes of data** (5 separate 1-minute records per station)
- **NEVER aggregate across files** - Stay within single file boundaries
- **Files published with ~2-3 minute delay** after the 5-minute window ends
- **URL format is strict**: `aws1min - YYYY-mm-dd HH-MM-SS-000.json`

### Key Gotchas
1. Files may have `-000` or `-264` suffix (try both)
2. Time is in CEST/CET (UTC+2/+1), not UTC
3. Not all stations report all sensors
4. Some values can be null/missing - handle gracefully

---

## STEP 1: Project Setup (Start Here)

### 1.1 Create Project Structure
```bash
mkdir -p src/utils config tests/fixtures
touch src/{__init__.py,main.py,fetcher.py,stations.py,transformer.py,models.py}
touch src/utils/{__init__.py,time_handler.py}
touch config/stations.json
touch requirements.txt .gitignore README.md
```

### 1.2 Install Dependencies
```python
# requirements.txt
httpx==0.27.0
pydantic==2.5.0
python-dateutil==2.8.2
click==8.1.7
tenacity==8.2.3
```

### 1.3 Create Station Database
```json
// config/stations.json
{
  "stations": {
    "11816": {
      "name": "Bratislava - letisko",
      "lat": 48.171667,
      "lon": 17.2,
      "elevation": 133
    },
    "11856": {
      "name": "Piešťany",
      "lat": 48.616667,
      "lon": 17.833333,
      "elevation": 163
    }
    // Add more stations
  }
}
```

---

## STEP 2: Time Handling (Critical for Success)

### 2.1 Implement Time Calculator
```python
# src/utils/time_handler.py
from datetime import datetime, timedelta
import pytz

def get_current_file_window():
    """
    Returns the most likely 5-minute window for current data.
    Account for CEST/CET timezone and publication delay.
    """
    utc_now = datetime.now(pytz.UTC)

    # Convert to Slovak time (handles DST automatically)
    slovak_tz = pytz.timezone('Europe/Bratislava')
    slovak_now = utc_now.astimezone(slovak_tz)

    # Round DOWN to nearest 5-minute interval
    minutes = (slovak_now.minute // 5) * 5
    window_start = slovak_now.replace(minute=minutes, second=0, microsecond=0)

    # Subtract 5 minutes for publication delay (files appear 2-3 min after window ends)
    target_window = window_start - timedelta(minutes=5)

    return target_window

def generate_url_candidates(window_time):
    """
    Generate URLs to try for given time window.
    Returns list of URLs in order of likelihood.
    """
    base = "https://opendata.shmu.sk/meteorology/climate/now/data"
    date_str = window_time.strftime("%Y%m%d")
    time_str = window_time.strftime("%Y-%m-%d %H-%M-%S")

    return [
        f"{base}/{date_str}/aws1min - {time_str}-000.json",  # Most common
        f"{base}/{date_str}/aws1min - {time_str}-264.json",  # Alternative
    ]
```

---

## STEP 3: Fetcher with Retry Logic

### 3.1 Implement Smart Fetcher
```python
# src/fetcher.py
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from datetime import timedelta
from utils.time_handler import get_current_file_window, generate_url_candidates

class DataFetcher:
    def __init__(self):
        self.client = httpx.Client(timeout=30.0)
        self.last_successful_url = None

    def fetch_latest_data(self):
        """
        Main entry point. Tries multiple strategies to get data.
        Returns: dict with JSON data or raises exception.
        """
        # Strategy 1: Try expected current window
        window = get_current_file_window()
        data = self._try_window(window)
        if data:
            return data

        # Strategy 2: Try previous windows (up to 15 min back)
        for minutes_back in [10, 15, 20]:
            window = get_current_file_window() - timedelta(minutes=minutes_back)
            data = self._try_window(window)
            if data:
                return data

        raise Exception("No data available in last 20 minutes")

    def _try_window(self, window_time):
        """Try all URL patterns for a specific time window."""
        urls = generate_url_candidates(window_time)

        for url in urls:
            try:
                response = self.client.get(url)
                if response.status_code == 200:
                    self.last_successful_url = url
                    return response.json()
            except:
                continue
        return None
```

---

## STEP 4: Data Aggregation (CRITICAL LOGIC)

### 4.1 Aggregation Rules Table
```python
# src/transformer.py

# THIS IS THE MOST IMPORTANT PART - AGGREGATION RULES
AGGREGATION_RULES = {
    # Take LAST minute (most recent) for instantaneous values
    't': 'last',              # Temperature
    'tlak': 'last',          # Pressure
    'vlh_rel': 'last',       # Humidity
    't_pod5': 'last',        # Soil temp at 5cm

    # SUM all 5 minutes for accumulative values
    'zra_uhrn': 'sum',       # Rain amount (mm)
    'zra_trv': 'sum',        # Rain duration (seconds)
    'sln_trv': 'sum',        # Sunshine duration (seconds)

    # Take MAX across 5 minutes for extremes
    'vie_max_rych': 'max',   # Wind gust

    # Take AVERAGE for radiation
    'zglo': 'mean',          # Global radiation
}
```

### 4.2 Process Station Data
```python
def process_single_station(json_data, station_id):
    """
    Extract and aggregate data for one station from 5-minute file.

    CRITICAL: json_data contains 5 records per station (1 per minute)
    We must aggregate these 5 records according to rules.
    """
    # Filter records for this station
    station_records = [r for r in json_data['data'] if r['ind_kli'] == station_id]

    if not station_records:
        return None

    # Sort by timestamp (safety measure)
    station_records.sort(key=lambda x: x['minuta'])

    # Get the LAST record for instantaneous values
    last_record = station_records[-1]

    result = {
        # Instantaneous values from LAST minute
        'temperature': last_record.get('t'),
        'pressure': last_record.get('tlak'),
        'humidity': last_record.get('vlh_rel'),

        # Accumulated values - SUM all 5 records
        'rain_5min': sum(r.get('zra_uhrn', 0) for r in station_records),
        'sunshine_seconds': sum(r.get('sln_trv', 0) for r in station_records),

        # Max values - scan all 5 records
        'wind_gust': max((r.get('vie_max_rych', 0) for r in station_records), default=None),

        # Metadata
        'timestamp': last_record.get('minuta'),
        'station_id': station_id
    }

    return result
```

---

## STEP 5: Transform to OpenWeatherMap Format

### 5.1 Basic Transformation
```python
def to_openweathermap_format(station_data, station_meta):
    """
    Convert aggregated station data to OpenWeatherMap JSON structure.
    """
    # Handle None values gracefully
    temp = station_data.get('temperature')
    humidity = station_data.get('humidity')
    pressure = station_data.get('pressure')

    return {
        "coord": {
            "lat": station_meta['lat'],
            "lon": station_meta['lon']
        },
        "main": {
            "temp": temp,
            "pressure": pressure,
            "humidity": humidity,
            "feels_like": calculate_feels_like(temp, station_data.get('wind_speed', 0), humidity)
        },
        "wind": {
            "speed": station_data.get('wind_speed'),
            "deg": station_data.get('wind_direction'),
            "gust": station_data.get('wind_gust')
        },
        "rain": {
            "5m": station_data.get('rain_5min', 0),
            "1h_estimated": station_data.get('rain_5min', 0) * 12  # Rough estimate
        },
        "dt": int(station_data['timestamp'].timestamp()),
        "name": station_meta['name'],
        "id": station_meta['id']
    }
```

### 5.2 Extended Fields
```python
def add_extended_fields(base_json, station_data):
    """Add Slovak-specific extended meteorological data."""
    base_json['extended'] = {
        "soil": {
            "temperatures": {
                "5cm": station_data.get('t_pod5'),
                "10cm": station_data.get('t_pod10'),
                "20cm": station_data.get('t_pod20')
            }
        },
        "radiation": {
            "global": station_data.get('zglo'),
            "gamma": station_data.get('zgama')
        },
        "precipitation": {
            "duration_seconds_5m": station_data.get('rain_duration'),
            "accumulation_5m": station_data.get('rain_5min')
        },
        "sunshine": {
            "duration_seconds": station_data.get('sunshine_seconds')
        }
    }
    return base_json
```

---

## STEP 6: Main Application Entry

### 6.1 CLI Implementation
```python
# src/main.py
import click
import json
from fetcher import DataFetcher
from transformer import process_single_station, to_openweathermap_format
from stations import load_stations

@click.command()
@click.option('--station', help='Station name or ID')
@click.option('--output', default=None, help='Output file (default: stdout)')
@click.option('--debug', is_flag=True, help='Enable debug logging')
def main(station, output, debug):
    """Fetch Slovak weather station data in OpenWeatherMap format."""

    # Load station metadata
    stations = load_stations()

    if not station:
        click.echo("Error: --station required", err=True)
        return 1

    # Find station
    station_meta = find_station(stations, station)
    if not station_meta:
        click.echo(f"Station '{station}' not found", err=True)
        return 1

    try:
        # Fetch latest data
        fetcher = DataFetcher()
        raw_data = fetcher.fetch_latest_data()

        # Process for requested station
        station_data = process_single_station(raw_data, station_meta['id'])

        if not station_data:
            click.echo(f"No data for station {station}", err=True)
            return 1

        # Transform to OpenWeatherMap format
        result = to_openweathermap_format(station_data, station_meta)

        # Output
        json_str = json.dumps(result, indent=2)
        if output:
            with open(output, 'w') as f:
                f.write(json_str)
        else:
            click.echo(json_str)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if debug:
            import traceback
            traceback.print_exc()
        return 1

    return 0

if __name__ == '__main__':
    exit(main())
```

---

## STEP 7: Testing Strategy

### 7.1 Critical Test Cases
```python
# tests/test_aggregation.py

def test_aggregation_rules():
    """Test that aggregation follows the rules correctly."""

    # Mock 5 minutes of data
    mock_data = {
        "data": [
            {"ind_kli": "11816", "minuta": "2025-01-01 12:00:00", "t": 10.0, "zra_uhrn": 0.1},
            {"ind_kli": "11816", "minuta": "2025-01-01 12:01:00", "t": 10.1, "zra_uhrn": 0.2},
            {"ind_kli": "11816", "minuta": "2025-01-01 12:02:00", "t": 10.2, "zra_uhrn": 0.1},
            {"ind_kli": "11816", "minuta": "2025-01-01 12:03:00", "t": 10.3, "zra_uhrn": 0.3},
            {"ind_kli": "11816", "minuta": "2025-01-01 12:04:00", "t": 10.5, "zra_uhrn": 0.1},
        ]
    }

    result = process_single_station(mock_data, "11816")

    # Temperature should be LAST value
    assert result['temperature'] == 10.5

    # Rain should be SUM of all 5
    assert result['rain_5min'] == 0.8  # 0.1+0.2+0.1+0.3+0.1

def test_missing_data_handling():
    """Test graceful handling of missing values."""
    mock_data = {
        "data": [
            {"ind_kli": "11816", "minuta": "2025-01-01 12:00:00", "t": None},
        ]
    }

    result = process_single_station(mock_data, "11816")
    assert result['temperature'] is None  # Should not crash
```

---

## Implementation Order

1. **Start with time handling** (Step 2) - This is the trickiest part
2. **Build fetcher** (Step 3) - Test with real URLs early
3. **Implement aggregation** (Step 4) - This is the core logic
4. **Add transformation** (Step 5) - Can start simple, add fields gradually
5. **Wire up CLI** (Step 6) - Makes testing easier
6. **Add tests** (Step 7) - Especially for aggregation logic

## Common Pitfalls to Avoid

1. **DO NOT** try to fetch multiple files for hourly data - stick to 5-min windows
2. **DO NOT** assume files are in UTC - they use Slovak time
3. **DO NOT** aggregate across file boundaries - each file is independent
4. **ALWAYS** handle None/null values - not all sensors report all the time
5. **ALWAYS** sort records by timestamp before processing
6. **REMEMBER** precipitation is already per-minute, so SUM for totals

## Quick Validation

To verify your implementation:
1. Fetch a file manually: Check if URL works in browser
2. Count records: Should be ~5 per station in each file
3. Check timestamps: Records should be 1 minute apart
4. Verify aggregation: Temperature last, rain summed, etc.