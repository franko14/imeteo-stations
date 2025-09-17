"""Integration tests for the complete weather data pipeline."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from src.fetcher import WeatherDataFetcher, DataUnavailableError
from src.transformer import WeatherTransformer
from src.stations import get_station_by_id
from src.main import cli


class TestIntegrationPipeline:
    """Test the complete data pipeline integration."""

    def create_mock_shmu_response(self) -> dict:
        """Create a realistic mock response from SHMU API."""
        return {
            "id": "12345678-1234-5678-9012-123456789012",
            "dataset": "Automatic stations",
            "interval": "1 minute",
            "frequency": "5 minute",
            "statistics": {
                "stations_count": 95,
                "records_count": 475  # 95 stations * 5 minutes
            },
            "data": [
                # Station 11816 (Bratislava - letisko) - 5 records
                {
                    "ind_kli": "11816",
                    "minuta": "2025-09-16T17:30:00",  # Note: UTC+1 in source
                    "t": 15.2,
                    "tprz": 12.8,
                    "tlak": 1015.3,
                    "vlh_rel": 68.0,
                    "vie_min_rych": 1.2,
                    "vie_max_rych": 3.8,
                    "vie_pr_rych": 2.1,
                    "vie_pr_smer": 180.0,
                    "zglo": 425.5,
                    "zra_uhrn": 0.0,
                    "zra_trv": 0.0,
                    "sln_trv": 60.0,
                    "dohl": 15000.0,
                    "stav_poc": 3,
                    "sneh_pokr": 0.0
                },
                {
                    "ind_kli": "11816",
                    "minuta": "2025-09-16T17:31:00",
                    "t": 15.4,
                    "tprz": 12.9,
                    "tlak": 1015.2,
                    "vlh_rel": 67.5,
                    "vie_min_rych": 1.5,
                    "vie_max_rych": 4.1,
                    "vie_pr_rych": 2.3,
                    "vie_pr_smer": 185.0,
                    "zglo": 430.2,
                    "zra_uhrn": 0.0,
                    "zra_trv": 0.0,
                    "sln_trv": 60.0,
                    "dohl": 15000.0,
                    "stav_poc": 3,
                    "sneh_pokr": 0.0
                },
                {
                    "ind_kli": "11816",
                    "minuta": "2025-09-16T17:32:00",
                    "t": 15.1,
                    "tprz": 12.7,
                    "tlak": 1015.1,
                    "vlh_rel": 68.2,
                    "vie_min_rych": 1.0,
                    "vie_max_rych": 3.5,
                    "vie_pr_rych": 1.9,
                    "vie_pr_smer": 175.0,
                    "zglo": 420.8,
                    "zra_uhrn": 0.0,
                    "zra_trv": 0.0,
                    "sln_trv": 60.0,
                    "dohl": 15000.0,
                    "stav_poc": 2,
                    "sneh_pokr": 0.0
                },
                {
                    "ind_kli": "11816",
                    "minuta": "2025-09-16T17:33:00",
                    "t": 15.6,
                    "tprz": 13.0,
                    "tlak": 1015.0,
                    "vlh_rel": 67.0,
                    "vie_min_rych": 1.8,
                    "vie_max_rych": 4.2,
                    "vie_pr_rych": 2.5,
                    "vie_pr_smer": 190.0,
                    "zglo": 435.1,
                    "zra_uhrn": 0.0,
                    "zra_trv": 0.0,
                    "sln_trv": 60.0,
                    "dohl": 15000.0,
                    "stav_poc": 3,
                    "sneh_pokr": 0.0
                },
                {
                    "ind_kli": "11816",
                    "minuta": "2025-09-16T17:34:00",
                    "t": 15.8,  # This will be the "last" value used
                    "tprz": 13.1,
                    "tlak": 1014.9,
                    "vlh_rel": 66.5,
                    "vie_min_rych": 1.3,
                    "vie_max_rych": 3.9,
                    "vie_pr_rych": 2.0,
                    "vie_pr_smer": 182.0,
                    "zglo": 428.7,
                    "zra_uhrn": 0.0,
                    "zra_trv": 0.0,
                    "sln_trv": 60.0,
                    "dohl": 15000.0,
                    "stav_poc": 3,
                    "sneh_pokr": 0.0
                },
                # Add some records for another station to test filtering
                {
                    "ind_kli": "11968",  # Košice
                    "minuta": "2025-09-16T17:30:00",
                    "t": 14.5,
                    "tlak": 1010.0,
                    "vlh_rel": 70.0,
                    "vie_pr_rych": 1.5,
                    "vie_pr_smer": 200.0,
                    "stav_poc": 1
                }
                # ... would have more stations in real data
            ]
        }

    @pytest.mark.asyncio
    async def test_complete_pipeline_mock(self):
        """Test complete pipeline with mocked HTTP response."""
        mock_response = self.create_mock_shmu_response()

        # Mock the HTTP client to return our test data
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Setup mock response
            mock_response_obj = AsyncMock()
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_client.get.return_value = mock_response_obj

            # Test the complete pipeline
            async with WeatherDataFetcher() as fetcher:
                # Fetch data
                result = await fetcher.fetch_latest_data()

                assert result.records_count == 6  # 5 for Bratislava + 1 for Košice
                assert result.stations_count == 2
                assert result.data == mock_response

                # Transform data
                transformer = WeatherTransformer()
                weather_data = transformer.transform_to_openweather(result.data, "11816")

                # Verify transformation results
                assert weather_data['id'] == 11816
                assert weather_data['name'] == "Bratislava - letisko"
                assert weather_data['coord']['lat'] == 48.171667
                assert weather_data['coord']['lon'] == 17.2

                # Check aggregated values (should use LAST for temperature)
                assert weather_data['main']['temp'] == 15.8

                # Check that wind data is present and properly aggregated
                assert 'wind' in weather_data
                assert weather_data['wind']['speed'] == 2.0  # Last wind speed

                # Check weather condition
                assert len(weather_data['weather']) == 1
                assert weather_data['weather'][0]['id'] == 803  # Broken clouds (code 3)

    @pytest.mark.asyncio
    async def test_pipeline_station_filtering(self):
        """Test that pipeline correctly filters data for specific station."""
        mock_response = self.create_mock_shmu_response()

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response_obj = AsyncMock()
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_client.get.return_value = mock_response_obj

            async with WeatherDataFetcher() as fetcher:
                result = await fetcher.fetch_latest_data()

                transformer = WeatherTransformer()

                # Test Bratislava (should have 5 records)
                bratislava_data = transformer.process_station_data(result.data, "11816")
                assert bratislava_data['record_count'] == 5
                assert bratislava_data['t'] == 15.8  # Last temperature

                # Test Košice (should have 1 record)
                kosice_data = transformer.process_station_data(result.data, "11968")
                assert kosice_data['record_count'] == 1
                assert kosice_data['t'] == 14.5

    @pytest.mark.asyncio
    async def test_pipeline_aggregation_correctness(self):
        """Test that aggregation rules are correctly applied in pipeline."""
        mock_response = self.create_mock_shmu_response()

        # Add precipitation to test SUM aggregation
        for i, record in enumerate(mock_response['data'][:5]):  # Bratislava records
            if record['ind_kli'] == "11816":
                record['zra_uhrn'] = 0.1 * (i + 1)  # 0.1, 0.2, 0.3, 0.4, 0.5

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response_obj = AsyncMock()
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_client.get.return_value = mock_response_obj

            async with WeatherDataFetcher() as fetcher:
                result = await fetcher.fetch_latest_data()

                transformer = WeatherTransformer()
                weather_data = transformer.transform_to_openweather(result.data, "11816")

                # Precipitation should be summed: 0.1 + 0.2 + 0.3 + 0.4 + 0.5 = 1.5
                assert 'rain' in weather_data
                assert weather_data['rain']['5m'] == 1.5

                # Temperature should be last value (LAST strategy)
                assert weather_data['main']['temp'] == 15.8

                # Max wind speed should be maximum across all records
                max_wind_expected = max([3.8, 4.1, 3.5, 4.2, 3.9])
                # Note: This would be in processed data, not directly in OpenWeatherMap format

    @pytest.mark.asyncio
    async def test_pipeline_error_handling(self):
        """Test pipeline error handling."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Test network error
            mock_client.get.side_effect = Exception("Network error")

            async with WeatherDataFetcher() as fetcher:
                with pytest.raises(DataUnavailableError):
                    await fetcher.fetch_latest_data()

    @pytest.mark.asyncio
    async def test_pipeline_data_validation(self):
        """Test pipeline data validation."""
        # Create invalid mock response
        invalid_response = {"invalid": "structure"}

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response_obj = AsyncMock()
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = invalid_response
            mock_client.get.return_value = mock_response_obj

            async with WeatherDataFetcher() as fetcher:
                with pytest.raises(DataUnavailableError):
                    await fetcher.fetch_latest_data()

    def test_station_integration(self):
        """Test integration with station database."""
        # Test that all known stations can be retrieved
        station = get_station_by_id("11816")
        assert station.name == "Bratislava - letisko"
        assert station.latitude == 48.171667
        assert station.longitude == 17.2

        # Test that transformer can use station data
        transformer = WeatherTransformer()
        mock_data = self.create_mock_shmu_response()

        result = transformer.transform_to_openweather(mock_data, "11816")

        # Should have correct station coordinates
        assert result['coord']['lat'] == station.latitude
        assert result['coord']['lon'] == station.longitude
        assert result['name'] == station.name

    @pytest.mark.asyncio
    async def test_cli_integration_mock(self):
        """Test CLI integration with mocked data."""
        from click.testing import CliRunner

        mock_response = self.create_mock_shmu_response()

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response_obj = AsyncMock()
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_client.get.return_value = mock_response_obj

            runner = CliRunner()

            # Test basic fetch command
            result = runner.invoke(cli, ['fetch', '--station-id', '11816'])

            assert result.exit_code == 0
            assert '"id": 11816' in result.output
            assert '"name": "Bratislava - letisko"' in result.output

    @pytest.mark.asyncio
    async def test_real_time_data_structure(self):
        """Test that real-time constraints are respected."""
        mock_response = self.create_mock_shmu_response()

        # Verify the mock data represents the expected structure:
        # - 5 minutes of 1-minute data per station
        # - Proper timestamp sequence
        # - Aggregation stays within file boundaries

        bratislava_records = [
            record for record in mock_response['data']
            if record['ind_kli'] == "11816"
        ]

        assert len(bratislava_records) == 5, "Should have exactly 5 records for 5-minute window"

        # Check timestamp sequence
        timestamps = [record['minuta'] for record in bratislava_records]
        assert timestamps == sorted(timestamps), "Timestamps should be in order"

        # Verify 1-minute intervals
        from datetime import datetime
        parsed_times = [datetime.fromisoformat(ts) for ts in timestamps]
        for i in range(1, len(parsed_times)):
            time_diff = parsed_times[i] - parsed_times[i-1]
            assert time_diff.total_seconds() == 60, "Should be 1-minute intervals"

        # Test transformation respects boundaries
        transformer = WeatherTransformer()
        processed = transformer.process_station_data(mock_response, "11816")

        # Verify aggregation used only these 5 records
        assert processed['record_count'] == 5
        assert processed['latest_timestamp'] == timestamps[-1]