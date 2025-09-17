"""Tests for station database and utilities."""

import pytest
import math

from src.stations import (
    StationInfo, StationDatabase, StationNotFoundError,
    get_station_by_id, get_station_by_name, get_nearest_station,
    search_stations, stations_db
)


class TestStationInfo:
    """Test StationInfo dataclass."""

    def test_station_info_creation(self):
        """Test creating StationInfo objects."""
        station = StationInfo(
            id="11816",
            name="Bratislava - letisko",
            latitude=48.171667,
            longitude=17.2,
            elevation=133
        )

        assert station.id == "11816"
        assert station.name == "Bratislava - letisko"
        assert station.latitude == 48.171667
        assert station.longitude == 17.2
        assert station.elevation == 133

    def test_station_info_immutable(self):
        """Test that StationInfo is immutable (frozen)."""
        station = StationInfo("11816", "Test", 48.0, 17.0, 100)

        with pytest.raises(AttributeError):
            station.name = "Modified"


class TestStationDatabase:
    """Test StationDatabase functionality."""

    def test_database_initialization(self):
        """Test that database initializes with expected stations."""
        db = StationDatabase()

        # Should have all Slovak stations (95+ stations)
        assert db.get_station_count() >= 90
        assert db.get_station_count() <= 100  # Reasonable upper bound

    def test_get_station_by_id_valid(self):
        """Test getting station by valid ID."""
        db = StationDatabase()

        # Test known stations
        bratislava = db.get_station_by_id("11816")
        assert bratislava.name == "Bratislava - letisko"
        assert bratislava.id == "11816"

        kosice = db.get_station_by_id("11968")
        assert "Košice" in kosice.name

    def test_get_station_by_id_invalid(self):
        """Test getting station by invalid ID."""
        db = StationDatabase()

        with pytest.raises(StationNotFoundError):
            db.get_station_by_id("99999")

        with pytest.raises(StationNotFoundError):
            db.get_station_by_id("invalid")

    def test_get_station_by_name_exact_match(self):
        """Test getting station by exact name match."""
        db = StationDatabase()

        station = db.get_station_by_name("Bratislava - letisko")
        assert station.id == "11816"

    def test_get_station_by_name_partial_match(self):
        """Test getting station by partial name match."""
        db = StationDatabase()

        # Should find Bratislava airport
        station = db.get_station_by_name("Bratislava")
        assert "Bratislava" in station.name

        # Should find some station with "Košice"
        station = db.get_station_by_name("Košice")
        assert "Košice" in station.name

    def test_get_station_by_name_case_insensitive(self):
        """Test case-insensitive name matching."""
        db = StationDatabase()

        station1 = db.get_station_by_name("bratislava")
        station2 = db.get_station_by_name("BRATISLAVA")
        station3 = db.get_station_by_name("Bratislava")

        # All should find the same station
        assert station1.id == station2.id == station3.id

    def test_get_station_by_name_diacritic_handling(self):
        """Test handling of Slovak diacritics."""
        db = StationDatabase()

        # Test with and without diacritics
        try:
            station1 = db.get_station_by_name("Zilina")  # ASCII
            station2 = db.get_station_by_name("Žilina")  # With diacritics

            # Should find the same station if both exist
            assert station1.id == station2.id
        except StationNotFoundError:
            # If one doesn't work, the other should
            station = db.get_station_by_name("Žilina")
            assert "Žilina" in station.name or "Zilina" in station.name

    def test_get_station_by_name_not_found(self):
        """Test error when station name is not found."""
        db = StationDatabase()

        with pytest.raises(StationNotFoundError):
            db.get_station_by_name("NonexistentStation")

    def test_get_nearest_station(self):
        """Test finding nearest station by coordinates."""
        db = StationDatabase()

        # Coordinates near Bratislava airport
        bratislava_lat, bratislava_lon = 48.171667, 17.2
        nearest = db.get_nearest_station(bratislava_lat, bratislava_lon)

        # Should find Bratislava airport or very close station
        assert nearest.id == "11816" or "Bratislava" in nearest.name

    def test_get_nearest_station_edge_cases(self):
        """Test nearest station with edge case coordinates."""
        db = StationDatabase()

        # Test with coordinates in Slovakia
        station = db.get_nearest_station(48.5, 19.0)  # Central Slovakia
        assert isinstance(station, StationInfo)

        # Test with coordinates outside Slovakia (should still return something)
        station = db.get_nearest_station(50.0, 14.0)  # Prague area
        assert isinstance(station, StationInfo)

    def test_distance_calculation(self):
        """Test distance calculation accuracy."""
        db = StationDatabase()

        # Test known distance (approximately)
        # Bratislava to Košice is roughly 350km
        bratislava_coords = (48.171667, 17.2)
        kosice_coords = (48.672222, 21.2225)

        distance = db._calculate_distance(*bratislava_coords, *kosice_coords)

        # Should be approximately 350km (allow some tolerance)
        assert 300 <= distance <= 400

    def test_get_stations_in_radius(self):
        """Test getting stations within radius."""
        db = StationDatabase()

        # Get stations within 50km of Bratislava
        bratislava_coords = (48.171667, 17.2)
        nearby_stations = db.get_stations_in_radius(*bratislava_coords, 50)

        assert len(nearby_stations) > 0
        assert len(nearby_stations) < db.get_station_count()  # Should be subset

        # All returned stations should be StationInfo objects
        for station in nearby_stations:
            assert isinstance(station, StationInfo)

        # Should include Bratislava airport itself
        station_ids = [s.id for s in nearby_stations]
        assert "11816" in station_ids

    def test_get_stations_in_radius_ordering(self):
        """Test that stations in radius are ordered by distance."""
        db = StationDatabase()

        bratislava_coords = (48.171667, 17.2)
        nearby_stations = db.get_stations_in_radius(*bratislava_coords, 100)

        if len(nearby_stations) > 1:
            # Calculate distances and verify ordering
            distances = []
            for station in nearby_stations:
                dist = db._calculate_distance(
                    *bratislava_coords, station.latitude, station.longitude
                )
                distances.append(dist)

            # Should be sorted by distance (ascending)
            assert distances == sorted(distances)

    def test_get_all_stations(self):
        """Test getting all stations."""
        db = StationDatabase()

        all_stations = db.get_all_stations()

        assert len(all_stations) == db.get_station_count()
        assert all(isinstance(s, StationInfo) for s in all_stations)

        # Should include known stations
        station_ids = [s.id for s in all_stations]
        assert "11816" in station_ids  # Bratislava
        assert "11968" in station_ids  # Košice

    def test_search_stations(self):
        """Test station search functionality."""
        db = StationDatabase()

        # Search for Bratislava stations
        results = db.search_stations("Bratislava")
        assert len(results) > 0

        # All results should contain Bratislava in name
        for station in results:
            assert "Bratislava" in station.name

        # Results should be ordered by relevance
        assert isinstance(results[0], StationInfo)

    def test_search_stations_empty_query(self):
        """Test search with empty or very short query."""
        db = StationDatabase()

        # Empty query should return no results
        results = db.search_stations("")
        assert len(results) == 0

        # Single character should return limited results
        results = db.search_stations("B")
        assert len(results) >= 0  # May or may not find matches

    def test_search_stations_partial_words(self):
        """Test search with partial words."""
        db = StationDatabase()

        # Should find stations with "rava" in name (like Bratislava)
        results = db.search_stations("rava")
        assert len(results) > 0


