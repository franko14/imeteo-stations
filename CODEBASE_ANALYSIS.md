# iMeteo Stations Codebase Analysis

## 1. APPLICATION PURPOSE & FUNCTIONALITY

### Core Purpose
Slovak weather station data fetcher that retrieves real-time weather data from 110+ automatic weather stations across Slovakia operated by SHMU (Slovak Hydrometeorological Institute) and transforms it to OpenWeatherMap-compatible JSON format.

### Primary Use Case
- Real-time weather data aggregation from 95+ Slovak weather stations
- OpenWeatherMap API compatibility
- Containerized deployment with Docker support
- CLI interface for data fetching and queries

### Key Features
- **Data Fetching**: Retrieves 5-minute resolution weather data from SHMU API
- **Station Management**: 110 stations with metadata (ID, coordinates, elevation)
- **Data Transformation**: Converts SHMU format to OpenWeatherMap standard
- **Multiple Query Modes**:
  - By station ID
  - By station name (fuzzy matching)
  - By geographic coordinates (nearest station)
  - Batch fetch all stations
- **Health Checking**: Service status validation
- **Error Handling**: Comprehensive error reporting with exit codes (0-5)

---

## 2. TECHNOLOGY STACK

### Language & Runtime
- **Python 3.12+** (upgraded to 3.14-rc in recent commits)
- **Type Hints**: Full type annotations enabled (mypy strict mode)

### Core Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| httpx | >=0.25.0 | Async HTTP client for SHMU API requests |
| pydantic | >=2.5.0 | Data validation and configuration |
| python-dateutil | >=2.8.0 | Timezone handling |
| click | >=8.1.0 | CLI framework |
| structlog | >=23.2.0 | Structured logging |

### Optional Dependencies
- **API Stack**: FastAPI, uvicorn, aioredis (for future API service)
- **Testing**: pytest, pytest-asyncio, pytest-httpx, pytest-cov
- **Quality**: ruff (linting), mypy (type checking), pre-commit

### Build & Deployment
- **Build System**: Hatchling (pyproject.toml)
- **Containerization**: Docker (Python 3.14-rc-slim)
- **Distribution**: pip-installable package (pyproject.toml)

---

## 3. MAIN COMPONENTS & ARCHITECTURE

```
src/
├── main.py          (424 lines) - CLI interface & command handlers
├── fetcher.py       (469 lines) - HTTP data fetching with smart URL discovery
├── transformer.py   (686 lines) - Data aggregation & OpenWeatherMap transformation
├── stations.py      (414 lines) - Station database & geolocation functions
├── time_utils.py    (168 lines) - Timezone handling (CET/CEST complexity)
└── __init__.py      (2 lines)   - Package marker

Total: 2,163 lines of Python code
```

### Component Responsibilities

#### **main.py** - CLI Entry Point (424 lines)
- **7 Commands**: fetch, fetch-all, search, nearest, list-stations, health, test
- Async command wrappers using asyncio.run()
- Error handling with specific exit codes
- Output formatting (JSON, compact)
- Progress reporting for batch operations

#### **fetcher.py** - Smart Data Fetcher (469 lines)
- `WeatherDataFetcher` class: Main data retrieval orchestrator
- **Key Features**:
  - Smart URL discovery with directory listing
  - Time window management (8 candidates per request)
  - Exponential backoff retry logic (3 attempts)
  - URL caching for recent requests
  - Data structure validation
  - Async parallel fetch attempts with asyncio.gather()
- **Timeout Handling**: Default 30s with timeout*2 for parallel operations
- **Critical Complexity**: Handles SHMU's 5-minute file structure and publication delays

#### **transformer.py** - Data Aggregation & Transformation (686 lines)
- `WeatherTransformer`: Main transformation orchestrator
- `DataAggregator`: 1-minute to 5-minute window aggregation
- **Aggregation Strategies**:
  - LAST: Instantaneous measurements (temperature, humidity, etc.)
  - SUM: Accumulative (precipitation, sunshine duration)
  - MEAN: Averaged values (radiation)
  - MIN/MAX: Wind extremes
  - VECTOR_AVG: Wind direction (complex trigonometry)
- **Processing Pipeline**:
  1. Filter records for target station
  2. Group into 5-minute windows
  3. Apply aggregation rules per field
  4. Calculate derived values (feels-like, dew point)
  5. Map to OpenWeatherMap schema
