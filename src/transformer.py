"""
Data aggregation and transformation to OpenWeatherMap format.

CRITICAL: This module handles the most important constraint:
Each JSON file contains exactly 5 minutes of 1-minute resolution data per station.
Aggregation MUST stay within single file boundaries.
"""

import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from pydantic import BaseModel
import logging

from .time_utils import fix_data_timestamp, utc_to_slovak_time
from .stations import StationInfo, get_station_by_id

logger = logging.getLogger(__name__)


class AggregationStrategy(Enum):
    """Aggregation strategies for different measurement types."""
    LAST = "last"          # Use most recent value (instantaneous measurements)
    SUM = "sum"            # Sum all values (accumulative measurements)
    MEAN = "mean"          # Average all values
    MIN = "min"            # Minimum value
    MAX = "max"            # Maximum value
    VECTOR_AVG = "vector"  # Vector average (for wind direction)


class WeatherCondition(BaseModel):
    """OpenWeatherMap weather condition."""
    id: int
    main: str
    description: str
    icon: str


class TransformationError(Exception):
    """Error during data transformation."""
    pass


# Aggregation rules for different measurements
# Based on CLAUDE.md aggregation table
AGGREGATION_RULES = {
    # Instantaneous measurements - use LAST (most recent minute)
    't': AggregationStrategy.LAST,                    # Air temperature
    'tprz': AggregationStrategy.LAST,                 # Ground temperature
    'tlak': AggregationStrategy.LAST,                 # Pressure
    'vlh_rel': AggregationStrategy.LAST,              # Relative humidity
    'dohl': AggregationStrategy.LAST,                 # Visibility
    'sneh_pokr': AggregationStrategy.LAST,            # Snow depth
    't_pod5': AggregationStrategy.LAST,               # Soil temp 5cm
    't_pod10': AggregationStrategy.LAST,              # Soil temp 10cm
    't_pod20': AggregationStrategy.LAST,              # Soil temp 20cm
    't_pod50': AggregationStrategy.LAST,              # Soil temp 50cm
    't_pod100': AggregationStrategy.LAST,             # Soil temp 100cm
    'vlh_pod10': AggregationStrategy.LAST,            # Soil moisture 10cm
    'vlh_pod20': AggregationStrategy.LAST,            # Soil moisture 20cm
    'vlh_pod50': AggregationStrategy.LAST,            # Soil moisture 50cm
    'el_vod_pod10': AggregationStrategy.LAST,         # Soil conductivity 10cm
    'el_vod_pod20': AggregationStrategy.LAST,         # Soil conductivity 20cm
    'el_vod_pod50': AggregationStrategy.LAST,         # Soil conductivity 50cm

    # Accumulative measurements - SUM all 5 minutes
    'zra_uhrn': AggregationStrategy.SUM,              # Precipitation amount
    'zra_trv': AggregationStrategy.SUM,               # Precipitation duration
    'sln_trv': AggregationStrategy.SUM,               # Sunshine duration

    # Average measurements - MEAN of 5 minutes
    'zglo': AggregationStrategy.MEAN,                 # Global radiation
    'zgama': AggregationStrategy.MEAN,                # Gamma radiation

    # Wind measurements - special handling
    'vie_pr_rych': AggregationStrategy.LAST,          # Average wind speed
    'vie_vp_rych': AggregationStrategy.VECTOR_AVG,    # Vector wind speed
    'vie_min_rych': AggregationStrategy.MIN,          # Min wind speed
    'vie_max_rych': AggregationStrategy.MAX,          # Max wind speed
    'vie_pr_smer': AggregationStrategy.VECTOR_AVG,    # Average wind direction
    'vie_vp_smer': AggregationStrategy.VECTOR_AVG,    # Vector wind direction
    'vie_smer_min': AggregationStrategy.LAST,         # Direction at min speed
    'vie_smer_max': AggregationStrategy.LAST,         # Direction at max speed

    # Weather condition - use last or most frequent
    'stav_poc': AggregationStrategy.LAST,             # Weather condition code
}


