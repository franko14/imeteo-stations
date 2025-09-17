#!/usr/bin/env python3
"""
Script to fetch WFS data from SHMU and find missing weather stations.
This script will identify stations that exist in live data but are missing from our database.
"""

import re
import requests
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple, Set
import sys
from pathlib import Path

# Add src to path to import our modules
sys.path.insert(0, str(Path(__file__).parent / "src"))
from stations import STATIONS_DATA

def fetch_wfs_data() -> str:
    """Fetch WFS data from SHMU."""
    url = "https://geo.shmu.sk/geoserver/ef-swn-cs/wfs"
    params = {
        'service': 'wfs',
        'version': '2.0.0',
        'request': 'GetFeature',
        'typeNames': 'ef-swn-cs:EnvironmentalMonitoringFacility'
    }

    print("Fetching WFS data from SHMU...")
    response = requests.get(url, params=params, verify=False)
    response.raise_for_status()

    # Print first 1000 characters to understand the format
    content = response.text
    print(f"Response content type: {response.headers.get('content-type', 'unknown')}")
    print(f"Response length: {len(content)} characters")
    print("First 1000 characters of response:")
    print(content[:1000])
    print("=" * 50)

    return content

def parse_wfs_stations(xml_content: str) -> List[Dict[str, str]]:
    """Parse WFS XML and extract station information."""
    stations = []

    # First, let's try to find stations using regex patterns since XML parsing with namespaces is tricky
    print("Parsing WFS XML content...")

    # Find all instances of station data using regex
    local_id_pattern = r'<base:localId>([^<]*SK(\d+)[^<]*)</base:localId>'
    name_pattern = r'<ef-swn-cs:name>([^<]+)</ef-swn-cs:name>'
    pos_pattern = r'<gml:pos>([^<]+)</gml:pos>'

    local_id_matches = re.findall(local_id_pattern, xml_content)
    name_matches = re.findall(name_pattern, xml_content)
    pos_matches = re.findall(pos_pattern, xml_content)

    print(f"Found {len(local_id_matches)} local IDs")
    print(f"Found {len(name_matches)} names")
    print(f"Found {len(pos_matches)} position entries")

    # Try to match them up by position in the document
    for i, (local_id_full, station_id) in enumerate(local_id_matches):
        try:
            if i < len(name_matches) and i < len(pos_matches):
                station_name = name_matches[i]
                coords = pos_matches[i].strip().split()

                if len(coords) == 2:
                    latitude = float(coords[0])
                    longitude = float(coords[1])

                    stations.append({
                        'id': station_id,
                        'name': station_name,
                        'latitude': latitude,
                        'longitude': longitude,
                        'local_id': local_id_full
                    })

        except Exception as e:
            print(f"Error parsing station {i}: {e}")
            continue

    # Also try XML parsing as fallback
    try:
        root = ET.fromstring(xml_content)

        # Try different namespace approaches
        for elem in root.iter():
            if 'localId' in elem.tag:
                local_id = elem.text
                if local_id and 'SK' in local_id:
                    match = re.search(r'SK(\d+)', local_id)
                    if match:
                        station_id = match.group(1)
                        # Look for corresponding name and position elements nearby
                        parent = elem.getparent() if hasattr(elem, 'getparent') else None
                        if parent is not None:
                            # Find name and position in the same facility
                            for child in parent.iter():
                                if 'name' in child.tag and child.text:
                                    station_name = child.text
                                elif 'pos' in child.tag and child.text:
                                    coords = child.text.strip().split()
                                    if len(coords) == 2:
                                        latitude = float(coords[0])
                                        longitude = float(coords[1])

                                        # Check if we already have this station
                                        if not any(s['id'] == station_id for s in stations):
                                            stations.append({
                                                'id': station_id,
                                                'name': station_name,
                                                'latitude': latitude,
                                                'longitude': longitude,
                                                'local_id': local_id
                                            })
                                        break
    except Exception as e:
        print(f"XML parsing fallback failed: {e}")

    return stations