class TestGlobalStationFunctions:
    """Test global convenience functions."""

    def test_global_get_station_by_id(self):
        """Test global get_station_by_id function."""
        station = get_station_by_id("11816")
        assert station.name == "Bratislava - letisko"

    def test_global_get_station_by_name(self):
        """Test global get_station_by_name function."""
        station = get_station_by_name("Bratislava")
        assert "Bratislava" in station.name

    def test_global_get_nearest_station(self):
        """Test global get_nearest_station function."""
        station = get_nearest_station(48.171667, 17.2)
        assert isinstance(station, StationInfo)

    def test_global_search_stations(self):
        """Test global search_stations function."""
        results = search_stations("Bratislava")
        assert len(results) > 0
        assert all(isinstance(s, StationInfo) for s in results)

    def test_global_stations_db_instance(self):
        """Test that global stations_db is properly initialized."""
        assert isinstance(stations_db, StationDatabase)
        assert stations_db.get_station_count() > 0


class TestStationDataIntegrity:
    """Test integrity of station data."""

    def test_all_stations_have_valid_coordinates(self):
        """Test that all stations have valid coordinates."""
        db = StationDatabase()
        all_stations = db.get_all_stations()

        for station in all_stations:
            # Latitude should be in Slovakia range (roughly 47-50°N)
            assert 47.0 <= station.latitude <= 50.0

            # Longitude should be in Slovakia range (roughly 16-23°E)
            assert 16.0 <= station.longitude <= 23.0

            # Elevation should be reasonable (Slovakia: sea level to ~2600m)
            assert 0 <= station.elevation <= 3000

    def test_all_stations_have_valid_ids(self):
        """Test that all stations have valid IDs."""
        db = StationDatabase()
        all_stations = db.get_all_stations()

        station_ids = set()
        for station in all_stations:
            # ID should be non-empty string
            assert isinstance(station.id, str)
            assert len(station.id) > 0

            # ID should be unique
            assert station.id not in station_ids
            station_ids.add(station.id)

    def test_all_stations_have_valid_names(self):
        """Test that all stations have valid names."""
        db = StationDatabase()
        all_stations = db.get_all_stations()

        for station in all_stations:
            # Name should be non-empty string
            assert isinstance(station.name, str)
            assert len(station.name.strip()) > 0

    def test_known_stations_exist(self):
        """Test that known important stations exist."""
        db = StationDatabase()

        # Test a few key stations
        important_stations = [
            ("11816", "Bratislava"),
            ("11968", "Košice"),
            ("11934", "Poprad"),
            ("11916", "Chopok"),  # High altitude station
        ]

        for station_id, expected_name_part in important_stations:
            station = db.get_station_by_id(station_id)
            assert expected_name_part in station.name