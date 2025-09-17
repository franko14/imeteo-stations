"""Station metadata and mapping utilities for Slovak weather stations."""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pydantic import BaseModel
import math


@dataclass(frozen=True)
class StationInfo:
    """Information about a weather station."""
    id: str
    name: str
    latitude: float
    longitude: float
    elevation: int  # meters above sea level


class StationNotFoundError(Exception):
    """Station not found in database."""
    pass


# Complete mapping of Slovak weather stations from SHMU
# Source: prompt.md lines 94-191
STATIONS_DATA = [
    ('664', 'Malinec-priehrada', 48.518056, 19.662778, 370),
    ('11800', 'Holíč', 48.812222, 17.163611, 180),
    ('11801', 'Kuchyňa - Nový Dvor', 48.401389, 17.147778, 206),
    ('11803', 'Trenčín', 48.86638889, 17.99944444, 303),
    ('11805', 'Senica', 48.68915, 17.403094, 232),
    ('11806', 'Myjava', 48.75333333, 17.56027778, 349),
    ('11808', 'Veľké Leváre', 48.519167, 16.984722, 152),
    ('11810', 'Bratislava-Mlynská dolina', 48.152222, 17.070278, 182),
    ('11811', 'Stupava', 48.28, 17.025833, 179),
    ('11812', 'Malý Javorník', 48.255743, 17.152589, 586),
    ('11813', 'Bratislava - Koliba', 48.16777778, 17.10583333, 286),
    ('11815', 'Slovenský Grob', 48.260417, 17.277434, 141),
    ('11816', 'Bratislava - letisko', 48.17027778, 17.2075, 133),
    ('11817', 'Kráľová pri Senci', 48.198208, 17.513472, 124),
    ('11818', 'Gabčíkovo', 47.897736, 17.566213, 113),
    ('11819', 'Jaslovské Bohunice', 48.48611111, 17.66388889, 176),
    ('11820', 'Žihárec', 48.070327, 17.881963, 112),
    ('11826', 'Piešťany', 48.613056, 17.832778, 163),
    ('11828', 'Trenčianske Teplice', 48.908889, 18.172222, 282),
    ('11833', 'Modra - Piesok', 48.37277778, 17.27388889, 531),
    ('11835', 'Moravský Svätý Ján', 48.58166667, 16.99416667, 155),
    ('11838', 'Kamanová', 48.47027778, 18.10277778, 350),
    ('11839', 'Uhrovec', 48.741415, 18.341417, 280),
    ('11841', 'Dolný Hričov', 49.231944, 18.617778, 309),
    ('11846', 'Veľké Ripňany', 48.510556, 17.990556, 188),
    ('11847', 'Topoľčany', 48.563889, 18.156111, 180),
    ('11849', 'Žikava', 48.458611, 18.390278, 318),
    ('11850', 'Podhájska', 48.1075, 18.339167, 140),
    ('11855', 'Nitra - Velké Janíkovce', 48.280556, 18.135556, 135),
    ('11856', 'Mochovce', 48.289444, 18.456111, 261),
    ('11857', 'Turzovka', 49.401564, 18.626783, 520),
    ('11858', 'Hurbanovo', 47.873333, 18.194444, 115),
    ('11862', 'Beluša', 49.066111, 18.318056, 254),
    ('11865', 'Žilina', 49.205278, 18.746667, 365),
    ('11866', 'Čadca', 49.436111, 18.765833, 456),
    ('11867', 'Prievidza', 48.769722, 18.593889, 260),
    ('11868', 'Oravská Lesná', 49.368333, 19.183056, 780),
    ('11869', 'Rabča', 49.479167, 19.485, 642),
    ('11872', 'Ružomberok', 49.079167, 19.307778, 471),
    ('11874', 'Liptovský Hrádok', 49.039167, 19.725278, 640),
    ('11876', 'Podbanské', 49.14, 19.910556, 972),
    ('11878', 'Liptovský Mikuláš - Ondrašová', 49.097778, 19.592222, 569),
    ('11879', 'Kremnické Bane', 48.735833, 18.91, 758),
    ('11880', 'Dudince', 48.169167, 18.876111, 139),
    ('11881', 'Želiezovce', 48.049444, 18.660833, 137),
    ('11882', 'Tesárske Mlyňany', 48.3225, 18.369444, 196),
    ('11883', 'Veľké Lovce', 48.056087, 18.335425, 200),
    ('11884', 'Mužla', 47.800456, 18.595672, 130),
    ('11890', 'Oravské Veselé', 49.471389, 19.385, 760),
    ('11892', 'Oravský Podzamok', 49.2625, 19.371111, 532),
    ('11894', 'Donovaly', 48.875067, 19.223514, 960),
    ('11893', 'Martin MS', 49.068333, 18.935833, 411),
    ('11897', 'Turčianske Teplice', 48.86, 18.860278, 522),
    ('11898', 'Banská Bystrica-Zelená', 48.733611, 19.116944, 427),
    ('11900', 'Žiar nad Hronom', 48.586111, 18.852222, 275),
    ('11901', 'Banská Štiavnica', 48.449444, 18.921667, 575),
    ('11902', 'Bzovík', 48.319167, 19.093889, 355),
    ('11903', 'Sliač', 48.6425, 19.141944, 313),
    ('11904', 'Vígľaš Pstruša', 48.544167, 19.321944, 368),
    ('11905', 'Dolné Plachtince', 48.206667, 19.32, 228),
    ('11908', 'Liptovská Osada', 48.949722, 19.216111, 605),
    ('11910', 'Lom nad Rimavicou', 48.644167, 19.650833, 1018),
    ('11916', 'Chopok', 48.943889, 19.592222, 2005),
    ('11917', 'Brezno', 48.801667, 19.637222, 487),
    ('11918', 'Liesek', 49.369444, 19.679444, 692),
    ('11919', 'Oravice', 49.29972222, 19.75166667, 780),
    ('11926', 'Málinec', 48.518275, 19.661455, 370),
    ('11927', 'Boľkovce', 48.338889, 19.736389, 214),
    ('11930', 'Lomnicky Štít', 49.195278, 20.215, 2635),
    ('11931', 'Skalnaté Pleso', 49.189444, 20.234444, 1778),
    ('11933', 'Štrbské Pleso', 49.119444, 20.063333, 1322),
    ('11934', 'Poprad', 49.068889, 20.245556, 694),
    ('11935', 'Tatranská Lomnica', 49.164444, 20.288056, 827),
    ('11936', 'Javorina', 49.263056, 20.143611, 1007),
    ('11938', 'Telgárt', 48.848611, 20.189167, 901),
    ('11941', 'Ratková', 48.592778, 20.093611, 311),
    ('11942', 'Rimavská Sobota', 48.373889, 20.010556, 215),
    ('11944', 'Rožňava', 48.653056, 20.5375, 311),
    ('11945', 'Švedlár', 48.811111, 20.711111, 472),
    ('11946', 'Štós-Kúpele', 48.718056, 20.7975, 580),
    ('11947', 'Moldava n.Bodvou', 48.604444, 21.001667, 218),
    ('11949', 'Spišské Vlachy', 48.943889, 20.804167, 380),
    ('11950', 'Podolínec', 49.255556, 20.532778, 573),
    ('11951', 'Červený Kláštor', 49.391667, 20.426667, 465),
    ('11952', 'Gánovce', 49.035, 20.324167, 703),
    ('11953', 'Revúca', 48.68, 20.118056, 327),
    ('11955', 'Prešov-vojsko', 49.031944, 21.308611, 307),
    ('11957', 'Stará Lesná', 49.152778, 20.291111, 808),
    ('11958', 'Kojšovská hoľa', 48.782907, 20.987029, 1240),
    ('11959', 'Tatranská Polianka', 49.121944, 20.1875, 975),
    ('11960', 'Košice-Mesto', 48.725278, 21.265, 203),
    ('11961', 'Plaveč nad Popradom', 49.259722, 20.845833, 485),
    ('11962', 'Bardejov', 49.289444, 21.273889, 305),
    ('11963', 'Jakubovany', 49.108889, 21.140833, 410),
    ('11964', 'Dubnik', 48.922778, 21.462778, 875),
    ('11966', 'Čaklov', 48.905278, 21.63, 134),
    ('11967', 'Zlatá Baňa', 48.949924, 21.420369, 875),
    ('11969', 'Košice-Podhradová', 48.753191, 21.245308, 210),
    ('11968', 'Košice - letisko', 48.672222, 21.2225, 230),
    ('11970', 'Silica', 48.553889, 20.520833, 520),
    ('11974', 'Roztoky', 49.396428, 21.492196, 320),
    ('11976', 'Tisinec', 49.215556, 21.65, 216),
    ('11977', 'Medzilaborce', 49.253333, 21.913889, 305),
    ('11978', 'Milhostov', 48.663056, 21.723889, 105),
    ('11979', 'Somotor', 48.421111, 21.819444, 100),
    ('11982', 'Michalovce', 48.74, 21.945278, 110),
    ('11984', 'Orechová', 48.705278, 22.225278, 122),
    ('11992', 'Osadné', 49.14, 22.150833, 378),
    ('11993', 'Kamenica nad Cirochou', 48.938889, 22.006111, 176),
    ('11995', 'Ruský Hrabovec', 48.625556, 22.083889, 105),
]


