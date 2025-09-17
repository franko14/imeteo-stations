"""Tests for data transformation and aggregation."""

import pytest
import math
from datetime import datetime

from src.transformer import (
    DataAggregator, WeatherTransformer, AggregationStrategy,
    AGGREGATION_RULES, WEATHER_CODE_MAPPING, TransformationError
)


class TestDataAggregator:
    """Test data aggregation logic."""

    def create_sample_records(self, station_id: str = "11816") -> list:
        """Create sample 5-minute records for testing."""
        return [
            {
                "ind_kli": station_id,
                "minuta": "2025-09-16T18:30:00",
                "t": 15.5,
                "tlak": 1015.2,
                "vlh_rel": 65.0,
                "zra_uhrn": 0.0,
                "vie_pr_rych": 2.1,
                "vie_pr_smer": 180.0,
                "vie_max_rych": 3.2,
            },
            {
                "ind_kli": station_id,
                "minuta": "2025-09-16T18:31:00",
                "t": 15.6,
                "tlak": 1015.1,
                "vlh_rel": 64.8,
                "zra_uhrn": 0.1,
                "vie_pr_rych": 2.3,
                "vie_pr_smer": 185.0,
                "vie_max_rych": 3.5,
            },
            {
                "ind_kli": station_id,
                "minuta": "2025-09-16T18:32:00",
                "t": 15.4,
                "tlak": 1015.0,
                "vlh_rel": 65.2,
                "zra_uhrn": 0.2,
                "vie_pr_rych": 1.9,
                "vie_pr_smer": 175.0,
                "vie_max_rych": 2.8,
            },
            {
                "ind_kli": station_id,
                "minuta": "2025-09-16T18:33:00",
                "t": 15.7,
                "tlak": 1014.9,
                "vlh_rel": 64.5,
                "zra_uhrn": 0.0,
                "vie_pr_rych": 2.5,
                "vie_pr_smer": 190.0,
                "vie_max_rych": 3.8,
            },
            {
                "ind_kli": station_id,
                "minuta": "2025-09-16T18:34:00",
                "t": 15.8,  # This should be the "last" value
                "tlak": 1014.8,
                "vlh_rel": 64.0,
                "zra_uhrn": 0.1,
                "vie_pr_rych": 2.0,
                "vie_pr_smer": 182.0,
                "vie_max_rych": 3.0,
            }
        ]

    def test_aggregate_field_last_strategy(self):
        """Test LAST aggregation strategy (most recent value)."""
        aggregator = DataAggregator()
        records = self.create_sample_records()

        # Temperature should use LAST strategy
        result = aggregator.aggregate_field(records, 't')
        assert result == 15.8  # Last value in the series

        # Pressure should also use LAST
        result = aggregator.aggregate_field(records, 'tlak')
        assert result == 1014.8

    def test_aggregate_field_sum_strategy(self):
        """Test SUM aggregation strategy."""
        aggregator = DataAggregator()
        records = self.create_sample_records()

        # Precipitation should use SUM strategy
        result = aggregator.aggregate_field(records, 'zra_uhrn')
        expected = 0.0 + 0.1 + 0.2 + 0.0 + 0.1  # = 0.4
        assert result == expected

    def test_aggregate_field_max_strategy(self):
        """Test MAX aggregation strategy."""
        aggregator = DataAggregator()
        records = self.create_sample_records()

        # Max wind speed should use MAX strategy
        result = aggregator.aggregate_field(records, 'vie_max_rych')
        assert result == 3.8  # Maximum value in the series

    def test_aggregate_field_mean_strategy(self):
        """Test MEAN aggregation strategy."""
        aggregator = DataAggregator()

        # Create records with a field that uses MEAN (like radiation)
        records = [
            {"zglo": 200.0, "minuta": "2025-09-16T18:30:00"},
            {"zglo": 250.0, "minuta": "2025-09-16T18:31:00"},
            {"zglo": 300.0, "minuta": "2025-09-16T18:32:00"},
            {"zglo": 220.0, "minuta": "2025-09-16T18:33:00"},
            {"zglo": 280.0, "minuta": "2025-09-16T18:34:00"},
        ]

        result = aggregator.aggregate_field(records, 'zglo')
        expected = (200.0 + 250.0 + 300.0 + 220.0 + 280.0) / 5  # = 250.0
        assert result == expected

    def test_aggregate_field_with_missing_values(self):
        """Test aggregation with None/missing values."""
        aggregator = DataAggregator()

        records = [
            {"t": 15.5, "minuta": "2025-09-16T18:30:00"},
            {"t": None, "minuta": "2025-09-16T18:31:00"},  # Missing value
            {"t": 15.7, "minuta": "2025-09-16T18:32:00"},
            {"minuta": "2025-09-16T18:33:00"},  # Missing field entirely
            {"t": 15.8, "minuta": "2025-09-16T18:34:00"},
        ]

        result = aggregator.aggregate_field(records, 't')
        assert result == 15.8  # Should ignore None values and use last valid

    def test_aggregate_field_all_missing(self):
        """Test aggregation when all values are missing."""
        aggregator = DataAggregator()

        records = [
            {"minuta": "2025-09-16T18:30:00"},
            {"t": None, "minuta": "2025-09-16T18:31:00"},
            {"minuta": "2025-09-16T18:32:00"},
        ]

        result = aggregator.aggregate_field(records, 't')
        assert result is None

    def test_aggregate_field_empty_records(self):
        """Test aggregation with empty records list."""
        aggregator = DataAggregator()

        result = aggregator.aggregate_field([], 't')
        assert result is None

    def test_vector_average_direction(self):
        """Test vector averaging for wind direction."""
        aggregator = DataAggregator()

        # Test with consistent wind directions around 0°/360°
        records = [
            {"vie_pr_smer": 350.0, "vie_pr_rych": 5.0},
            {"vie_pr_smer": 10.0, "vie_pr_rych": 5.0},
            {"vie_pr_smer": 0.0, "vie_pr_rych": 5.0},
            {"vie_pr_smer": 5.0, "vie_pr_rych": 5.0},
            {"vie_pr_smer": 355.0, "vie_pr_rych": 5.0},
        ]

        result = aggregator._vector_average_direction(records, 'vie_pr_smer')

        # Should be close to 0° (or 360°)
        assert result is not None
        assert 0 <= result <= 360
        # Allow some tolerance for floating point calculations
        assert result < 15 or result > 345

    def test_aggregation_rules_completeness(self):
        """Test that aggregation rules cover expected fields."""
        expected_fields = [
            't', 'tlak', 'vlh_rel', 'zra_uhrn', 'vie_pr_rych', 'vie_max_rych'
        ]

        for field in expected_fields:
            assert field in AGGREGATION_RULES, f"Missing aggregation rule for {field}"

    def test_aggregation_strategies_valid(self):
        """Test that all aggregation strategies are valid."""
        valid_strategies = set(AggregationStrategy)

        for field, strategy in AGGREGATION_RULES.items():
            assert strategy in valid_strategies, f"Invalid strategy for {field}: {strategy}"