- **Mathematical Operations**:
  - Haversine distance calculations (not here, in stations.py)
  - Vector wind averaging (sine/cosine components)
  - Heat index & wind chill calculations

#### **stations.py** - Station Database (414 lines)
- `StationDatabase`: In-memory station metadata store
- **110 Stations**: Complete SHMU station inventory
- **Index Structures**:
  - Primary: ID-based lookup (O(1))
  - Secondary: Name-based with diacritics handling
  - Fuzzy matching for partial name queries
- **Geolocation Features**:
  - Haversine distance calculation
  - Radius-based station search
  - Nearest station lookup
- **Text Processing**:
  - Slovak diacritics removal (á→a, č→c, etc.)
  - Case-insensitive matching
  - Multi-word search with relevance scoring

#### **time_utils.py** - Timezone Magic (168 lines)
- **Critical Complexity**: SHMU uses Slovak local time (CET/CEST) in URLs but timestamps marked as UTC
- `get_current_time_windows()`: Generates 8 candidate time windows accounting for:
  - Summer (CEST = UTC+2) vs Winter (CET = UTC+1)
  - File publication delays (0-15 min offsets)
  - 5-minute rounding boundaries
- DST detection: Last Sunday of March/October transitions
- Timestamp correction: Subtracts 1 hour from "fake UTC" to get real UTC

---

## 4. PERFORMANCE-CRITICAL AREAS & BOTTLENECKS

### Critical Performance Paths

#### **A. Data Fetching Pipeline** (fetcher.py)
**Bottleneck 1: URL Discovery**
- Current: Sequential HTTP GET per time window + regex parsing of HTML
- Issue: Inefficient directory listing and regex-based file matching
- Scale: 8 time windows × 2-3 retries = potential 24+ HTTP requests per fetch
- Symptoms: High latency, especially with network delays

**Bottleneck 2: Parallel Fetch Without Optimization**
- Current: asyncio.gather() for all discovered URLs
- Issue: No connection pooling optimization across sequential calls
- Problem: Timeout multiplied by 2 (timeout*2) for parallel operations

#### **B. Data Transformation** (transformer.py)
**Bottleneck 3: Vector Wind Averaging**
- Current: Trigonometric calculations per record (sine, cosine, atan2)
- Issue: Performed on every 5-minute window, 110+ stations
- Complexity: O(5 * num_stations) = ~550 trigonometric operations per fetch-all
- Code lines 182-226: Loop-based record iteration with math ops

**Bottleneck 4: 5-Minute Window Grouping**
- Current: Full record iteration with datetime parsing per record (lines 331-371)
- Issue: ISO timestamp parsing, dictionary operations in tight loop
- Problem: Performed on potentially hundreds of records per station

#### **C. Station Lookups** (stations.py)
**Bottleneck 5: Fuzzy Name Matching**
- Current: Multi-pass search with nested loops (lines 224-237)
- Issue: O(n) searches with word splitting and set operations
- For 'search' command: Could iterate full station list multiple times
- Scale: 110 stations × multiple passes

**Bottleneck 6: Haversine Distance Calculation**
- Current: Math-heavy calculations (sin, cos, sqrt, atan) in tight loop
- Issue: Full station scan for nearest/radius queries (lines 307-333)
- Scale: O(n) for every geolocation query on 110 stations
- Problem: Not optimized for batch radius queries

#### **D. Batch Operations** (main.py, lines 157-228)
**Bottleneck 7: fetch-all Sequential Transformation**
- Current: Sequential loop processing all stations (lines 183-192)
- Issue: No parallel transformation of 95+ stations
- Scale: 100+ seconds for fetch-all on slow connections
- Problem: Main bottleneck for high-volume data collection
- Code: Lines 183-192 show synchronous loop

#### **E. Data Structure Validation** (fetcher.py)
**Bottleneck 8: Repeated Structure Validation**
- Current: Validation on every fetch attempt (lines 265-301)
- Issue: Redundant checks for already-validated data
- Problem: JSON parsing happens multiple times

### Summary of Performance Issues

