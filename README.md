# Slovak Weather Station Data Fetcher

A robust Python application for fetching real-time weather data from Slovak Automatic Weather Stations (SHMU) and transforming it into OpenWeatherMap-compatible JSON format.

**Developed for [iMeteo.sk](https://www.imeteo.sk)** - Slovakia's premier weather service.

## 🌡️ Features

- **Real-time data fetching** from 95+ Slovak weather stations
- **Smart URL discovery** with automatic fallback for data availability
- **Proper aggregation** of 1-minute data within 5-minute boundaries
- **OpenWeatherMap compatibility** for easy integration
- **Slovak timezone handling** (CEST/CET complexities)
- **Comprehensive error handling** and retry logic
- **CLI interface** with multiple output formats
- **Extensive test coverage** with integration tests

## 🚀 Quick Start

### Installation

```bash
# Install from source
git clone https://github.com/imeteo-sk/imeteo-stations.git
cd imeteo-stations

# Install with uv (recommended)
uv venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
uv pip install -e .

# Or install with pip
pip install -e .
```

### Basic Usage

```bash
# Fetch current weather for Bratislava Airport
imeteo fetch --station-id 11816

# Search for stations by name
imeteo search --query "Bratislava"

# Find nearest station to coordinates
imeteo nearest --lat 48.17 --lon 17.20

# Test the complete pipeline
imeteo test
```

### Python API

```python
import asyncio
from src.fetcher import WeatherDataFetcher
from src.transformer import WeatherTransformer

async def get_weather():
    async with WeatherDataFetcher() as fetcher:
        # Fetch latest data
        result = await fetcher.fetch_latest_data()

        # Transform to OpenWeatherMap format
        transformer = WeatherTransformer()
        weather_data = transformer.transform_to_openweather(
            result.data, "11816"  # Bratislava Airport
        )

        return weather_data

# Run
weather = asyncio.run(get_weather())
print(f"Temperature: {weather['main']['temp']}°C")
```

## 📊 Data Aggregation Strategy

**CRITICAL**: Each JSON file contains exactly **5 minutes of 1-minute resolution data** per station. Aggregation rules:

| Measurement Type | Strategy | Fields |
|-----------------|----------|---------|
| Temperature, Pressure, Humidity | **LAST** (most recent) | `t`, `tlak`, `vlh_rel` |
| Precipitation, Sunshine | **SUM** (all 5 minutes) | `zra_uhrn`, `zra_trv`, `sln_trv` |
| Wind extremes | **MIN/MAX** (scan all) | `vie_min_rych`, `vie_max_rych` |
| Radiation | **MEAN** (average) | `zglo`, `zgama` |

## 🏛️ Architecture

```
src/
├── main.py          # CLI entry point
├── fetcher.py       # Smart URL discovery & HTTP fetching
├── transformer.py   # Data aggregation & OpenWeatherMap format
├── stations.py      # Station metadata (95 stations)
├── time_utils.py    # Slovak timezone handling
└── models.py        # Pydantic data models
```

### Key Components

1. **Smart Fetcher**: Handles Slovak timezone complexities and file availability
2. **Data Aggregator**: Enforces 5-minute boundaries with proper strategies
3. **Station Database**: Complete metadata for all 95 Slovak stations
4. **Time Utilities**: Manages CEST/CET transitions and data timestamp corrections

## 🌍 Station Coverage

95 automatic weather stations across Slovakia:

- **Western Slovakia**: Bratislava, Senica, Trenčín, Piešťany
- **Central Slovakia**: Žilina, Banská Bystrica, Poprad, Chopok (2005m)
- **Eastern Slovakia**: Košice, Prešov, Bardejov, Michalovce

### Key Stations

| ID | Name | Location | Elevation |
|----|------|----------|-----------|
| 11816 | Bratislava - letisko | 48.17°N, 17.20°E | 133m |
| 11968 | Košice - letisko | 48.67°N, 21.22°E | 230m |
| 11916 | Chopok | 48.94°N, 19.59°E | 2005m |
| 11934 | Poprad | 49.07°N, 20.25°E | 694m |

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run integration tests only
pytest tests/test_integration.py

# Test live API (requires internet)
imeteo test --station-id 11816
```

## 📚 CLI Commands

### Fetch Weather Data

```bash
# By station ID
imeteo fetch --station-id 11816

# By station name (fuzzy matching)
imeteo fetch --station "Bratislava letisko"

# By coordinates (finds nearest)
imeteo fetch --lat 48.17 --lon 17.20

# Compact JSON output
imeteo fetch --station-id 11816 --compact

# Save to file
imeteo fetch --station-id 11816 --output weather.json
```

### Station Management

```bash
# Search stations
imeteo search --query "Bratislava" --limit 5

# Find nearest stations
imeteo nearest --lat 48.17 --lon 17.20 --radius 50

# List all stations
imeteo list-stations
```

### System Health

```bash
# Health check
imeteo health

# Full pipeline test
imeteo test --station-id 11816 --debug
```

## 🔧 Configuration

### Environment Variables

```bash
# Optional configuration
export IMETEO_BASE_URL="https://opendata.shmu.sk/meteorology/climate/now/data"
export IMETEO_TIMEOUT=30
export IMETEO_RETRIES=3
```

### Custom Settings

```python
from src.fetcher import WeatherDataFetcher, FetchSettings

settings = FetchSettings(
    timeout=60.0,
    max_retries=5,
    user_agent="MyApp/1.0.0"
)

async with WeatherDataFetcher(settings) as fetcher:
    data = await fetcher.fetch_latest_data()
```

## 🕒 Slovak Timezone Handling

The application correctly handles Slovakia's complex timezone situation:

- **File URLs**: Use local Slovak time (CEST in summer, CET in winter)
- **Data timestamps**: Appear as UTC but are actually UTC+1
- **Output**: Proper UTC timestamps in OpenWeatherMap format

```python
# Automatic timezone detection and conversion
from src.time_utils import fix_data_timestamp, utc_to_slovak_time

# Convert Slovak data timestamp to true UTC
utc_time = fix_data_timestamp("2025-09-16T18:35:00")  # Subtracts 1 hour
```

## 📖 Data Format

### Input (SHMU)
```json
{
  "data": [
    {
      "ind_kli": "11816",
      "minuta": "2025-09-16T17:35:00",
      "t": 15.8,
      "tlak": 1015.2,
      "vlh_rel": 65.0,
      "vie_pr_rych": 2.1,
      "zra_uhrn": 0.0
    }
  ]
}
```

### Output (OpenWeatherMap Compatible)
```json
{
  "coord": {"lat": 48.171667, "lon": 17.2},
  "weather": [{"id": 803, "main": "Clouds", "description": "broken clouds"}],
  "main": {
    "temp": 15.8,
    "feels_like": 14.2,
    "pressure": 1015,
    "humidity": 65
  },
  "wind": {"speed": 2.1, "deg": 180},
  "dt": 1726505700,
  "id": 11816,
  "name": "Bratislava - letisko"
}
```

## 🚨 Critical Constraints

1. **5-minute boundaries**: Never aggregate across multiple JSON files
2. **Timezone handling**: URLs use CEST/CET, data is UTC+1
3. **Data availability**: Files may be delayed; smart discovery tries multiple windows
4. **Station filtering**: Each file contains all 95 stations; filter by `ind_kli`

## 🔍 Debugging

```bash
# Enable debug logging
imeteo fetch --station-id 11816 --debug

# Check service health
imeteo health

# Verbose pipeline test
imeteo test --debug
```

## 📈 Performance

- **Async/await**: Non-blocking I/O for concurrent requests
- **Smart caching**: 4-minute TTL with stale data fallback
- **Connection pooling**: Reuses HTTP connections
- **Parallel discovery**: Tests multiple URLs simultaneously

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Install development dependencies (`uv pip install -e ".[dev]"`)
4. Run tests (`pytest`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Development Setup

```bash
# Clone and setup
git clone https://github.com/imeteo-sk/imeteo-stations.git
cd imeteo-stations

# Install with development dependencies
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Run pre-commit hooks
pre-commit install

# Run tests with coverage
pytest --cov=src --cov-report=html
```

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **SHMU** (Slovak Hydrometeorological Institute) for providing open weather data
- **iMeteo.sk** team for project requirements and testing
- **OpenWeatherMap** for API format inspiration

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/imeteo-sk/imeteo-stations/issues)
- **Documentation**: See `docs/` directory and inline docstrings
- **iMeteo.sk**: [https://www.imeteo.sk](https://www.imeteo.sk)

---

**Built with ❤️ for Slovak weather enthusiasts**