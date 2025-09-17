I want you to generate a script that will fetch data from Automatic Weather stations. The script should be lightweight and you can choose any language that fits the best for this task. I am familiar with PYthon, Go, Spark, JS.

# Source data

## Data Source
- Data is stored in json files,
- each jason file contains data for multiple stations,
- jsons are stored in 5-minute bins with 1 minute data granulariy (described in Data Schema below).

**Example:**
- it is now 16th of September 2025 in Slovakia, 18:38 CEST (16:38 UTC),
- latest json is available from 18:35 with this naming convention: "https://opendata.shmu.sk/meteorology/climate/now/data/20250916/aws1min - 2025-09-16 18-35-00-264.json" published at 16:35 UTC (18:35 CEST),

## Issues in Source Data
- file naming is in CEST time - so now when it is 18:38, then latest json is 18:35 (note the timestamp is in the file URL),
- data is stored in UTC, but it is actually UTC shifted by 1 hour. So for example we would expect the data from the example file to be between 16:30 and 16:35 UTC (18:30 - 18:35 CEST). But the timestamps show 17:30 - 17:35. So it is actually UTC, but shifted by +1 hour,

## Data Schema
- id is the unique identifier of the JSON file (UUID format)
- dataset describes the source/type of meteorological data ("Automatic stations")
- interval specifies the measurement interval ("1 minute")
- frequency indicates the data update frequency ("5 minute")
- statistics contains metadata with stations_count and records_count
- data is an array of meteorological records from automatic weather stations, each containing:
  - ind_kli - station climate index/ID
  - minuta - timestamp in ISO format (YYYY-MM-DDTHH:MM:SS)
  - t - air temperature (°C)
  - tprz - dew point temperature (°C)
  - t_pod5/10/20/50/100 - soil temperatures at depths 5/10/20/50/100 cm (°C)
  - tlak - atmospheric pressure (hPa)
  - vie_* - wind measurements (speed in m/s, direction in degrees)
  - vlh_rel - relative humidity (%)
  - zglo - global radiation (W/m²)
  - zra_* - precipitation measurements (duration, amount)
  - sln_trv - sunshine duration (minutes)
  - dohl - visibility (meters)
  - stav_poc - weather condition code
  - sneh_pokr - snow cover (cm)
  - vlh_pod* - soil moisture at various depths (%)
  - el_vod_pod* - soil electrical conductivity at various depths
  - zgama - gamma radiation (nSv/h)

## Distinct Station Analysis:
- Number of distinct stations (ind_kli): 95
- Station ID range: 11800-11995 (5-digit integer identifiers)

## Data Granularity & Types:

Temporal Granularity:
- 1-minute measurement intervals
- 5-minute data update frequency
- Timestamps in ISO 8601 format (YYYY-MM-DDTHH:MM:SS)

## Data Types by Category:

Identifiers:
- ind_kli: Integer (station climate index)
- minuta: String/DateTime (ISO timestamp)

Temperature Measurements (°C):
- t, tprz: Float (air temp, dew point) - precision to 0.1°C
- t_pod5/10/20/50/100: Float/null (soil temps at depths) - precision to 0.1°C

Atmospheric Pressure:
- tlak: Float/null (hPa) - precision to 0.1 hPa

Wind Measurements:
- Speed: Float (m/s) - precision to 0.1 m/s
- Direction: Float (degrees) - precision to 1.0°
- Multiple variants: min/max/average for both speed and direction

Humidity & Radiation:
- vlh_rel: Float (%) - precision to 0.1%
- zglo: Float/null (W/m²) - precision to 0.1 W/m²
- zgama: Float/null (nSv/h) - precision to 0.01 nSv/h

Precipitation & Weather:
- zra_trv, sln_trv: Float (minutes) - integer precision
- zra_uhrn: Float (mm) - precision to 0.1 mm
- dohl: Float/null (meters) - typically 20000.0 or null
- stav_poc: Integer/null (weather code)
- sneh_pokr: Float/null (cm) - precision to 0.1 cm

Soil Properties:
- vlh_pod*: Float/null (%) - soil moisture, precision to 0.1%
- el_vod_pod*: Float/null - electrical conductivity, precision to 0.1

Data Completeness: Many fields can be null, indicating either sensor unavailability or measurement outside valid ranges.

## Mapping of ind_kli to actual stations:

