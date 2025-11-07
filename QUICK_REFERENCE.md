# iMeteo Stations - Quick Reference Guide

## What Is This Application?

A **weather data aggregator** that:
- Fetches real-time weather data from 110 Slovak weather stations (SHMU)
- Transforms the data into OpenWeatherMap format
- Provides CLI tools for querying and searching stations
- Runs as a Docker container or standalone Python CLI

**Use Case**: Weather service APIs, data collection, weather monitoring systems

---

## Codebase at a Glance

| File | Size | Purpose |
|------|------|---------|
| **main.py** | 424 lines | CLI commands (fetch, search, nearest, etc.) |
| **fetcher.py** | 469 lines | HTTP data fetching with smart URL discovery |
| **transformer.py** | 686 lines | Data aggregation & OpenWeatherMap conversion |
| **stations.py** | 414 lines | Station database & geolocation |
| **time_utils.py** | 168 lines | Timezone handling (CET/CEST complexity) |
| **TOTAL** | 2,163 lines | ~50KB of Python code |

---

## Technology Stack

```
Python 3.12+ (async/await)
  ├── httpx (async HTTP client)
  ├── pydantic (validation)
  ├── click (CLI)
  └── structlog (logging)

Docker: python:3.14-rc-slim
Build: hatchling
Quality: mypy (strict), ruff, pytest
```

---

## Architecture Overview

```
CLI User
   │
   ▼
main.py (Click commands)
   │
   ├─→ fetcher.py (HTTP)        [BOTTLENECK: URL discovery]
   │     └─→ time_utils.py       [Timezone handling]
   │
   ├─→ transformer.py            [BOTTLENECK: Aggregation math]
   │     └─→ wind vector averaging (trig functions)
   │
   └─→ stations.py               [BOTTLENECK: Distance calc]
         └─→ Haversine formula (110 stations)

Output: OpenWeatherMap JSON
```

---

## Performance Bottlenecks (Short Version)

### 🔴 CRITICAL (Easy Wins)

1. **Batch Processing** (main.py:183-192)
   - Sequential loop for 95 stations
   - Should be: Parallel processing
   - Gain: 3-5x

2. **Wind Math** (transformer.py:182-226)
   - 5 trig operations per record
   - Should be: SIMD vectorization
   - Gain: 5-10x

3. **Distance Loop** (stations.py:307-333)
   - Haversine for 110 stations
   - Should be: KD-tree spatial index
   - Gain: 10-50x

### 🟠 HIGH (Medium Effort)

4. **Window Grouping** (transformer.py:331-371)
   - DateTime parsing per record
   - Gain: 2-3x

5. **Fuzzy Search** (stations.py:224-237)
   - Multi-pass string matching
   - Gain: 3-5x

6. **URL Discovery** (fetcher.py:94-157)
   - HTML regex parsing
   - Gain: 2-3x

---

## Rust Optimization Strategy

**Goal**: Move CPU-intensive code to Rust via PyO3

```
Current:  Python → Python → Python [Slow]
Optimized: Python → Rust → Python [Fast]

Keep Python for:
  - CLI interface (Click)
  - HTTP orchestration
  - Main logic

Move to Rust:
  - Data aggregation (transformer)
  - Geolocation (stations)
  - Math operations
```

### 4-Week Implementation

| Week | Focus | Expected Gain |
|------|-------|---------------|
| 1 | Aggregation engine | 5-10x |
| 2 | Station database | 10-50x |
| 3 | URL discovery | 2-3x |
| 4 | Integration & testing | 3-8x overall |

---

## Key Data Structures

### Station
```
ID: "11816"
Name: "Bratislava - letisko"
Coordinates: (48.17°N, 17.21°E)
Elevation: 133m
```

### Weather Record (per station, 1-minute)
```
{
  "ind_kli": "11816",           # Station ID
  "minuta": "2025-01-15T10:35", # Timestamp
  "t": 5.7,                      # Temperature (°C)
  "vlh_rel": 76,                # Humidity (%)
  "tlak": 1004,                 # Pressure (hPa)
  "vie_pr_rych": 1.0,           # Wind speed (m/s)
  "vie_pr_smer": 342,           # Wind direction (°)
  ...                           # 30+ other fields
}
```

### Aggregation (5 records → 1 output)
```
5x 1-minute records → Aggregation rules → OpenWeather format

Strategies:
- LAST: Use most recent (temperature, humidity)
- SUM: Total (precipitation)
- MEAN: Average (radiation)
- VECTOR_AVG: Wind average (directional)
```