class TestWeatherTransformer:
    """Test weather data transformation."""

    def create_sample_json_data(self) -> dict:
        """Create sample JSON data from SHMU API."""
        return {
            "id": "test-uuid",
            "dataset": "Automatic stations",
            "interval": "1 minute",
            "frequency": "5 minute",
            "statistics": {
                "stations_count": 1,
                "records_count": 5
            },
            "data": [
                {
                    "ind_kli": "11816",
                    "minuta": "2025-09-16T18:30:00",
                    "t": 15.5,
                    "tlak": 1015.2,
                    "vlh_rel": 65.0,
                    "zra_uhrn": 0.0,
                    "vie_pr_rych": 2.1,
                    "vie_pr_smer": 180.0,
                    "stav_poc": 3,  # Broken clouds
                },
                {
                    "ind_kli": "11816",
                    "minuta": "2025-09-16T18:31:00",
                    "t": 15.6,
                    "tlak": 1015.1,
                    "vlh_rel": 64.8,
                    "zra_uhrn": 0.1,
                    "vie_pr_rych": 2.3,
                    "vie_pr_smer": 185.0,
                    "stav_poc": 3,
                },
                {
                    "ind_kli": "11816",
                    "minuta": "2025-09-16T18:32:00",
                    "t": 15.4,
                    "tlak": 1015.0,
                    "vlh_rel": 65.2,
                    "zra_uhrn": 0.2,
                    "vie_pr_rych": 1.9,
                    "vie_pr_smer": 175.0,
                    "stav_poc": 3,
                },
                {
                    "ind_kli": "11816",
                    "minuta": "2025-09-16T18:33:00",
                    "t": 15.7,
                    "tlak": 1014.9,
                    "vlh_rel": 64.5,
                    "zra_uhrn": 0.0,
                    "vie_pr_rych": 2.5,
                    "vie_pr_smer": 190.0,
                    "stav_poc": 3,
                },
                {
                    "ind_kli": "11816",
                    "minuta": "2025-09-16T18:34:00",
                    "t": 15.8,
                    "tlak": 1014.8,
                    "vlh_rel": 64.0,
                    "zra_uhrn": 0.1,
                    "vie_pr_rych": 2.0,
                    "vie_pr_smer": 182.0,
                    "stav_poc": 3,
                }
            ]
        }

    def test_process_station_data_basic(self):
        """Test basic station data processing."""
        transformer = WeatherTransformer()
        json_data = self.create_sample_json_data()

        result = transformer.process_station_data(json_data, "11816")

        assert isinstance(result, dict)
        assert result['station_id'] == "11816"
        assert result['record_count'] == 5

        # Check that aggregation happened correctly
        assert result['t'] == 15.8  # Last temperature
        assert result['zra_uhrn'] == 0.4  # Sum of precipitation (0.0+0.1+0.2+0.0+0.1)

    def test_process_station_data_station_not_found(self):
        """Test error when station not in data."""
        transformer = WeatherTransformer()
        json_data = self.create_sample_json_data()

        with pytest.raises(TransformationError):
            transformer.process_station_data(json_data, "99999")

    def test_process_station_data_incomplete_records(self):
        """Test handling of incomplete record sets."""
        transformer = WeatherTransformer()
        json_data = self.create_sample_json_data()

        # Remove some records to simulate incomplete data
        json_data['data'] = json_data['data'][:3]  # Only 3 records instead of 5

        result = transformer.process_station_data(json_data, "11816")

        assert result['record_count'] == 3
        # Should still work with available data

    def test_transform_to_openweather_structure(self):
        """Test complete transformation to OpenWeatherMap format."""
        transformer = WeatherTransformer()
        json_data = self.create_sample_json_data()

        result = transformer.transform_to_openweather(json_data, "11816")

        # Check required OpenWeatherMap fields
        required_fields = ['coord', 'weather', 'main', 'dt', 'sys', 'id', 'name', 'cod']
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

        # Check coordinate structure
        assert 'lat' in result['coord']
        assert 'lon' in result['coord']
        assert isinstance(result['coord']['lat'], float)
        assert isinstance(result['coord']['lon'], float)

        # Check weather array
        assert isinstance(result['weather'], list)
        assert len(result['weather']) > 0

        # Check main weather data
        main = result['main']
        assert 'temp' in main
        assert 'pressure' in main
        assert 'humidity' in main
        assert main['temp'] == 15.8  # Last temperature

    def test_transform_to_openweather_with_precipitation(self):
        """Test transformation with precipitation data."""
        transformer = WeatherTransformer()
        json_data = self.create_sample_json_data()

        result = transformer.transform_to_openweather(json_data, "11816")

        # Should have rain data since we have precipitation
        assert 'rain' in result
        assert '5m' in result['rain']
        assert result['rain']['5m'] == 0.4  # Sum of 5-minute precipitation

    def test_feels_like_calculation(self):
        """Test feels-like temperature calculation."""
        transformer = WeatherTransformer()

        # Test normal conditions (no wind chill or heat index)
        feels_like = transformer._calculate_feels_like(20.0, 1.0, 50.0)
        assert feels_like == 20.0

        # Test wind chill conditions (cold + wind)
        feels_like = transformer._calculate_feels_like(5.0, 5.0, 60.0)
        assert feels_like < 5.0  # Should feel colder

        # Test heat index conditions (hot + humid)
        feels_like = transformer._calculate_feels_like(30.0, 1.0, 80.0)
        assert feels_like > 30.0  # Should feel hotter

    def test_dew_point_calculation(self):
        """Test dew point calculation."""
        transformer = WeatherTransformer()

        # Test with known values
        dew_point = transformer._calculate_dew_point(20.0, 60.0)
        assert isinstance(dew_point, float)
        assert 0 <= dew_point <= 20.0  # Dew point should be below temperature

        # Test with 100% humidity (dew point should equal temperature)
        dew_point = transformer._calculate_dew_point(15.0, 100.0)
        assert abs(dew_point - 15.0) < 0.5  # Should be very close

    def test_cloud_coverage_estimation(self):
        """Test cloud coverage estimation from radiation."""
        transformer = WeatherTransformer()

        # High radiation = clear skies
        clouds = transformer._estimate_cloud_coverage(900.0)
        assert clouds == 0

        # Low radiation = overcast
        clouds = transformer._estimate_cloud_coverage(100.0)
        assert clouds == 100

        # Medium radiation = partial clouds
        clouds = transformer._estimate_cloud_coverage(500.0)
        assert 0 < clouds < 100

    def test_weather_condition_mapping(self):
        """Test weather condition code mapping."""
        transformer = WeatherTransformer()

        # Test with sample data that has weather code 3 (broken clouds)
        json_data = self.create_sample_json_data()
        result = transformer.transform_to_openweather(json_data, "11816")

        weather = result['weather'][0]
        assert weather['id'] == 803  # OpenWeatherMap code for broken clouds
        assert weather['main'] == "Clouds"
        assert "clouds" in weather['description'].lower()

    def test_wind_data_transformation(self):
        """Test wind data transformation."""
        transformer = WeatherTransformer()
        json_data = self.create_sample_json_data()

        result = transformer.transform_to_openweather(json_data, "11816")

        # Should have wind data
        assert 'wind' in result
        wind = result['wind']

        assert 'speed' in wind
        assert isinstance(wind['speed'], (int, float))

        assert 'deg' in wind
        assert 0 <= wind['deg'] <= 360

    def test_timestamp_correction(self):
        """Test that timestamps are properly corrected from Slovak to UTC."""
        transformer = WeatherTransformer()
        json_data = self.create_sample_json_data()

        result = transformer.transform_to_openweather(json_data, "11816")

        # Check that dt is a valid Unix timestamp
        assert isinstance(result['dt'], int)
        assert result['dt'] > 0

        # Convert back to check it's reasonable
        dt = datetime.fromtimestamp(result['dt'])
        assert dt.year == 2025
        assert dt.month == 9
        assert dt.day == 16

    def test_station_not_found_in_database(self):
        """Test error when station ID not in station database."""
        transformer = WeatherTransformer()
        json_data = self.create_sample_json_data()

        # Try to transform data for invalid station
        with pytest.raises(TransformationError):
            transformer.transform_to_openweather(json_data, "99999")