Schema is in (ind_kli, station_name, latitude, longitude, elevation)

('664', 'Malinec-priehrada', 48.518056, 19.662778, 370),
('11800', 'Holíč', 48.812222, 17.163611, 180),
('11801', 'Kuchyňa - Nový Dvor', 48.401389, 17.147778, 206),
('11803', 'Trenčín', 48.878333, 18.048333, 303),
('11805', 'Senica', 48.689444, 17.405, 232),
('11806', 'Myjava', 48.753889, 17.561667, 349),
('11808', 'Veľké Leváre', 48.519167, 16.984722, 152),
('11810', 'Bratislava-Mlynská dolina', 48.152222, 17.070278, 182),
('11811', 'Stupava', 48.28, 17.025833, 179),
('11812', 'Malý Javorník', 48.255833, 17.153889, 586),
('11813', 'Bratislava - Koliba', 48.168611, 17.110556, 286),
('11815', 'Slovenský Grob', 48.260556, 17.279722, 141),
('11816', 'Bratislava - letisko', 48.171667, 17.2, 133),
('11817', 'Kráľová pri Senci', 48.2, 17.274722, 124),
('11818', 'Gabčíkovo', 47.895833, 17.565556, 113),
('11819', 'Jaslovské Bohunice', 48.486667, 17.670833, 176),
('11820', 'Žihárec', 48.070278, 17.881944, 112),
('11826', 'Piešťany', 48.613056, 17.832778, 163),
('11828', 'Trenčianske Teplice', 48.908889, 18.172222, 282),
('11833', 'Modra - Piesok', 48.374167, 17.275833, 531),
('11835', 'Moravský Svätý Ján', 48.581667, 16.995278, 155),
('11841', 'Dolný Hričov', 49.231944, 18.617778, 309),
('11846', 'Veľké Ripňany', 48.510556, 17.990556, 188),
('11847', 'Topoľčany', 48.563889, 18.156111, 180),
('11849', 'Žikava', 48.458611, 18.390278, 318),
('11850', 'Podhájska', 48.1075, 18.339167, 140),
('11855', 'Nitra - Velké Janíkovce', 48.280556, 18.135556, 135),
('11856', 'Mochovce', 48.289444, 18.456111, 261),
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
('11890', 'Oravské Veselé', 49.471389, 19.385, 760),
('11892', 'Oravský Podzamok', 49.2625, 19.371111, 532),
('11893', 'Martin MS', 49.068333, 18.935833, 411),
('11897', 'Turčianske Teplice', 48.86, 18.860278, 522),
('11898', 'Banská  Bystrica-Zelená', 48.733611, 19.116944, 427),
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
('11959', 'Tatranská Polianka', 49.121944, 20.1875, 975),
('11960', 'Košice-Mesto', 48.725278, 21.265, 203),
('11961', 'Plaveč nad Popradom', 49.259722, 20.845833, 485),
('11962', 'Bardejov', 49.289444, 21.273889, 305),
('11963', 'Jakubovany', 49.108889, 21.140833, 410),
('11964', 'Dubnik', 48.922778, 21.462778, 875),
('11966', 'Čaklov', 48.905278, 21.63, 134),
('11968', 'Košice - letisko', 48.672222, 21.2225, 230),
('11970', 'Silica', 48.553889, 20.520833, 520),
('11976', 'Tisinec', 49.215556, 21.65, 216),
('11977', 'Medzilaborce', 49.253333, 21.913889, 305),
('11978', 'Milhostov', 48.663056, 21.723889, 105),
('11979', 'Somotor', 48.421111, 21.819444, 100),
('11982', 'Michalovce', 48.74, 21.945278, 110),
('11984', 'Orechová', 48.705278, 22.225278, 122),
('11992', 'Osadné', 49.14, 22.150833, 378),
('11993', 'Kamenica nad Cirochou', 48.938889, 22.006111, 176),
('11995', 'Ruský Hrabovec', 48.625556, 22.083889, 105)


## This is mapping of weather elements

(column_name, description_sk, description_en, unit, parameter_type)