| Issue | Location | Scale | Impact |
|-------|----------|-------|--------|
| Sequential URL discovery | fetcher.py | 8 windows | High latency |
| Inefficient HTML parsing | fetcher.py | Per request | I/O bound |
| Vector math in loops | transformer.py | 5 records/station | CPU bound |
| DateTime parsing in loops | transformer.py | Per record | CPU bound |
| Nested station searches | stations.py | Multiple passes | CPU bound |
| Full Haversine loop | stations.py | 110 stations | CPU bound |
| Sequential batch processing | main.py | 95+ stations | Critical bottleneck |
| Repeated validation | fetcher.py | Per attempt | CPU bound |

---

## 5. CURRENT DEPENDENCIES & BUILD SETUP

### Dependency Tree
```
imeteo-stations
├── httpx 0.25+ (async HTTP)
├── pydantic 2.5+ (validation)
├── python-dateutil 2.8+ (date handling)
├── click 8.1+ (CLI)
└── structlog 23.2+ (logging)

[DEV]
├── pytest 7.4+
├── pytest-asyncio 0.21+
├── pytest-httpx 0.22+ (mock HTTP)
├── ruff (linting)
└── mypy 1.7+ (strict type checking)

[OPTIONAL: API]
├── fastapi 0.104+
├── uvicorn[standard] 0.24+
└── aioredis 2.0+
```

### Build Pipeline
```
1. pyproject.toml (hatchling backend)
   ├── Source: ./src/
   ├── Entry point: imeteo = src.main:cli
   └── Python 3.12+ required

2. Docker Build
   ├── Base: python:3.14-rc-slim
   ├── Package installation: pip install .
   └── Entrypoint: imeteo (CLI)

3. Testing
   ├── pytest with asyncio support
   ├── HTTP mocking with pytest-httpx
   └── Coverage reporting
```

### Quality Tools
- **Ruff**: Fast Python linting (E, W, F, I, B, C4, UP rules)
- **MyPy**: Strict type checking (all strict options enabled)
- **Pre-commit**: Git hooks for quality gates

---

## 6. AREAS SUITABLE FOR RUST OPTIMIZATION

### TIER 1: High-Impact Optimization Opportunities

#### **1. Data Aggregation Engine** (transformer.py)
**Why Rust?**
- Heavy CPU workload: 5-minute window grouping, aggregation, math
- Current bottleneck: Vector wind averaging with trigonometry
- Scale: 110+ stations × thousands of data points daily
- Memory-intensive: Large JSON parsing and transformation

**Expected Improvement**: 3-10x speedup
- Python loops → Rust vectorized operations
- Math operations: Compiled SIMD
- JSON parsing: serde_json (faster than Python)
- Memory: Zero-copy transformations

**Scope**: Core aggregation logic (500+ lines of Python)

#### **2. Station Database & Geolocation** (stations.py)
**Why Rust?**
- O(n) distance calculations in tight loops
- Haversine formula: CPU-intensive math
- Multiple search types: fuzzy matching, radius, nearest
- 110 stations × multiple queries per request

**Expected Improvement**: 5-50x speedup
- Fuzzy matching: String algorithms (edit distance, Levenshtein)
- Geolocation: SIMD distance calculations
- Spatial indexing: KD-tree for nearest neighbor searches
- Zero-copy text processing

**Scope**: Station lookup, fuzzy matching, distance calculations

#### **3. URL Discovery & HTTP Orchestration** (fetcher.py)
**Why Rust?**
- HTML regex parsing: Inefficient in Python
- URL construction and validation
- Parallel HTTP orchestration
- Retry logic with exponential backoff

**Expected Improvement**: 2-5x speedup
- HTML parsing: nom/regex library
- Concurrent HTTP: tokio + reqwest
- Connection pooling: Better than httpx
- URL handling: Compiled string operations

**Scope**: Directory listing, file discovery, retry logic

### TIER 2: Medium-Impact Optimizations

#### **4. JSON Processing Pipeline**
**Why Rust?**
- Current: Multiple json() calls per request
- Issue: Python's json module is slower than Rust alternatives
- Scale: Every fetch operation

**Expected Improvement**: 1.5-3x speedup
- serde_json: Near C-level JSON performance
- Stream parsing for large files
- Type-safe deserialization

#### **5. Timezone Calculations** (time_utils.py)
**Why Rust?**
- Current: Datetime object creation in loops
- Issue: Python datetime is slow for bulk operations
- Scale: 8 windows × retries per fetch

