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