('ind_kli', 'klimatologicky indikativ stanice', 'climatological station indicator', '', 'station_info'),
('minuta', 'termín v case UTC', 'time in UTC', '', 'timestamp'),
('t', 'teplota vzduchu vo vyske 2m - minutovy priemer', 'air temperature at 2m height - minute average', 'st.C', 'temperature'),
('tprz', 'prizemna teplota vzduchu vo vyske 5 cm - minutovy priemer', 'ground temperature at 5cm height - minute average', 'st.C', 'temperature'),
('t_pod5', 'teplota pody v hlbke 5 cm - minutovy priemer', 'soil temperature at 5cm depth - minute average', 'st.C', 'soil'),
('t_pod10', 'teplota pody v hlbke 10 cm - minutovy priemer', 'soil temperature at 10cm depth - minute average', 'st.C', 'soil'),
('t_pod20', 'teplota pody v hlbke 20 cm - minutovy priemer', 'soil temperature at 20cm depth - minute average', 'st.C', 'soil'),
('t_pod50', 'teplota pody v hlbke 50 cm - minutovy priemer', 'soil temperature at 50cm depth - minute average', 'st.C', 'soil'),
('t_pod100', 'teplota pody v hlbke 100 cm - minutovy priemer', 'soil temperature at 100cm depth - minute average', 'st.C', 'soil'),
('tlak', 'tlak vzduchu - minutovy priemer', 'air pressure - minute average', 'hPa', 'pressure'),
('vie_min_rych', 'rychlost vetra - minutove minimum', 'wind speed - minute minimum', 'm/s', 'wind'),
('vie_max_rych', 'rychlost vetra - minutove maximum', 'wind speed - minute maximum', 'm/s', 'wind'),
('vie_pr_rych', 'rychlost vetra - minutovy priemer - skalarny', 'wind speed - minute average - scalar', 'm/s', 'wind'),
('vie_vp_rych', 'rychlost vetra - minutovy priemer - vektorovy', 'wind speed - minute average - vector', 'm/s', 'wind'),
('vie_smer_min', 'smer vetra - minutove minimum', 'wind direction - minute minimum', 'dg', 'wind'),
('vie_smer_max', 'smer vetra - minutove maximum', 'wind direction - minute maximum', 'dg', 'wind'),
('vie_pr_smer', 'smer vetra - minutovy priemer - skalarny', 'wind direction - minute average - scalar', 'dg', 'wind'),
('vie_vp_smer', 'smer vetra - minutovy priemer - vektorovy', 'wind direction - minute average - vector', 'dg', 'wind'),
('vie_smer_min_rych', 'smer vetra pri minimalnej rychlosti', 'wind direction at minimum speed', 'dg', 'wind'),
('vie_smer_max_rych', 'smer vetra pri maximalnej rychlosti', 'wind direction at maximum speed', 'dg', 'wind'),
('vlh_rel', 'relativna vlhkost vzduchu - minutovy priemer', 'relative humidity - minute average', '%', 'humidity'),
('zglo', 'globalne ziarenie - minutovy priemer', 'global radiation - minute average', 'W/m2', 'radiation'),
('zra_trv', 'trvanie zrazok - minutova suma', 'precipitation duration - minute sum', 'sekunda', 'precipitation'),
('zra_uhrn', 'uhrn zrazok - minutova suma', 'precipitation amount - minute sum', 'mm', 'precipitation'),
('sln_trv', 'slnecny svit - minutova suma', 'sunshine duration - minute sum', 'sekunda', 'sunshine'),
('dohl', 'dohladnost MOR - minutovy priemer', 'visibility MOR - minute average', 'm', 'visibility'),
('stav_poc', 'stav pocasia', 'weather condition', '', 'weather'),
('sneh_pokr', 'vyska snehovej pokryvky - minutovy priemer', 'snow depth - minute average', 'cm', 'snow'),
('vlh_pod10', 'obj. vlhkost pody v hlbke 10 cm - minutovy priemer', 'soil moisture at 10cm depth - minute average', '%', 'soil'),
('vlh_pod20', 'obj. vlhkost pody v hlbke 20 cm - minutovy priemer', 'soil moisture at 20cm depth - minute average', '%', 'soil'),
('vlh_pod50', 'obj. vlhkost pody v hlbke 50 cm - minutovy priemer', 'soil moisture at 50cm depth - minute average', '%', 'soil'),
('el_vod_pod10', 'elektricka vodivost pody v hlbke 10 cm - minutovy priemer', 'soil electrical conductivity at 10cm depth - minute average', 'dS/m', 'soil'),
('el_vod_pod20', 'elektricka vodivost pody v hlbke 20 cm - minutovy priemer', 'soil electrical conductivity at 20cm depth - minute average', 'dS/m', 'soil'),
('el_vod_pod50', 'elektricka vodivost pody v hlbke 50 cm - minutovy priemer', 'soil electrical conductivity at 50cm depth - minute average', 'dS/m', 'soil'),
('zgama', 'davkovy prikon gama ziarenia', 'gamma radiation dose rate', 'nSv/h', 'radiation'),
('cas', 'cas aktualizacie', 'update time', '', 'timestamp')


