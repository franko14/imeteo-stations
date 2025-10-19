# Slovak Weather Station Data Fetcher

Real-time weather data from 95+ Slovak automatic weather stations in OpenWeatherMap-compatible JSON format.

**Developed for [iMeteo.sk](https://www.imeteo.sk)** - Slovakia's premier weather service.

## Features

- Real-time data from 95+ weather stations across Slovakia
- OpenWeatherMap-compatible JSON format
- Multiple ways to fetch: by station ID, name, or coordinates
- Docker support with Python 3.14
- Simple CLI interface

## Getting Started

### Build Docker Image

```bash
./docker-build.sh
```

## Usage Examples

### Fetch weather data

```bash
# By station ID (Bratislava Airport)
docker run --rm imeteo-stations fetch --station-id 11816

# By station name
docker run --rm imeteo-stations fetch --station "Bratislava letisko"

# By coordinates (finds nearest)
docker run --rm imeteo-stations fetch --lat 48.17 --lon 17.20

# Fetch all stations
docker run --rm imeteo-stations fetch-all

# Save to file
docker run --rm imeteo-stations fetch --station-id 11816 > weather.json

# Compact output
docker run --rm imeteo-stations fetch --station-id 11816 --compact
```

### Find stations

```bash
# Search by name
docker run --rm imeteo-stations search --query "Bratislava"

# Find nearest station
docker run --rm imeteo-stations nearest --lat 48.17 --lon 17.20

# List all available stations
docker run --rm imeteo-stations list-stations

# Show help
docker run --rm imeteo-stations --help
```

### Example Output

```json
{
  "coord": {
    "lon": 17.2075,
    "lat": 48.17027778
  },
  "weather": [
    {
      "id": 804,
      "main": "Clouds",
      "description": "overcast clouds",
      "icon": "04d"
    }
  ],
  "base": "stations",
  "main": {
    "temp": 5.7,
    "feels_like": 5.7,
    "temp_min": 5.4,
    "temp_max": 5.7,
    "pressure": 1004,
    "sea_level": 1004,
    "grnd_level": 1004,
    "humidity": 76
  },
  "visibility": null,
  "wind": {
    "speed": 1.0,
    "deg": 342,
    "gust": 1.4
  },
  "clouds": {
    "all": 100
  },
  "dt": 1760901240,
  "sys": {
    "type": 2,
    "id": 11816,
    "country": "SK",
    "sunrise": 1760853600,
    "sunset": 1760896800
  },
  "timezone": 3600,
  "id": 11816,
  "name": "Bratislava - letisko",
  "cod": 200,
  "timestamps": {
    "utc": "2025-10-19 19:14:00 UTC",
    "bratislava": "2025-10-19 21:14:00 CET/CEST"
  }
}
```

## Troubleshooting

### Common Issues

#### Data Unavailable Error
```
Data unavailable: No weather data available for station X in the last 40 minutes.
```

**What it means:** The system searched 8 time windows (40 minutes of data) but couldn't find data for this station.

**Possible causes:**
- SHMU service delay (data publishes every 5 minutes)
- Station temporarily offline for maintenance
- Brief service outage

**What to do:**
- Wait 5-10 minutes and try again
- Verify station ID with `docker run --rm imeteo-stations list-stations`
- Check service health: `docker run --rm imeteo-stations health`

#### Network Error
```
Network error: Connection failed to SHMU servers
```

**Possible causes:**
- No internet connection
- Firewall blocking access to opendata.shmu.sk
- SHMU server is temporarily unreachable

**What to do:**
- Check your internet connection
- Verify you can reach `https://opendata.shmu.sk`
- Try again in a few moments

#### Station Not Found
```
Error: Station ID 'XXXXX' not found
```

**What it means:** The provided station ID doesn't exist in the database.

**What to do:**
- List all stations: `docker run --rm imeteo-stations list-stations`
- Search by name: `docker run --rm imeteo-stations search --query "Bratislava"`

#### Request Timeout
```
Timeout for URL: https://...
```

**What it means:** Request took longer than the timeout setting (default 30 seconds).

**Possible causes:**
- Slow internet connection
- SHMU server overloaded

**What to do:**
- Increase timeout with `--timeout` flag:
```bash
# Increase to 60 seconds
docker run --rm imeteo-stations fetch --station-id 11816 --timeout 60

# For slow connections, try 120 seconds
docker run --rm imeteo-stations fetch-all --timeout 120
```

### Exit Codes

The tool uses these exit codes for automation and scripting:

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Success | Data retrieved successfully |
| 1 | Not found | Station ID invalid or not found |
| 2 | Data unavailable | No data in last 40 minutes |
| 3 | Transformation error | Data processing failed |
| 4 | Network error | Connection/network issues |
| 5 | Unexpected error | Unhandled exception |

### Getting Help

Run with `--debug` flag for detailed logs:
```bash
docker run --rm imeteo-stations fetch --station-id 11816 --debug
```

Check service status:
```bash
docker run --rm imeteo-stations health
```

## Station Coverage

95 automatic weather stations across Slovakia:

- **Western Slovakia**: Bratislava, Senica, Trenčín, Piešťany
- **Central Slovakia**: Žilina, Banská Bystrica, Poprad, Chopok (2005m)
- **Eastern Slovakia**: Košice, Prešov, Bardejov, Michalovce

### Key Stations

| ID | Name | Location |
|----|------|----------|
| 11816 | Bratislava - letisko | 48.17°N, 17.20°E |
| 11968 | Košice - letisko | 48.67°N, 21.22°E |
| 11916 | Chopok | 48.94°N, 19.59°E |
| 11934 | Poprad | 49.07°N, 20.25°E |

Use `docker run --rm imeteo-stations list-stations` to see all available stations.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/imeteo-sk/imeteo-stations/issues)
- **Weather Service**: [iMeteo.sk](https://www.imeteo.sk)
- **Data Source**: [SHMU](https://www.shmu.sk) - Slovak Hydrometeorological Institute