---

## Code Hotspots for Profiling

```python
# #1 Highest impact - measure first
transformer.py::_vector_average_direction()  # Lines 182-226
→ 5 trig ops × 5 records × 95 stations = 2,375 trig calls

# #2 Sequential bottleneck
main.py::fetch_all()  # Lines 183-192
→ for station_id in station_ids: process(station_id)
→ 95 iterations, ~500ms each

# #3 Search bottleneck
stations.py::get_nearest_station()  # Lines 266-274
→ for station in 110 stations: calculate_distance()
→ 110 distance calculations

# #4 Text processing
stations.py::get_station_by_name()  # Lines 224-237
→ Nested loops with string ops

# #5 DateTime parsing
transformer.py::_get_latest_5min_window()  # Lines 331-371
→ datetime.fromisoformat() per record
```

---

## Files to Optimize (Priority Order)

1. ⚠️ **transformer.py** (686 lines)
   - Data aggregation engine
   - Mathematical operations
   - Estimated speedup: 5-10x

2. ⚠️ **stations.py** (414 lines)
   - Geolocation calculations
   - Fuzzy matching
   - Estimated speedup: 10-50x

3. ⚠️ **fetcher.py** (469 lines)
   - URL discovery
   - HTTP orchestration
   - Estimated speedup: 2-3x

4. ✓ **main.py** (424 lines)
   - Keep as-is (CLI wrapper)
   - Will benefit from optimized modules

5. ✓ **time_utils.py** (168 lines)
   - Keep as-is (good as-is)
   - Or optimize for batch operations

---

## Testing Strategy for Optimization

### Before Rust Rewrite
```bash
# Benchmark current performance
pytest tests/ --benchmark

# Profile hot spots
python -m cProfile -s cumulative src/main.py fetch-all

# Profile specific functions
import cProfile
cProfile.run('transformer._vector_average_direction(...)')
```

### After Rust Integration
```bash
# Validate correctness
pytest tests/ -v  # Must pass 100%

# Compare performance
benchmark_python.py vs benchmark_rust.py

# Integration tests
test_rust_bindings.py  # PyO3 FFI tests
```

---

## Integration Points (PyO3)

### Python Calls Rust
```python
from imeteo_core import aggregate_records, find_nearest_station

# In transformer.py
aggregated = aggregate_records(station_records, station_id)

# In stations.py
nearest = find_nearest_station(lat, lon)
```

### Type Definitions (Must Match)
```
Python             Rust
Dict[str, Any]  ↔  serde_json::Value
List[Dict]      ↔  Vec<serde_json::Value>
float           ↔  f64
str             ↔  String
int             ↔  i32/i64
Optional[T]     ↔  Option<T>
```

---

## Performance Targets

| Operation | Current | Target | Gain |
|-----------|---------|--------|------|
| fetch(1 station) | 2-5s | 1-2s | 2-3x |
| fetch-all(95) | 60-120s | 15-30s | 3-5x |
| search(name) | 10-50ms | 1-5ms | 5-10x |
| nearest(lat,lon) | 20-100ms | 2-5ms | 10-50x |
| wind average | ~10ms | ~1ms | 10x |
| overall | 1x | 3-8x | **3-8x** |

---

## Red Flags to Avoid

❌ **Don't**:
- Rewrite Python-specific logic in Rust (click, asyncio)
- Change the public Python API
- Add too many dependencies
- Ignore error cases
- Skip testing during transition

✅ **Do**:
- Keep PyO3 bindings simple
- Write comprehensive integration tests
- Benchmark before and after
- Document the FFI boundary
- Use type-safe Rust features

---

## Recommended Reading

1. **PyO3 Documentation**: https://pyo3.rs/
2. **Rust Performance**: https://nnethercote.github.io/perf-book/
3. **This Project's Analysis**: `CODEBASE_ANALYSIS.md`
4. **Optimization Roadmap**: `RUST_OPTIMIZATION_ROADMAP.md`

---

## Quick Commands

```bash
# Build Docker image
./docker-build.sh

# Run CLI
docker run --rm imeteo-stations fetch --station-id 11816

# Test
pytest tests/ -v

# Benchmark (after instrumentation)
python -m pytest tests/ --benchmark

# Profile
python -m cProfile -s cumulative -m src.main fetch-all
```

---

**Last Updated**: 2025-01-15
**Total LOC**: 2,163 Python + docs
**Performance Gain Target**: 3-8x overall improvement