class StationDatabase:
    """Database of Slovak weather stations."""

    def __init__(self):
        """Initialize station database."""
        self._stations = {}
        self._name_index = {}
        self._initialize_stations()

    def _initialize_stations(self):
        """Load station data into internal structures."""
        for station_id, name, lat, lon, elevation in STATIONS_DATA:
            station = StationInfo(
                id=station_id,
                name=name,
                latitude=lat,
                longitude=lon,
                elevation=elevation
            )
            self._stations[station_id] = station

            # Create name index for fuzzy matching
            normalized_name = self._normalize_name(name)
            self._name_index[normalized_name] = station_id

            # Also index without diacritics for easier searching
            ascii_name = self._remove_diacritics(name)
            if ascii_name != normalized_name:
                self._name_index[ascii_name] = station_id

    def _normalize_name(self, name: str) -> str:
        """Normalize station name for comparison."""
        return name.lower().strip()

    def _remove_diacritics(self, name: str) -> str:
        """Remove Slovak diacritics for ASCII searching."""
        replacements = {
            'á': 'a', 'ä': 'a', 'č': 'c', 'ď': 'd', 'é': 'e',
            'í': 'i', 'ĺ': 'l', 'ľ': 'l', 'ň': 'n', 'ó': 'o',
            'ô': 'o', 'ŕ': 'r', 'š': 's', 'ť': 't', 'ú': 'u',
            'ý': 'y', 'ž': 'z'
        }
        result = name.lower()
        for diacritic, ascii_char in replacements.items():
            result = result.replace(diacritic, ascii_char)
        return result

    def get_station_by_id(self, station_id: str) -> StationInfo:
        """
        Get station information by ID.

        Args:
            station_id: Station ID (e.g., "11816")

        Returns:
            StationInfo object

        Raises:
            StationNotFoundError: If station ID is not found
        """
        if station_id not in self._stations:
            raise StationNotFoundError(f"Station ID '{station_id}' not found")
        return self._stations[station_id]

    def get_station_by_name(self, name: str) -> StationInfo:
        """
        Get station information by name (fuzzy matching).

        Args:
            name: Station name (partial matches allowed)

        Returns:
            StationInfo object

        Raises:
            StationNotFoundError: If no matching station is found
        """
        normalized_name = self._normalize_name(name)

        # Try exact match first
        if normalized_name in self._name_index:
            station_id = self._name_index[normalized_name]
            return self._stations[station_id]

        # Try partial matches
        matching_stations = []
        for indexed_name, station_id in self._name_index.items():
            if normalized_name in indexed_name or indexed_name in normalized_name:
                matching_stations.append(self._stations[station_id])

        if not matching_stations:
            # Try even more fuzzy matching
            for indexed_name, station_id in self._name_index.items():
                # Check if most words match
                name_words = set(normalized_name.split())
                indexed_words = set(indexed_name.split())
                if name_words & indexed_words:  # At least one word in common
                    matching_stations.append(self._stations[station_id])

        if not matching_stations:
            raise StationNotFoundError(f"No station found matching '{name}'")

        if len(matching_stations) == 1:
            return matching_stations[0]

        # Multiple matches - return the best one (shortest name difference)
        best_match = min(
            matching_stations,
            key=lambda s: abs(len(s.name) - len(name))
        )
        return best_match

    def get_nearest_station(self, latitude: float, longitude: float) -> StationInfo:
        """
        Find the nearest station to given coordinates.

        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees

        Returns:
            StationInfo of nearest station
        """
        min_distance = float('inf')
        nearest_station = None

        for station in self._stations.values():
            distance = self._calculate_distance(
                latitude, longitude,
                station.latitude, station.longitude
            )

            if distance < min_distance:
                min_distance = distance
                nearest_station = station

        if nearest_station is None:
            raise StationNotFoundError("No stations available")

        return nearest_station

    def _calculate_distance(self, lat1: float, lon1: float,
                           lat2: float, lon2: float) -> float:
        """
        Calculate distance between two points using Haversine formula.

        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates

        Returns:
            Distance in kilometers
        """
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = (math.sin(dlat/2)**2 +
             math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2)
        c = 2 * math.asin(math.sqrt(a))

        # Earth's radius in kilometers
        r = 6371
        return c * r

    def get_stations_in_radius(self, latitude: float, longitude: float,
                              radius_km: float) -> List[StationInfo]:
        """
        Get all stations within specified radius.

        Args:
            latitude: Center latitude
            longitude: Center longitude
            radius_km: Radius in kilometers

        Returns:
            List of stations within radius, sorted by distance
        """
        stations_in_radius = []

        for station in self._stations.values():
            distance = self._calculate_distance(
                latitude, longitude,
                station.latitude, station.longitude
            )

            if distance <= radius_km:
                stations_in_radius.append((station, distance))

        # Sort by distance
        stations_in_radius.sort(key=lambda x: x[1])
        return [station for station, _ in stations_in_radius]

    def get_all_stations(self) -> List[StationInfo]:
        """
        Get list of all available stations.

        Returns:
            List of all StationInfo objects
        """
        return list(self._stations.values())

    def get_station_count(self) -> int:
        """
        Get total number of stations.

        Returns:
            Number of stations in database
        """
        return len(self._stations)

    def search_stations(self, query: str) -> List[StationInfo]:
        """
        Search stations by name query.

        Args:
            query: Search query

        Returns:
            List of matching stations, sorted by relevance
        """
        query_normalized = self._normalize_name(query)
        matching_stations = []

        for station in self._stations.values():
            station_name = self._normalize_name(station.name)

            # Calculate relevance score
            if query_normalized == station_name:
                score = 100  # Exact match
            elif query_normalized in station_name:
                score = 80  # Substring match
            elif station_name in query_normalized:
                score = 70  # Query contains station name
            else:
                # Check word overlap
                query_words = set(query_normalized.split())
                station_words = set(station_name.split())
                overlap = len(query_words & station_words)
                if overlap > 0:
                    score = 50 + (overlap * 10)
                else:
                    continue  # No match

            matching_stations.append((station, score))

        # Sort by score (highest first)
        matching_stations.sort(key=lambda x: x[1], reverse=True)
        return [station for station, _ in matching_stations]


# Global station database instance
stations_db = StationDatabase()


# Convenience functions
def get_station_by_id(station_id: str) -> StationInfo:
    """Get station by ID."""
    return stations_db.get_station_by_id(station_id)


def get_station_by_name(name: str) -> StationInfo:
    """Get station by name."""
    return stations_db.get_station_by_name(name)


def get_nearest_station(latitude: float, longitude: float) -> StationInfo:
    """Get nearest station to coordinates."""
    return stations_db.get_nearest_station(latitude, longitude)


def search_stations(query: str) -> List[StationInfo]:
    """Search stations by query."""
    return stations_db.search_stations(query)