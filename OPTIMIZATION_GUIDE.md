# iMeteo Stations - Rust Optimization Guide

## Documentation Overview

This directory contains comprehensive analysis and guidance for optimizing the iMeteo Stations application with Rust. Start here to understand what to read next.

### Document Map

```
OPTIMIZATION_GUIDE.md  ← You are here
├── QUICK_REFERENCE.md         [5 min read] Quick facts & code hotspots
├── CODEBASE_ANALYSIS.md       [30 min read] Deep technical analysis
└── RUST_OPTIMIZATION_ROADMAP.md [20 min read] Implementation plan
```

---

## Quick Start (5 Minutes)

**New to this project?** Read this first:

1. **What is iMeteo Stations?**
   - Weather data aggregator for Slovak SHMU stations
   - Transforms data to OpenWeatherMap format
   - CLI tool + Docker container
   - 2,163 lines of Python code, 5 modules

2. **Why Optimize?**
   - **Current bottleneck**: CPU-bound operations (not I/O)
   - **Potential gain**: 3-8x overall performance improvement
   - **Key metrics**:
     - fetch-all: 60-120s → 15-30s
     - search: 10-50ms → 1-5ms  
     - nearest: 20-100ms → 2-5ms

3. **Quick Wins (Top 3 Bottlenecks)**
   - Batch sequential processing (3-5x)
   - Vector wind averaging (5-10x)
   - Distance calculations (10-50x)

**Next Step**: Read `QUICK_REFERENCE.md`

---

## For Developers (30 Minutes)

**Want to understand the code structure?** Read in this order:

### Step 1: Architecture (5 min)
- Read: QUICK_REFERENCE.md → "Codebase at a Glance"
- Understand: 5 main modules and their responsibilities

### Step 2: Bottlenecks (10 min)
- Read: QUICK_REFERENCE.md → "Code Hotspots for Profiling"
- Understand: Where time is spent (line numbers)
- Tools: cProfile, flamegraph for verification

### Step 3: Deep Dive (15 min)
- Read: CODEBASE_ANALYSIS.md → Sections 3 & 4
- Understand: 8 specific performance issues
- Code: Review actual Python implementations

---

## For Architects (45 Minutes)

**Planning a Rust rewrite?** Follow this path:

### Phase 1: Understanding (20 min)
- Read: CODEBASE_ANALYSIS.md (complete)
- Map: Data structures, functions, dependencies
- Ask: Where is time really spent?

### Phase 2: Strategy (15 min)
- Read: RUST_OPTIMIZATION_ROADMAP.md → Sections 1-3
- Understand: 4-phase implementation plan
- Prioritize: Which modules to tackle first

### Phase 3: Planning (10 min)
- Read: RUST_OPTIMIZATION_ROADMAP.md → Sections 4-7
- Risk assessment: Compatibility, testing, distribution
- Resource estimation: Timeline, budget, tooling

---

## For Performance Engineers (60 Minutes)

**Want detailed performance analysis?** Deep dive:

### 1. Current Baselines (15 min)
- Read: CODEBASE_ANALYSIS.md → Section 4
- Identify: 8 specific bottlenecks with line numbers
- Prioritize: Order by impact vs complexity

### 2. Measurement Plan (15 min)
- Tool: cProfile (Python built-in profiling)
- Benchmark: pytest-benchmark for tests
- Visualize: flamegraph, speedscope
- See: QUICK_REFERENCE.md → "Code Hotspots"

### 3. Rust Migration (20 min)
- Read: RUST_OPTIMIZATION_ROADMAP.md → Section 7
- Understand: PyO3 integration strategy
- Review: Type mapping, FFI boundaries

### 4. Validation (10 min)
- Strategy: Before/after benchmarks
- Testing: Integration tests to verify correctness
- Metrics: Performance targets in QUICK_REFERENCE.md

---

## Module-by-Module Analysis

### 🔴 Priority 1: transformer.py (686 lines) - **5-10x potential**

**Bottlenecks**:
1. Vector wind averaging (lines 182-226) - 5 trig ops per record
2. 5-minute window grouping (lines 331-371) - DateTime parsing

**What to Optimize**:
- `_vector_average_direction()` - Use Rust math
- `_get_latest_5min_window()` - Chronos date handling
- `aggregate_field()` - Vectorized aggregation