**Expected Improvement**: 2-3x speedup
- chrono crate: Optimized datetime handling
- Pre-computed DST tables
- Bulk calculations without object allocation

### TIER 3: Infrastructure Optimizations

#### **6. HTTP Client Wrapper**
**Why Rust?**
- Async runtime: Rust tokio vs Python asyncio
- Better connection pooling
- HTTP/2 support
- Proper timeout handling

**Expected Improvement**: 1.5-2x speedup for concurrent operations

#### **7. CLI Command Handler**
**Why Rust?**
- Startup time: Rust is instant vs Python 0.5-1s
- Memory: Rust minimal overhead vs Python runtime
- Binary distribution: Single executable

**Expected Improvement**: Startup time from 1s → 50ms

---

## 7. RECOMMENDED RUST OPTIMIZATION STRATEGY

### Phase 1: High-Impact, Self-Contained Modules
**Priority 1: Aggregation Engine** (transformer.py logic)
- Standalone module: Independent of other components
- High CPU workload: Direct performance impact
- Clear interface: `aggregate_records(data, station_id) → result`
- Build: Rust library exposed via PyO3

**Timeline**: 2-4 weeks
**Expected Speedup**: 5-10x
**Complexity**: Medium (trigonometry, aggregation logic)

### Phase 2: Critical Path Optimization
**Priority 2: Station Database** (stations.py)
- Geolocation: Nearest station, radius search
- Fuzzy matching: Name-based queries
- Build: Separate Rust binary or shared library

**Timeline**: 2-3 weeks
**Expected Speedup**: 5-50x for geolocation
**Complexity**: High (spatial indexing, string algorithms)

### Phase 3: I/O Optimization
**Priority 3: Data Fetcher** (fetcher.py)
- URL discovery optimization
- HTTP pooling improvements
- Concurrent request handling

**Timeline**: 3-4 weeks
**Expected Speedup**: 2-5x
**Complexity**: Medium (async Rust, HTTP)

### Phase 4: System-Wide Benefits
**Priority 4: End-to-End Service**
- CLI binary in Rust (optional)
- Microservice architecture
- API server with Rust backend

---

## 8. SPECIFIC RUST OPTIMIZATION POINTS

### Hot Paths (Instrument These First)
```python
# transformer.py - Line 182-226 (Vector averaging)
def _vector_average_direction(...)
    → Bottleneck: 5 trig functions per record

# transformer.py - Line 331-371 (Window grouping)
def _get_latest_5min_window(...)
    → Bottleneck: datetime parsing per record

# stations.py - Line 266-274 (Distance calc)
def get_nearest_station(...)
    → Bottleneck: 110 Haversine calculations

# stations.py - Line 224-237 (Fuzzy match)
def get_station_by_name(...)
    → Bottleneck: Multiple string comparisons

# main.py - Line 183-192 (Batch processing)
for station_id in station_ids:
    → Bottleneck: Sequential transformation
```

### Rust Module Structure Recommendation
```
imeteo-stations-core/
├── src/
│   ├── aggregation.rs         # Data aggregation engine
│   ├── station_db.rs          # Station database with spatial index
│   ├── url_discovery.rs       # URL finding and HTTP ops
│   ├── timezone.rs            # Fast timezone calculations
│   └── lib.rs                 # PyO3 bindings
├── Cargo.toml
└── tests/

Python wrapper:
├── src/rust_bindings.py       # PyO3 FFI
└── tests/test_rust_integration.py
```

---

## 9. EXPECTED OVERALL PERFORMANCE GAINS

### Baseline (Current Python)
- **fetch(single_station)**: ~2-5s (includes network)
- **fetch_all(95 stations)**: ~60-120s sequential
- **search_station(name)**: 10-50ms
- **nearest_station(lat,lon)**: 20-100ms

### With Tier 1+2 Rust Optimizations
- **fetch(single_station)**: ~1-2s (network bound)
- **fetch_all(95 stations)**: ~15-30s (with parallel transforms)
- **search_station(name)**: 1-5ms (5-10x speedup)
- **nearest_station(lat,lon)**: 2-5ms (10-50x speedup)
- **Overall Throughput**: 3-8x improvement

### Bottleneck Shifts (After Optimization)
- Current: CPU-bound (aggregation, distance calc)
- Future: I/O-bound (HTTP requests, disk)
- Final Limiting Factor: SHMU API response time

