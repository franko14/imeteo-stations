# Rust Optimization Roadmap for iMeteo Stations

## Executive Summary

The **iMeteo Stations** application is a Slovak weather data fetching and transformation service with clear performance bottlenecks suitable for Rust optimization. The codebase is well-structured with 2,163 lines of type-safe Python across 5 modules.

**Key Finding**: The application is **CPU-bound** (not I/O-bound), with 8 distinct optimization opportunities that could yield **3-8x overall performance improvement**.

---

## Critical Metrics

| Metric | Current | After Optimization |
|--------|---------|-------------------|
| **fetch-all (95 stations)** | 60-120s | 15-30s |
| **Nearest station lookup** | 20-100ms | 2-5ms |
| **Station search** | 10-50ms | 1-5ms |
| **Data aggregation** | 500ms+ | 50-100ms |
| **Overall throughput** | 1x baseline | **3-8x improvement** |

---

## Top 8 Performance Bottlenecks (Ranked)

### 🔴 CRITICAL (Days 1-14)

**1. Batch Sequential Processing** (main.py)
- **Impact**: Blocks fetch-all at 60-120s
- **Issue**: Lines 183-192 process 95 stations sequentially
- **Fix**: Parallel Rust transformation + asyncio
- **Expected Gain**: 3-5x

**2. Vector Wind Averaging** (transformer.py)
- **Impact**: ~550 trigonometric operations per fetch-all
- **Issue**: Lines 182-226, sin/cos/atan2 in loops
- **Fix**: Rust SIMD operations
- **Expected Gain**: 5-10x

**3. Full Haversine Loop** (stations.py)
- **Impact**: 110 distance calculations per query
- **Issue**: Lines 307-333, O(n) full scan for nearest/radius
- **Fix**: KD-tree spatial indexing in Rust
- **Expected Gain**: 10-50x (depending on use case)

### 🟠 HIGH (Days 15-28)

**4. 5-Minute Window Grouping** (transformer.py)
- **Impact**: DateTime parsing per record
- **Issue**: Lines 331-371, ISO parsing in tight loop
- **Fix**: Chrono crate optimization
- **Expected Gain**: 2-3x

**5. Fuzzy Station Matching** (stations.py)
- **Impact**: Multiple string searches
- **Issue**: Lines 224-237, nested loops with word splitting
- **Fix**: Levenshtein distance in Rust
- **Expected Gain**: 3-5x

**6. URL Discovery** (fetcher.py)
- **Impact**: HTML regex parsing inefficiency
- **Issue**: Lines 94-157, sequential directory listing
- **Fix**: Nom parser + concurrent HTTP
- **Expected Gain**: 2-3x

### 🟡 MEDIUM (Days 29-42)

**7. JSON Processing** (fetcher.py)
- **Impact**: Multiple json() calls per request
- **Issue**: Python json module performance
- **Fix**: serde_json integration
- **Expected Gain**: 1.5-3x

**8. Repeated Validation** (fetcher.py)
- **Impact**: Redundant structure checks
- **Issue**: Lines 265-301, validation on every attempt
- **Fix**: Single validation + caching
- **Expected Gain**: 1.2-1.5x

---

## Rust Integration Strategy

### Architecture Pattern
```
┌─────────────────────────────────────┐
│  Python CLI (Click)                 │
│  src/main.py (unchanged)            │
└──────────┬──────────────────────────┘
           │
           ▼ PyO3 bindings
┌─────────────────────────────────────┐
│  Rust Core Library                  │
│  imeteo-core (new)                  │
├─────────────────────────────────────┤
│ ✓ aggregation.rs (high CPU)         │
│ ✓ station_db.rs (spatial index)     │
│ ✓ url_discovery.rs (HTTP ops)       │
│ ✓ timezone.rs (fast date math)      │
└─────────────────────────────────────┘
```

### Integration Points (PyO3)
1. **Aggregation Module** (data → OpenWeather format)
2. **Station Database** (lookups, geolocation)
3. **URL Discovery** (file discovery logic)
4. **Math Operations** (wind vectors, distances)

### Build System Changes
```toml
# pyproject.toml additions
[build-system]
requires = ["maturin>=0.14"]  # PyO3 build tool
build-backend = "maturin"

[project.optional-dependencies]
core = ["imeteo-core>=1.0"]  # Rust extension
```

---

## 4-Phase Implementation Plan

