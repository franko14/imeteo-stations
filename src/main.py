"""
CLI entry point for iMeteo.sk weather station data fetcher.

This script provides a command-line interface to fetch Slovak weather station data
and transform it to OpenWeatherMap-compatible format.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional

import click
from pydantic import ValidationError

from .fetcher import WeatherDataFetcher, DataUnavailableError, NetworkError
from .transformer import WeatherTransformer, TransformationError
from .stations import (
    get_station_by_id, get_station_by_name, get_nearest_station,
    search_stations, stations_db, StationNotFoundError
)


def setup_logging(debug: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stderr)
        ]
    )

    # Reduce httpx logging noise
    logging.getLogger("httpx").setLevel(logging.WARNING)


def format_output(data: dict, format_type: str = "json", compact: bool = False) -> str:
    """Format output data."""
    if format_type == "json":
        if compact:
            return json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        else:
            return json.dumps(data, indent=2, ensure_ascii=False)
    else:
        # Could add other formats like YAML, CSV, etc.
        return json.dumps(data, indent=2, ensure_ascii=False)


@click.group(invoke_without_command=True)
@click.option('--debug', is_flag=True, help='Enable debug logging')
@click.option('--version', is_flag=True, help='Show version and exit')
@click.pass_context
def cli(ctx, debug: bool, version: bool):
    """iMeteo.sk Slovak weather station data fetcher."""
    setup_logging(debug)

    if version:
        click.echo("imeteo-stations 1.0.0")
        click.echo("Slovak weather station data fetcher for iMeteo.sk")
        ctx.exit()

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
@click.option('--station', help='Station name (partial matches allowed)')
@click.option('--station-id', help='Station ID (e.g., "11816")')
@click.option('--lat', type=float, help='Latitude for nearest station lookup')
@click.option('--lon', type=float, help='Longitude for nearest station lookup')
@click.option('--format', 'output_format', default='json', type=click.Choice(['json']),
              help='Output format')
@click.option('--output', '-o', type=click.Path(), help='Output file (default: stdout)')
@click.option('--compact', is_flag=True, help='Compact JSON output')
@click.option('--timeout', default=30.0, help='Request timeout in seconds')
def fetch(station: Optional[str], station_id: Optional[str],
          lat: Optional[float], lon: Optional[float],
          output_format: str, output: Optional[str], compact: bool,
          timeout: float):
    """Fetch current weather data for a station."""

    async def _fetch():
        try:
            # Determine target station
            if station_id:
                target_station = get_station_by_id(station_id)
                target_id = station_id
            elif station:
                target_station = get_station_by_name(station)
                target_id = target_station.id
            elif lat is not None and lon is not None:
                target_station = get_nearest_station(lat, lon)
                target_id = target_station.id
            else:
                click.echo("Error: Must specify --station, --station-id, or --lat/--lon", err=True)
                return 1

            click.echo(f"Fetching data for: {target_station.name} (ID: {target_id})", err=True)

            # Fetch and transform data
            async with WeatherDataFetcher() as fetcher:
                fetcher.settings.timeout = timeout

                result = await fetcher.fetch_latest_data_for_station(target_id)
                click.echo(f"Fetched {result.records_count} records from {result.stations_count} stations", err=True)

                transformer = WeatherTransformer()
                weather_data = transformer.transform_to_openweather(result.data, target_id)

                # Format and output
                formatted_output = format_output(weather_data, output_format, compact)

                if output:
                    Path(output).write_text(formatted_output, encoding='utf-8')
                    click.echo(f"Data written to {output}", err=True)
                else:
                    click.echo(formatted_output)

            return 0

        except StationNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            return 1
        except DataUnavailableError as e:
            click.echo(f"Data unavailable: {e}", err=True)
            return 2
        except TransformationError as e:
            click.echo(f"Transformation error: {e}", err=True)
            return 3
        except NetworkError as e:
            click.echo(f"Network error: {e}", err=True)
            return 4
        except Exception as e:
            click.echo(f"Unexpected error: {e}", err=True)
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                import traceback
                traceback.print_exc()
            return 5

    return asyncio.run(_fetch())


@cli.command()
@click.option('--format', 'output_format', default='json', type=click.Choice(['json']),
              help='Output format')
@click.option('--output', '-o', type=click.Path(), help='Output file (default: stdout)')
@click.option('--compact', is_flag=True, help='Compact JSON output')
@click.option('--timeout', default=30.0, help='Request timeout in seconds')
@click.option('--limit', default=None, type=int, help='Limit number of stations (default: all)')
def fetch_all(output_format: str, output: Optional[str], compact: bool, timeout: float, limit: Optional[int]):
    """Fetch current weather data for all available stations."""

    async def _fetch_all():
        try:
            click.echo("Fetching data for all stations...", err=True)

            # Fetch the latest data file
            async with WeatherDataFetcher() as fetcher:
                fetcher.settings.timeout = timeout
                result = await fetcher.fetch_latest_data()
                click.echo(f"Fetched {result.records_count} records from {result.stations_count} stations", err=True)

                # Get list of available stations in the data
                available_station_ids = set()
                for record in result.data.get('data', []):
                    if record.get('ind_kli'):
                        available_station_ids.add(str(record.get('ind_kli')))

                station_ids = sorted(list(available_station_ids))
                if limit:
                    station_ids = station_ids[:limit]

                click.echo(f"Processing {len(station_ids)} stations...", err=True)

                # Transform data for each station
                transformer = WeatherTransformer()
                all_stations_data = []

                for i, station_id in enumerate(station_ids, 1):
                    try:
                        weather_data = transformer.transform_to_openweather(result.data, station_id)
                        all_stations_data.append(weather_data)

                        if i % 10 == 0:  # Progress update every 10 stations
                            click.echo(f"Processed {i}/{len(station_ids)} stations...", err=True)

                    except Exception as e:
                        click.echo(f"Warning: Failed to process station {station_id}: {e}", err=True)

                # Format output
                output_data = {
                    "count": len(all_stations_data),
                    "stations": all_stations_data,
                    "data_source": result.url,
                    "fetch_time": result.timestamp.isoformat()
                }

                formatted_output = format_output(output_data, output_format, compact)

                if output:
                    Path(output).write_text(formatted_output, encoding='utf-8')
                    click.echo(f"Data for {len(all_stations_data)} stations written to {output}", err=True)
                else:
                    click.echo(formatted_output)

            return 0

        except DataUnavailableError as e:
            click.echo(f"Data unavailable: {e}", err=True)
            return 2
        except TransformationError as e:
            click.echo(f"Transformation error: {e}", err=True)
            return 3
        except NetworkError as e:
            click.echo(f"Network error: {e}", err=True)
            return 4
        except Exception as e:
            click.echo(f"Unexpected error: {e}", err=True)
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                import traceback
                traceback.print_exc()
            return 5

    return asyncio.run(_fetch_all())


@cli.command()
@click.option('--query', required=True, help='Search query for station names')
@click.option('--limit', default=10, help='Maximum number of results')
def search(query: str, limit: int):
    """Search for weather stations by name."""
    try:
        results = search_stations(query)[:limit]

        if not results:
            click.echo(f"No stations found matching '{query}'")
            return 1

        click.echo(f"Found {len(results)} station(s) matching '{query}':")
        click.echo()

        for station in results:
            distance_info = ""
            click.echo(f"ID: {station.id}")
            click.echo(f"Name: {station.name}")
            click.echo(f"Location: {station.latitude:.4f}°N, {station.longitude:.4f}°E")
            click.echo(f"Elevation: {station.elevation}m")
            click.echo("-" * 50)

        return 0

    except Exception as e:
        click.echo(f"Search error: {e}", err=True)
        return 1


@cli.command()
@click.option('--lat', type=float, required=True, help='Latitude')
@click.option('--lon', type=float, required=True, help='Longitude')
@click.option('--radius', default=50, help='Search radius in kilometers')
def nearest(lat: float, lon: float, radius: int):
    """Find nearest weather stations to coordinates."""
    try:
        # Get stations within radius
        stations = stations_db.get_stations_in_radius(lat, lon, radius)

        if not stations:
            click.echo(f"No stations found within {radius}km of {lat:.4f}°N, {lon:.4f}°E")
            return 1

        click.echo(f"Stations within {radius}km of {lat:.4f}°N, {lon:.4f}°E:")
        click.echo()

        for i, station in enumerate(stations[:10], 1):  # Limit to 10 closest
            # Calculate distance
            from .stations import StationDatabase
            db = StationDatabase()
            distance = db._calculate_distance(lat, lon, station.latitude, station.longitude)

            click.echo(f"{i}. {station.name} (ID: {station.id})")
            click.echo(f"   Distance: {distance:.1f}km")
            click.echo(f"   Location: {station.latitude:.4f}°N, {station.longitude:.4f}°E")
            click.echo(f"   Elevation: {station.elevation}m")
            click.echo()

        return 0

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        return 1


@cli.command()
def list_stations():
    """List all available weather stations."""
    try:
        stations = stations_db.get_all_stations()

        click.echo(f"Available weather stations ({len(stations)} total):")
        click.echo()

        # Group by region (rough approximation based on longitude)
        western = [s for s in stations if s.longitude < 18.5]
        central = [s for s in stations if 18.5 <= s.longitude < 20.5]
        eastern = [s for s in stations if s.longitude >= 20.5]

        for region_name, region_stations in [
            ("Western Slovakia", western),
            ("Central Slovakia", central),
            ("Eastern Slovakia", eastern)
        ]:
            if region_stations:
                click.echo(f"{region_name}:")
                for station in sorted(region_stations, key=lambda s: s.name):
                    click.echo(f"  {station.id:>6} - {station.name}")
                click.echo()

        return 0

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        return 1


@cli.command()
def health():
    """Check health of the weather data service."""

    async def _health():
        click.echo("Checking service health...")

        try:
            async with WeatherDataFetcher() as fetcher:
                health_info = await fetcher.health_check()

                status = health_info.get('status', 'unknown')

                if status == 'healthy':
                    click.echo("✅ Service is healthy")
                    click.echo(f"   Response time: {health_info.get('response_time', 0):.2f}s")
                    click.echo(f"   Records: {health_info.get('records_count', 0)}")
                    click.echo(f"   Stations: {health_info.get('stations_count', 0)}")
                    return 0
                else:
                    click.echo("❌ Service is unhealthy")
                    click.echo(f"   Error: {health_info.get('error', 'Unknown error')}")
                    return 1

        except Exception as e:
            click.echo(f"❌ Health check failed: {e}")
            return 1

    return asyncio.run(_health())


@cli.command()
@click.option('--station-id', default='11816', help='Station ID to test (default: Bratislava)')
@click.option('--timeout', default=30.0, help='Request timeout in seconds')
def test(station_id: str, timeout: float):
    """Test the complete data pipeline with a known station."""

    async def _test():
        click.echo(f"Testing complete pipeline with station {station_id}...")

        try:
            # Test station lookup
            click.echo("1. Testing station lookup...")
            station = get_station_by_id(station_id)
            click.echo(f"   ✅ Station found: {station.name}")

            # Test data fetching
            click.echo("2. Testing data fetching...")
            async with WeatherDataFetcher() as fetcher:
                fetcher.settings.timeout = timeout
                result = await fetcher.fetch_latest_data_for_station(station_id)
                click.echo(f"   ✅ Data fetched: {result.records_count} records")

            # Test transformation
            click.echo("3. Testing data transformation...")
            transformer = WeatherTransformer()
            weather_data = transformer.transform_to_openweather(result.data, station_id)
            click.echo(f"   ✅ Transformation successful")

            # Validate result structure
            click.echo("4. Validating result structure...")
            required_fields = ['coord', 'weather', 'main', 'dt', 'id', 'name']
            missing_fields = [field for field in required_fields if field not in weather_data]

            if missing_fields:
                click.echo(f"   ❌ Missing required fields: {missing_fields}")
                return 1
            else:
                click.echo(f"   ✅ All required fields present")

            # Show sample data
            click.echo("5. Sample result:")
            sample = {
                'station': weather_data['name'],
                'temperature': weather_data['main'].get('temp'),
                'humidity': weather_data['main'].get('humidity'),
                'pressure': weather_data['main'].get('pressure'),
                'wind_speed': weather_data.get('wind', {}).get('speed'),
                'timestamp': weather_data['dt']
            }
            click.echo(f"   {json.dumps(sample, indent=4)}")

            click.echo("\n✅ All tests passed!")
            return 0

        except Exception as e:
            click.echo(f"❌ Test failed: {e}")
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                import traceback
                traceback.print_exc()
            return 1

    return asyncio.run(_test())


if __name__ == '__main__':
    sys.exit(cli())