# Slovak weather codes to OpenWeatherMap mapping
WEATHER_CODE_MAPPING = {
    # Clear conditions
    0: {"id": 800, "main": "Clear", "description": "clear sky", "icon": "01"},
    1: {"id": 801, "main": "Clouds", "description": "few clouds", "icon": "02"},

    # Cloudy conditions
    2: {"id": 802, "main": "Clouds", "description": "scattered clouds", "icon": "03"},
    3: {"id": 803, "main": "Clouds", "description": "broken clouds", "icon": "04"},
    4: {"id": 804, "main": "Clouds", "description": "overcast clouds", "icon": "04"},

    # Fog and mist
    5: {"id": 701, "main": "Mist", "description": "mist", "icon": "50"},
    6: {"id": 741, "main": "Fog", "description": "fog", "icon": "50"},
    7: {"id": 741, "main": "Fog", "description": "thick fog", "icon": "50"},

    # Precipitation
    10: {"id": 500, "main": "Rain", "description": "light rain", "icon": "10"},
    11: {"id": 501, "main": "Rain", "description": "moderate rain", "icon": "10"},
    12: {"id": 502, "main": "Rain", "description": "heavy rain", "icon": "10"},
    13: {"id": 511, "main": "Rain", "description": "freezing rain", "icon": "13"},

    # Snow
    20: {"id": 600, "main": "Snow", "description": "light snow", "icon": "13"},
    21: {"id": 601, "main": "Snow", "description": "snow", "icon": "13"},
    22: {"id": 602, "main": "Snow", "description": "heavy snow", "icon": "13"},
    23: {"id": 611, "main": "Snow", "description": "sleet", "icon": "13"},

    # Thunderstorms
    30: {"id": 200, "main": "Thunderstorm", "description": "thunderstorm with light rain", "icon": "11"},
    31: {"id": 201, "main": "Thunderstorm", "description": "thunderstorm with rain", "icon": "11"},
    32: {"id": 202, "main": "Thunderstorm", "description": "thunderstorm with heavy rain", "icon": "11"},

    # Severe weather
    40: {"id": 781, "main": "Tornado", "description": "tornado", "icon": "50"},
    41: {"id": 771, "main": "Squall", "description": "squalls", "icon": "50"},
}


class DataAggregator:
    """Aggregates 1-minute data within 5-minute boundaries."""

    def aggregate_field(self, records: List[Dict[str, Any]], field: str) -> Optional[float]:
        """
        Aggregate a specific field from station records.

        CRITICAL: Records must be from the same 5-minute window only!

        Args:
            records: List of 5 station records (1-minute each)
            field: Field name to aggregate

        Returns:
            Aggregated value or None if no valid data
        """
        if not records:
            return None

        strategy = AGGREGATION_RULES.get(field, AggregationStrategy.LAST)
        values = [r.get(field) for r in records if r.get(field) is not None]

        if not values:
            return None

        if strategy == AggregationStrategy.LAST:
            # Most recent value (records should be sorted by time)
            return values[-1]

        elif strategy == AggregationStrategy.SUM:
            return sum(values)

        elif strategy == AggregationStrategy.MEAN:
            return sum(values) / len(values)

        elif strategy == AggregationStrategy.MIN:
            return min(values)

        elif strategy == AggregationStrategy.MAX:
            return max(values)

        elif strategy == AggregationStrategy.VECTOR_AVG:
            # Special handling for wind direction
            if field in ['vie_pr_smer', 'vie_vp_smer']:
                return self._vector_average_direction(records, field)
            else:
                return values[-1]  # Fallback to last

        else:
            logger.warning(f"Unknown aggregation strategy for {field}: {strategy}")
            return values[-1]  # Fallback to last

    def _vector_average_direction(self, records: List[Dict[str, Any]], direction_field: str) -> Optional[float]:
        """
        Calculate vector average for wind direction.

        Args:
            records: Station records
            direction_field: Direction field name

        Returns:
            Vector-averaged direction in degrees
        """
        # Get corresponding speed field
        if direction_field == 'vie_pr_smer':
            speed_field = 'vie_pr_rych'
        elif direction_field == 'vie_vp_smer':
            speed_field = 'vie_vp_rych'
        else:
            speed_field = 'vie_pr_rych'  # Default

        u_sum = 0.0
        v_sum = 0.0
        count = 0

        for record in records:
            direction = record.get(direction_field)
            speed = record.get(speed_field, 0)

            if direction is not None and speed is not None and speed > 0:
                # Convert to radians and calculate components
                dir_rad = math.radians(direction)
                u_sum += speed * math.sin(dir_rad)
                v_sum += speed * math.cos(dir_rad)
                count += 1

        if count == 0:
            return None

        # Calculate average direction
        avg_direction = math.degrees(math.atan2(u_sum, v_sum))

        # Normalize to 0-360 degrees
        if avg_direction < 0:
            avg_direction += 360

        return avg_direction