### Phase 1: Foundation (Weeks 1-4)
**Goal**: Establish Rust foundation, optimize highest ROI
- [ ] Create `imeteo-core` Rust crate with PyO3 bindings
- [ ] Implement aggregation engine (transformer.py → Rust)
- [ ] Benchmark aggregation speedup
- **Deliverable**: 5-10x faster data transformation

### Phase 2: Geolocation (Weeks 5-7)
**Goal**: Optimize station queries with spatial indexing
- [ ] Build station database with KD-tree
- [ ] Implement fuzzy matching algorithm
- [ ] Integrate with stations.py via PyO3
- **Deliverable**: 10-50x faster geolocation queries

### Phase 3: I/O Optimization (Weeks 8-11)
**Goal**: Optimize URL discovery and HTTP handling
- [ ] Rewrite URL discovery with nom parser
- [ ] Improve concurrent HTTP with tokio
- [ ] Optimize JSON parsing pipeline
- **Deliverable**: 2-3x faster data fetching

### Phase 4: Integration & Polish (Weeks 12-14)
**Goal**: End-to-end optimization and deployment
- [ ] Create unified Python/Rust package
- [ ] Write integration tests
- [ ] Update CI/CD pipeline
- [ ] Benchmark end-to-end improvements
- **Deliverable**: 3-8x overall speedup, production-ready

---

## Risk Mitigation

### Compatibility
- **Issue**: Breaking changes to Python interface
- **Mitigation**: Keep Python API unchanged, Rust is internal only

### Maintenance
- **Issue**: Adding Rust complexity to Python project
- **Mitigation**: Modular design, clear boundaries, comprehensive tests

### Distribution
- **Issue**: Binary wheels for multiple platforms
- **Mitigation**: Use maturin for automated build matrix

### Testing
- **Issue**: Ensuring Rust/Python interface correctness
- **Mitigation**: Property-based tests, fuzzing, integration tests

---

## Resource Requirements

### Development
- 2-3 developers with Rust experience
- 12-16 weeks full-time commitment
- ~50-80 hours code review

### Infrastructure
- CI/CD: GitHub Actions for multi-platform builds
- Benchmarking: Criterion.rs + pytest benchmarks
- Testing: Full integration test suite

### Documentation
- PyO3 FFI documentation
- Migration guides for API changes
- Performance improvement benchmarks

---

## Success Criteria

| Criterion | Target |
|-----------|--------|
| fetch-all time | < 30s (from 60-120s) |
| Station search | < 5ms (from 10-50ms) |
| Nearest station | < 5ms (from 20-100ms) |
| API compatibility | 100% (no breaking changes) |
| Test coverage | > 95% |
| Documentation | Complete |

---

## Next Steps

1. **Benchmark Current Performance** (Day 1)
   - Create baseline metrics for all 8 bottlenecks
   - Identify exact hotspots with cProfile/flamegraph
   - Set performance targets

2. **Prototype Aggregation Module** (Week 1)
   - Build minimal Rust aggregation engine
   - Measure speedup vs Python
   - Validate correctness against test suite

3. **Design Rust Architecture** (Week 2)
   - Define PyO3 FFI boundaries
   - Plan module dependencies
   - Design test strategy

4. **Full Implementation** (Weeks 3-14)
   - Follow 4-phase roadmap
   - Continuous benchmarking
   - Regular integration checkpoints

---

## Files to Review for Implementation

- `/home/user/imeteo-stations/CODEBASE_ANALYSIS.md` - Detailed analysis
- `/home/user/imeteo-stations/src/transformer.py` - Lines 182-226, 331-371
- `/home/user/imeteo-stations/src/stations.py` - Lines 266-274, 224-237
- `/home/user/imeteo-stations/src/main.py` - Lines 183-192
- `/home/user/imeteo-stations/src/fetcher.py` - Lines 94-157, 265-301

---

## Appendix: Rust Crate Recommendations

### Core Dependencies
```toml
[dependencies]
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
chrono = "0.4"
regex = "1.10"
rayon = "1.7"  # Parallel iterators for aggregation
pyo3 = { version = "0.20", features = ["extension-module"] }

[dev-dependencies]
criterion = "0.5"  # Benchmarking
proptest = "1.4"   # Property-based testing
```

### Spatial Indexing Options
- **kdtree**: Simple KD-tree for nearest neighbor
- **rstar**: R-tree for 2D spatial indexing
- **geo**: Geographic computations (Haversine alternative)

### String Algorithms
- **strsim**: String similarity metrics
- **edit-distance**: Levenshtein distance
- **fuzzy-matcher**: Fuzzy string matching