**Rust Approach**: 
- Standalone Rust module: `aggregation.rs`
- Expose via PyO3: `aggregate_records(data, station_id) → dict`

**Testing**:
- Test exact numeric output matches Python
- Benchmark aggregation speed
- Test all aggregation strategies (LAST, SUM, MEAN, etc.)

---

### 🔴 Priority 2: stations.py (414 lines) - **10-50x potential**

**Bottlenecks**:
1. Haversine distance loop (lines 307-333) - 110 stations per query
2. Fuzzy matching (lines 224-237) - Multiple passes

**What to Optimize**:
- `get_nearest_station()` - Use spatial indexing
- `get_stations_in_radius()` - KD-tree lookup
- `get_station_by_name()` - Levenshtein distance

**Rust Approach**:
- Spatial index: KD-tree or R-tree
- String similarity: strsim crate
- In-memory database: Serialize on load

**Testing**:
- Validate KD-tree returns same nearest station
- Test radius searches against brute-force
- Benchmark fuzzy matching

---

### 🟠 Priority 3: fetcher.py (469 lines) - **2-3x potential**

**Bottlenecks**:
1. URL discovery (lines 94-157) - HTML regex parsing
2. Parallel fetch coordination - Timeout handling

**What to Optimize**:
- `_discover_available_files()` - HTML parser
- URL construction - Validation
- Directory listing - Cache strategy

**Rust Approach**:
- HTML parsing: nom or regex crate
- HTTP handling: Keep in Python (asyncio works)
- Caching: In-memory with TTL

**Testing**:
- Test HTML parsing with actual SHMU responses
- Verify file discovery logic
- Cache hit rates

---

### ✓ Priority 4: main.py (424 lines) - **Keep as-is**

**Why**: CLI interface logic, not performance-critical

**Changes Needed**: Only integration points:
- Import Rust modules via PyO3
- Call Rust functions instead of Python
- Handle exceptions properly

---

### ✓ Priority 5: time_utils.py (168 lines) - **Maybe optimize**

**Current**: Datetime operations for 8 time windows

**If Optimizing**:
- Use chrono for faster date math
- Pre-compute DST transitions
- Bulk window generation

**Complexity**: Medium (datetime handling tricky)

---

## Performance Targets

### Current Baseline (Must measure!)

```bash
# Profile single fetch
python -m cProfile -s cumulative \
  -m src.main fetch --station-id 11816

# Profile batch operation  
python -m cProfile -s cumulative \
  -m src.main fetch-all --limit 95

# Expected output analysis:
# - Look for cumulative time
# - Identify top 5 functions
# - Compare against CODEBASE_ANALYSIS.md
```

### Target Metrics (After Optimization)

| Operation | Current | Target | Approach |
|-----------|---------|--------|----------|
| Aggregate 5 records | 10ms | 1ms | Rust math |
| Find nearest (110 stations) | 50ms | 2ms | KD-tree |
| Fuzzy search (110 stations) | 30ms | 3ms | Levenshtein |
| Discover URLs | 100ms | 30ms | nom parser |
| Transform all 95 stations | 50s | 5s | Parallel |

---

## Testing & Validation Strategy

### Pre-Optimization (Baseline)

```python
# Create benchmark suite
pytest tests/ --benchmark --benchmark-save=baseline

# Profile critical functions
cProfile.run('transformer.process_station_data(...)')

# Measure specific hotspots
import timeit
timeit.timeit(vector_avg_direction, number=1000)
```

### Post-Optimization (Validation)

```python
# Unit tests must pass 100%
pytest tests/ -v --tb=short

# Integration tests (Python ↔ Rust)
pytest tests/test_rust_bindings.py -v

# Performance comparison
pytest tests/ --benchmark --benchmark-compare=baseline

# Expected: each optimization shows target speedup
```

### Correctness Verification

1. **Numeric Accuracy**
   - Compare Rust output vs Python (float precision)
   - Check aggregation strategies match exactly
   - Validate JSON schema

2. **Edge Cases**
   - Empty data sets
   - Missing fields
   - Invalid timestamps
   - Boundary conditions

3. **Integration Points**
   - PyO3 type conversion
   - Error handling across boundary
   - Memory management

---

## Development Workflow