# Acceptance Criteria
When executed, 
- the script should fetch latest json data,
- parse the data with known structure,
- return json in the following format:
```
{
  "coord": {
    "lon": 17.1097,
    "lat": 48.1439
  },
  "weather": [
    {
      "id": 803,
      "main": "Clouds",
      "description": "broken clouds",
      "icon": "04d"
    }
  ],
  "base": "stations",
  "main": {
    "temp": 6.32,
    "feels_like": 5.4,
    "temp_min": 5.43,
    "temp_max": 6.84,
    "pressure": 1036,
    "humidity": 59,
    "sea_level": 1036,
    "grnd_level": 1013
  },
  "visibility": 10000,
  "wind": {
    "speed": 1.54,
    "deg": 50
  },
  "clouds": {
    "all": 75
  },
  "dt": 1738850283,
  "sys": {
    "type": 2,
    "id": 2044188,
    "country": "SK",
    "sunrise": 1738822365,
    "sunset": 1738857514
  },
  "timezone": 3600,
  "id": 3060972,
  "name": "Bratislava",
  "cod": 200
}
```
- and target schema description:
```
coord.lon: number
The longitude of the location (e.g., 17.1097).
coord.lat: number
The latitude of the location (e.g., 48.1439).
weather[].id: number
The weather condition ID representing a specific weather phenomenon (e.g., 803 for "broken clouds").
See https://openweathermap.org/weather-conditions for more details
weather[].main: string
The primary group of weather parameters (e.g., "Clouds").
weather[].description: string
A detailed description of the current weather condition (e.g., "broken clouds").
weather[].icon: string
The ID of the weather icon representing the current condition visually (e.g., "04d").
base: string
Internal parameter.
main.temp: number
Current temperature in degrees Celsius (e.g., 6.32°C).
main.feels_like: number
Perceived temperature in degrees Celsius, accounting for human perception (e.g., 5.4°C).
main.pressure: number
Atmospheric pressure at sea level, in hPa (e.g., 1036).
main.humidity: number
Current humidity in percentage (e.g., 59%).
main.temp_min: number
Minimum observed temperature in degrees Celsius (e.g., 5.43°C).
main.temp_max: number
Maximum observed temperature in degrees Celsius (e.g., 6.84°C).
main.sea_level: number (optional)
Atmospheric pressure at sea level, in hPa (e.g., 1036).
main.grnd_level: number (optional)
Atmospheric pressure at ground level, in hPa (e.g., 1013).
visibility: number
Visibility in meters (maximum 10,000m) (e.g., 10,000).
wind.speed: number
Wind speed in meters per second (e.g., 1.54 m/s).
wind.deg: number
Wind direction in meteorological degrees (e.g., 50°).
wind.gust: number (optional)
Wind gust speed in meters per second (e.g., 2.1 m/s).
clouds.all: number
Cloudiness in percentage (e.g., 75%).
rain.1h: number (optional)
Precipitation in the last hour, in millimeters (e.g., 0.5 mm).
snow.1h: number (optional)
Snowfall in the last hour, in millimeters (e.g., 1.2 mm).
dt: number
Unix timestamp of the data calculation in UTC (e.g., 1738850283).
sys.type: number
Internal parameter.
sys.id: number
Internal parameter.
sys.message: string (optional)
Internal parameter.
sys.country: string
The country code of the location (e.g., "SK" for Slovakia).
sys.sunrise: number
Sunrise time as a Unix timestamp (e.g., 1738822365).
sys.sunset: number
Sunset time as a Unix timestamp (e.g., 1738857514).
timezone: number
Shift in seconds from UTC (e.g., 3600).
id: number
City ID (e.g., 3060972 for Bratislava).
name: string
The name of the city (e.g., "Bratislava").
cod: number
Internal parameter indicating response status.
```