class TestWeatherCodeMapping:
    """Test weather code mapping functionality."""

    def test_weather_code_mapping_completeness(self):
        """Test that weather code mapping has reasonable coverage."""
        # Should have mappings for common conditions
        common_codes = [0, 1, 2, 3, 4, 10, 11, 20, 21, 30]

        for code in common_codes:
            if code in WEATHER_CODE_MAPPING:
                mapping = WEATHER_CODE_MAPPING[code]
                assert 'id' in mapping
                assert 'main' in mapping
                assert 'description' in mapping
                assert 'icon' in mapping

    def test_weather_code_structure(self):
        """Test structure of weather code mappings."""
        for code, mapping in WEATHER_CODE_MAPPING.items():
            assert isinstance(code, int)
            assert isinstance(mapping, dict)

            # Check required fields
            assert isinstance(mapping['id'], int)
            assert isinstance(mapping['main'], str)
            assert isinstance(mapping['description'], str)
            assert isinstance(mapping['icon'], str)

            # Check OpenWeatherMap ID ranges
            assert 200 <= mapping['id'] <= 999

    def test_weather_code_consistency(self):
        """Test consistency of weather code mappings."""
        for code, mapping in WEATHER_CODE_MAPPING.items():
            main = mapping['main']
            description = mapping['description']

            # Description should be related to main category
            if main == "Clear":
                assert "clear" in description.lower()
            elif main == "Clouds":
                assert "cloud" in description.lower()
            elif main == "Rain":
                assert "rain" in description.lower()
            elif main == "Snow":
                assert "snow" in description.lower() or "sleet" in description.lower()
            elif main == "Thunderstorm":
                assert "thunder" in description.lower()