### Setup

```bash
# Install Rust (if needed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Add Rust Python support
cargo install maturin  # PyO3 build tool

# Python dev dependencies
pip install -e ".[dev]"
```

### Build & Test Loop

```bash
# Rust
cargo build --release
cargo test

# Python  
pytest tests/ -v

# Integration
python -c "from imeteo_core import aggregate_records"

# Benchmark
cargo bench
pytest tests/ --benchmark
```

---

## Risk Mitigation Checklist

### Before You Start
- [ ] Baseline performance measurements recorded
- [ ] Test suite passes 100%
- [ ] Documentation reviewed
- [ ] Team aligned on priorities

### During Development
- [ ] Each module tested independently
- [ ] Integration tests passing
- [ ] Performance improvements verified
- [ ] Type safety maintained

### Before Production
- [ ] All edge cases handled
- [ ] Error messages informative
- [ ] Documentation updated
- [ ] Gradual rollout planned

---

## Common Pitfalls to Avoid

| Pitfall | Solution |
|---------|----------|
| Breaking Python API | Keep interface unchanged |
| Complex FFI | Design simple PyO3 boundaries |
| Missing tests | Test all code paths before/after |
| Type mismatches | Create comprehensive type mappings |
| Performance regressions | Benchmark continuously |
| Dependency bloat | Use minimal Rust crates |

---

## Documentation Files Summary

### QUICK_REFERENCE.md (7.7 KB)
- **What**: One-page reference guide
- **Best For**: Quick lookup, code hotspots
- **Read Time**: 5-10 minutes
- **Contains**: Architecture, bottlenecks, code locations

### CODEBASE_ANALYSIS.md (16 KB)  
- **What**: Complete technical analysis
- **Best For**: Understanding entire system
- **Read Time**: 30-45 minutes
- **Contains**: All 8 bottlenecks, recommendations, metrics

### RUST_OPTIMIZATION_ROADMAP.md (8.3 KB)
- **What**: Implementation plan & strategy
- **Best For**: Project planning, architecture decisions
- **Read Time**: 20-30 minutes
- **Contains**: Phases, timeline, risks, resources

### OPTIMIZATION_GUIDE.md (This file)
- **What**: Navigation & reading guide
- **Best For**: Where to start, what to read
- **Read Time**: 10-15 minutes

---

## Quick Links

- **Source Code**: `/home/user/imeteo-stations/src/`
- **Tests**: `/home/user/imeteo-stations/tests/`
- **Config**: `/home/user/imeteo-stations/pyproject.toml`

---

## Getting Help

1. **Understand Bottlenecks**: Read CODEBASE_ANALYSIS.md Section 4
2. **See Code Hotspots**: Read QUICK_REFERENCE.md "Code Hotspots"
3. **Plan Implementation**: Read RUST_OPTIMIZATION_ROADMAP.md
4. **Integration Questions**: See QUICK_REFERENCE.md "Integration Points"

---

## Next Actions

### If You're...

**Learning about the project**:
1. Read QUICK_REFERENCE.md
2. Review architecture in CODEBASE_ANALYSIS.md
3. Identify one hotspot to measure

**Planning the optimization**:
1. Read RUST_OPTIMIZATION_ROADMAP.md
2. Create detailed project timeline
3. Allocate development resources

**Starting implementation**:
1. Choose Priority 1 module (transformer.py)
2. Create Rust crate with PyO3 bindings
3. Implement aggregation functions
4. Run benchmarks vs Python

**Debugging performance**:
1. Use cProfile to measure baseline
2. Compare against CODEBASE_ANALYSIS.md
3. Identify misaligned expectations
4. Create targeted benchmarks

---

## Document Generation Info

**Created**: 2025-11-07
**For Project**: iMeteo Stations (Slovak Weather Data Fetcher)
**Python LOC**: 2,163 (5 modules)
**Documentation**: ~1,300 lines
**Estimated Read Time**: 1.5-2 hours (complete)
**Time to Implement**: 12-16 weeks

---

**Start Here**: Read QUICK_REFERENCE.md (5 minutes)
**Then Read**: CODEBASE_ANALYSIS.md (30 minutes)
**Finally**: RUST_OPTIMIZATION_ROADMAP.md (20 minutes)

Good luck with the optimization!