class WeatherTransformer:
    """Transforms Slovak weather data to OpenWeatherMap format."""

    def __init__(self):
        self.aggregator = DataAggregator()

    def process_station_data(self, json_data: Dict[str, Any], station_id: str) -> Dict[str, Any]:
        """
        Process data for a single station from 5-minute JSON file.

        CRITICAL: This method enforces the 5-minute boundary constraint.

        Args:
            json_data: Complete JSON data from SHMU
            station_id: Target station ID

        Returns:
            Aggregated data for the station
        """
        # Filter records for this station only
        all_station_records = [
            record for record in json_data.get('data', [])
            if str(record.get('ind_kli')) == str(station_id)
        ]

        if not all_station_records:
            raise TransformationError(f"No data found for station {station_id}")

        # Sort by timestamp to ensure proper ordering
        all_station_records.sort(key=lambda x: x.get('minuta', ''))

        # CRITICAL: Enforce 5-minute boundary constraint
        # Find the most recent complete 5-minute window
        station_records = self._get_latest_5min_window(all_station_records)

        if not station_records:
            raise TransformationError(f"No complete 5-minute window found for station {station_id}")

        if len(station_records) != 5:
            logger.warning(
                f"Expected 5 records for station {station_id}, got {len(station_records)}. "
                "Using available records within the latest 5-minute boundary."
            )

        # Log the time window for debugging
        if station_records:
            first_time = station_records[0].get('minuta', 'unknown')
            last_time = station_records[-1].get('minuta', 'unknown')
            logger.debug(f"Processing station {station_id} data from {first_time} to {last_time}")

        result = self._aggregate_station_records(station_records)

        # Add min/max calculations for temperature and wind gust
        result.update(self._calculate_minmax_values(station_records))

        return result

    def _calculate_minmax_values(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate min/max values from the 5-minute window.

        Args:
            records: Station records from 5-minute window

        Returns:
            Dictionary with min/max values
        """
        if not records:
            return {}

        result = {}

        # Temperature min/max
        temps = [r.get('t') for r in records if r.get('t') is not None]
        if temps:
            result['temp_min'] = min(temps)
            result['temp_max'] = max(temps)

        # Wind gust maximum
        wind_gusts = [r.get('vie_max_rych') for r in records if r.get('vie_max_rych') is not None]
        if wind_gusts:
            result['wind_gust_max'] = max(wind_gusts)

        return result

    def _get_latest_5min_window(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract the latest complete 5-minute window from station records.

        CRITICAL: This enforces the 5-minute boundary constraint.

        Args:
            records: Sorted station records

        Returns:
            Records from the latest complete 5-minute window
        """
        if not records:
            return []

        from datetime import datetime

        # Group records by 5-minute windows
        windows = {}

        for record in records:
            timestamp_str = record.get('minuta', '')
            if not timestamp_str:
                continue

            try:
                # Parse timestamp
                dt = datetime.fromisoformat(timestamp_str.replace('Z', ''))

                # Calculate 5-minute window start (round down to nearest 5-minute boundary)
                window_minute = (dt.minute // 5) * 5
                window_start = dt.replace(minute=window_minute, second=0, microsecond=0)
                window_key = window_start.isoformat()

                if window_key not in windows:
                    windows[window_key] = []
                windows[window_key].append(record)

            except (ValueError, AttributeError):
                logger.warning(f"Invalid timestamp format: {timestamp_str}")
                continue

        if not windows:
            return []

        # Find the latest window with complete data (5 records)
        latest_window_key = max(windows.keys())
        latest_window_records = windows[latest_window_key]

        # If the latest window doesn't have 5 records, try the previous one
        if len(latest_window_records) < 5 and len(windows) > 1:
            sorted_windows = sorted(windows.keys(), reverse=True)
            for window_key in sorted_windows[1:]:  # Skip the latest, try previous ones
                if len(windows[window_key]) == 5:
                    return windows[window_key]

        # Return the latest window even if incomplete
        return latest_window_records

    def _aggregate_station_records(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate station records according to measurement types.

        Args:
            records: List of 5 station records

        Returns:
            Aggregated measurements
        """
        result = {}

        # Get the most recent record for metadata
        latest_record = records[-1] if records else {}

        # Aggregate all known fields
        for field in AGGREGATION_RULES:
            value = self.aggregator.aggregate_field(records, field)
            if value is not None:
                result[field] = value

        # Add metadata
        result['record_count'] = len(records)
        result['latest_timestamp'] = latest_record.get('minuta')
        result['station_id'] = latest_record.get('ind_kli')

        # Calculate derived values
        result.update(self._calculate_derived_values(result))

        return result

    def _calculate_derived_values(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate derived meteorological values.

        Args:
            data: Aggregated station data

        Returns:
            Dictionary with derived values
        """
        derived = {}

        # Calculate feels-like temperature
        temp = data.get('t')
        wind_speed = data.get('vie_pr_rych', 0)
        humidity = data.get('vlh_rel')

        if temp is not None:
            derived['feels_like'] = self._calculate_feels_like(temp, wind_speed, humidity)

        # Calculate dew point
        if temp is not None and humidity is not None:
            derived['dew_point'] = self._calculate_dew_point(temp, humidity)

        # Calculate cloud coverage from radiation if available
        radiation = data.get('zglo')
        if radiation is not None:
            derived['cloud_coverage'] = self._estimate_cloud_coverage(radiation)

        return derived

    def _calculate_feels_like(self, temp: float, wind_speed: float, humidity: Optional[float]) -> float:
        """
        Calculate feels-like temperature.

        Args:
            temp: Air temperature in Celsius
            wind_speed: Wind speed in m/s
            humidity: Relative humidity in %

        Returns:
            Feels-like temperature in Celsius
        """
        # Wind chill for cold conditions
        if temp <= 10 and wind_speed > 1.3:
            # Convert wind speed to km/h for formula
            wind_kmh = wind_speed * 3.6
            feels_like = (13.12 + 0.6215 * temp -
                         11.37 * (wind_kmh ** 0.16) +
                         0.3965 * temp * (wind_kmh ** 0.16))
            return round(feels_like, 1)

        # Heat index for warm conditions
        elif temp >= 27 and humidity is not None:
            # Simplified heat index
            feels_like = temp + 0.5 * (humidity - 40) / 100 * (temp - 27)
            return round(feels_like, 1)

        # No significant wind chill or heat index
        return temp

    def _calculate_dew_point(self, temp: float, humidity: float) -> float:
        """
        Calculate dew point using Magnus formula.

        Args:
            temp: Temperature in Celsius
            humidity: Relative humidity in %

        Returns:
            Dew point in Celsius
        """
        # Magnus formula constants
        a = 17.27
        b = 237.7

        alpha = ((a * temp) / (b + temp)) + math.log(humidity / 100.0)
        dew_point = (b * alpha) / (a - alpha)

        return round(dew_point, 1)

    def _estimate_cloud_coverage(self, radiation: float) -> int:
        """
        Estimate cloud coverage from global radiation.

        Args:
            radiation: Global radiation in W/m²

        Returns:
            Cloud coverage percentage (0-100)
        """
        # Very rough estimation - would need solar angle calculation for accuracy
        # This is a simplified approach
        if radiation > 800:
            return 0   # Clear
        elif radiation > 600:
            return 25  # Few clouds
        elif radiation > 400:
            return 50  # Scattered clouds
        elif radiation > 200:
            return 75  # Broken clouds
        else:
            return 100 # Overcast

    def transform_to_openweather(self, json_data: Dict[str, Any], station_id: str) -> Dict[str, Any]:
        """
        Transform Slovak weather data to OpenWeatherMap format.

        Args:
            json_data: Raw JSON data from SHMU
            station_id: Station ID to process

        Returns:
            OpenWeatherMap-compatible JSON
        """
        # Get station information
        try:
            station_info = get_station_by_id(station_id)
        except Exception as e:
            raise TransformationError(f"Station {station_id} not found: {e}")

        # Process and aggregate station data
        processed_data = self.process_station_data(json_data, station_id)

        # Fix timestamp (Slovak data is UTC+1, need true UTC)
        latest_timestamp = processed_data.get('latest_timestamp')
        if latest_timestamp:
            dt_utc = fix_data_timestamp(latest_timestamp)
            unix_timestamp = int(dt_utc.timestamp())
            dt_slovak = utc_to_slovak_time(dt_utc)
        else:
            dt_utc = datetime.utcnow()
            unix_timestamp = int(dt_utc.timestamp())
            dt_slovak = utc_to_slovak_time(dt_utc)

        # Build OpenWeatherMap structure
        result = {
            "coord": {
                "lon": station_info.longitude,
                "lat": station_info.latitude
            },
            "weather": self._get_weather_conditions(processed_data),
            "base": "stations",
            "main": self._build_main_section(processed_data),
            "visibility": self._get_visibility(processed_data),
            "wind": self._build_wind_section(processed_data),
            "clouds": self._build_clouds_section(processed_data),
            "dt": unix_timestamp,
            "sys": {
                "type": 2,
                "id": int(station_id),
                "country": "SK",
                "sunrise": self._calculate_sunrise(station_info.latitude, station_info.longitude),
                "sunset": self._calculate_sunset(station_info.latitude, station_info.longitude),
            },
            "timezone": 3600,  # Slovakia is UTC+1 (CET) base
            "id": int(station_id),
            "name": station_info.name,
            "cod": 200,
            "timestamps": {
                "utc": dt_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "bratislava": dt_slovak.strftime("%Y-%m-%d %H:%M:%S") + " CET/CEST"
            }
        }

        # Add precipitation if present
        rain_5min = processed_data.get('zra_uhrn', 0)
        if rain_5min and rain_5min > 0:
            result["rain"] = {
                "5m": round(rain_5min, 1),
                "1h_estimated": round(rain_5min * 12, 1)  # Extrapolate carefully
            }

        # Add snow if present
        snow_depth = processed_data.get('sneh_pokr')
        if snow_depth and snow_depth > 0:
            result["snow"] = {
                "depth": round(snow_depth, 1)
            }

        return result

    def _get_weather_conditions(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get weather condition array."""
        weather_code = data.get('stav_poc')

        if weather_code in WEATHER_CODE_MAPPING:
            condition = WEATHER_CODE_MAPPING[weather_code].copy()

            # Adjust icon for day/night (simplified)
            if condition["icon"].endswith("d") or condition["icon"].endswith("n"):
                # Keep as is - would need solar calculations for proper day/night
                pass
            else:
                condition["icon"] += "d"  # Default to day

            return [condition]
        else:
            # Default condition based on other data
            clouds = data.get('cloud_coverage', 50)
            if clouds < 25:
                return [{"id": 800, "main": "Clear", "description": "clear sky", "icon": "01d"}]
            elif clouds < 75:
                return [{"id": 803, "main": "Clouds", "description": "broken clouds", "icon": "04d"}]
            else:
                return [{"id": 804, "main": "Clouds", "description": "overcast clouds", "icon": "04d"}]

    def _build_main_section(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build main weather data section."""
        temp = data.get('t')
        pressure = data.get('tlak')
        humidity = data.get('vlh_rel')
        feels_like = data.get('feels_like', temp)

        main = {}

        if temp is not None:
            main["temp"] = round(temp, 1)
            main["feels_like"] = round(feels_like, 1) if feels_like else round(temp, 1)

            # Use actual min/max from 5-minute window
            temp_min = data.get('temp_min', temp)
            temp_max = data.get('temp_max', temp)
            main["temp_min"] = round(temp_min, 1)
            main["temp_max"] = round(temp_max, 1)

        if pressure is not None:
            main["pressure"] = int(round(pressure))
            main["sea_level"] = int(round(pressure))  # Approximate
            main["grnd_level"] = int(round(pressure))

        if humidity is not None:
            main["humidity"] = int(round(humidity))

        return main

    def _get_visibility(self, data: Dict[str, Any]) -> Optional[int]:
        """Get visibility in meters."""
        visibility = data.get('dohl')
        if visibility is not None:
            # Cap at 10000m as per OpenWeatherMap spec
            return min(int(visibility), 10000)
        return None

    def _build_wind_section(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Build wind data section."""
        wind_speed = data.get('vie_pr_rych')
        wind_dir = data.get('vie_pr_smer')
        # Use maximum gust from 5-minute window
        wind_gust_max = data.get('wind_gust_max', data.get('vie_max_rych'))

        if wind_speed is None:
            return None

        wind = {
            "speed": round(wind_speed, 1)
        }

        if wind_dir is not None:
            wind["deg"] = int(round(wind_dir))

        if wind_gust_max is not None and wind_gust_max > wind_speed:
            wind["gust"] = round(wind_gust_max, 1)

        return wind

    def _build_clouds_section(self, data: Dict[str, Any]) -> Dict[str, int]:
        """Build clouds data section."""
        cloud_coverage = data.get('cloud_coverage', 50)
        return {"all": int(cloud_coverage)}

    def _calculate_sunrise(self, lat: float, lon: float) -> int:
        """Calculate approximate sunrise time (placeholder)."""
        # This is a simplified calculation - proper implementation would need
        # astronomical calculations based on date and location
        base_time = datetime.utcnow().replace(hour=6, minute=0, second=0, microsecond=0)
        return int(base_time.timestamp())

    def _calculate_sunset(self, lat: float, lon: float) -> int:
        """Calculate approximate sunset time (placeholder)."""
        # This is a simplified calculation - proper implementation would need
        # astronomical calculations based on date and location
        base_time = datetime.utcnow().replace(hour=18, minute=0, second=0, microsecond=0)
        return int(base_time.timestamp())