def get_current_station_ids() -> Set[str]:
    """Get set of station IDs from our current database."""
    return {station_id for station_id, _, _, _, _ in STATIONS_DATA}

def get_live_station_ids() -> Set[str]:
    """Get station IDs that appear in live data by running fetch-all."""
    import subprocess
    import tempfile

    print("Getting live station IDs from fetch-all command...")

    # Run fetch-all and capture stderr to see which stations are being processed
    try:
        result = subprocess.run([
            sys.executable, '-m', 'src.main', 'fetch-all', '--limit', '200'
        ], capture_output=True, text=True, cwd=Path(__file__).parent)

        # Extract station IDs from the output
        station_ids = set()

        # Look for processing messages and error messages
        for line in result.stderr.split('\n'):
            # Look for "Failed to process station XXXXX" messages
            if 'Failed to process station' in line:
                match = re.search(r'station (\d+)', line)
                if match:
                    station_ids.add(match.group(1))

        # Also extract from successful processing (look at the output for station count)
        if 'Processing' in result.stderr and 'stations' in result.stderr:
            # Try to get the actual count and extract from successful runs too
            pass

        return station_ids

    except Exception as e:
        print(f"Error getting live station IDs: {e}")
        return set()

def main():
    """Main function to find missing stations."""
    print("=== SHMU Missing Stations Finder ===\n")

    try:
        # Get WFS data
        xml_content = fetch_wfs_data()

        # Parse stations from WFS
        wfs_stations = parse_wfs_stations(xml_content)
        wfs_station_ids = {s['id'] for s in wfs_stations}

        print(f"Found {len(wfs_stations)} stations in WFS data")
        if wfs_station_ids:
            print(f"WFS Station ID range: {min(wfs_station_ids)} - {max(wfs_station_ids)}")
        else:
            print("No station IDs found in WFS data")

        # Get current database stations
        current_station_ids = get_current_station_ids()
        print(f"Current database has {len(current_station_ids)} stations")

        # Get live data station IDs (from error messages)
        live_station_ids = get_live_station_ids()
        print(f"Found {len(live_station_ids)} stations with errors in live data")

        # Find missing stations that are in WFS but not in our database
        missing_in_db = wfs_station_ids - current_station_ids

        # Find missing stations that appear in live data errors
        missing_from_errors = live_station_ids - current_station_ids

        print(f"\n=== ANALYSIS ===")
        print(f"Stations in WFS but missing from database: {len(missing_in_db)}")
        print(f"Stations with live data errors: {len(missing_from_errors)}")

        # Combine and find stations we need to add
        all_missing = missing_in_db | missing_from_errors

        if all_missing:
            print(f"\n=== MISSING STATIONS TO ADD ===")

            # Show details for stations found in WFS
            for station_id in sorted(all_missing):
                wfs_station = next((s for s in wfs_stations if s['id'] == station_id), None)
                if wfs_station:
                    print(f"ID: {station_id}")
                    print(f"  Name: {wfs_station['name']}")
                    print(f"  Coordinates: {wfs_station['latitude']}, {wfs_station['longitude']}")
                    print(f"  Local ID: {wfs_station['local_id']}")
                    print()
                else:
                    print(f"ID: {station_id} (found in live data errors, but not in WFS)")
                    print()

            # Generate Python code to add to stations.py
            print("=== CODE TO ADD TO stations.py ===")
            for station_id in sorted(all_missing):
                wfs_station = next((s for s in wfs_stations if s['id'] == station_id), None)
                if wfs_station:
                    # Estimate elevation (you may want to refine this)
                    elevation = 200  # Default elevation
                    print(f"    ('{station_id}', '{wfs_station['name']}', {wfs_station['latitude']}, {wfs_station['longitude']}, {elevation}),")

        else:
            print("No missing stations found!")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()