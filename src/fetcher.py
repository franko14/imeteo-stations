"""Smart weather data fetcher with robust URL discovery."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import httpx
from pydantic import BaseModel, Field

from .time_utils import get_current_time_windows, build_url_timestamp, build_date_path

logger = logging.getLogger(__name__)


class WeatherDataError(Exception):
    """Base exception for weather data operations."""
    pass


class DataUnavailableError(WeatherDataError):
    """Data temporarily unavailable."""
    pass


class NetworkError(WeatherDataError):
    """Network-related error."""
    pass


@dataclass
class FetchResult:
    """Result of a successful data fetch."""
    data: Dict[str, Any]
    url: str
    timestamp: datetime
    records_count: int
    stations_count: int


class FetchSettings(BaseModel):
    """Configuration for data fetcher."""
    base_url: str = Field(
        default="https://opendata.shmu.sk/meteorology/climate/now/data",
        description="Base URL for SHMU data"
    )
    timeout: float = Field(default=30.0, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay: float = Field(default=1.0, description="Base retry delay in seconds")
    user_agent: str = Field(
        default="imeteo-stations/1.0.0 (iMeteo.sk Weather Data Service)",
        description="User agent string"
    )


class WeatherDataFetcher:
    """
    Smart weather data fetcher with robust URL discovery.

    This fetcher handles the complexities of Slovak weather data:
    1. Files are published every 5 minutes
    2. URLs use Slovak local time (CEST/CET)
    3. Publication delays may occur
    4. File naming patterns may vary slightly
    """

    def __init__(self, settings: Optional[FetchSettings] = None):
        self.settings = settings or FetchSettings()
        self._client: Optional[httpx.AsyncClient] = None
        self._last_successful_url: Optional[str] = None
        self._last_fetch_time: Optional[datetime] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _ensure_client(self):
        """Ensure HTTP client is initialized."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.settings.timeout),
                headers={"User-Agent": self.settings.user_agent},
                follow_redirects=True,
                verify=False,  # Disable SSL verification for SHMU API
            )

    async def _discover_available_files(self, timestamp: datetime) -> List[str]:
        """
        Discover available files by listing directory contents.

        Args:
            timestamp: Local Slovak time

        Returns:
            List of actual available file URLs for the time window
        """
        base = self.settings.base_url
        date_path = build_date_path(timestamp)

        # Build directory listing URL
        directory_url = f"{base}/{date_path}/"

        try:
            logger.debug(f"Listing directory: {directory_url}")
            response = await self._client.get(directory_url)

            if response.status_code == 200:
                # Parse HTML directory listing to find aws1min files
                html_content = response.text

                # Look for files matching our time pattern
                time_pattern = timestamp.strftime("%Y-%m-%d %H-%M")

                # Extract ALL file links from HTML for debugging
                import re
                import urllib.parse
                all_files_pattern = r'href="([^"]*\.json)"'
                all_files = re.findall(all_files_pattern, html_content, re.IGNORECASE)

                # Filter for aws1min files and decode URL encoding
                aws_files = []
                for f in all_files:
                    if 'aws1min' in f.lower():
                        decoded_file = urllib.parse.unquote(f)
                        aws_files.append(decoded_file)

                if aws_files:
                    logger.debug(f"Available aws1min files: {aws_files[-10:]}...")  # Show last 10 (most recent)

                # Look for files matching our time pattern in decoded filenames
                matches = []
                for f in aws_files:
                    if time_pattern in f:
                        matches.append(urllib.parse.quote(f))  # Re-encode for URL

                if matches:
                    # Build full URLs
                    urls = [f"{base}/{date_path}/{filename}" for filename in matches]
                    logger.debug(f"Found {len(urls)} files for {time_pattern}")
                    return urls
                else:
                    logger.debug(f"No files found matching {time_pattern}. Available files: {len(aws_files)}")
                    return []
            else:
                logger.debug(f"Directory listing failed: {response.status_code}")
                return []

        except Exception as e:
            logger.debug(f"Directory discovery failed: {e}")
            return []

    async def _try_fetch_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Try to fetch data from a single URL.

        Args:
            url: URL to fetch

        Returns:
            JSON data if successful, None if failed
        """
        try:
            logger.debug(f"Trying URL: {url}")
            response = await self._client.get(url)

            if response.status_code == 200:
                data = response.json()
                logger.info(f"Successfully fetched data from: {url}")
                return data
            elif response.status_code == 404:
                logger.debug(f"URL not found: {url}")
                return None
            else:
                logger.warning(f"Unexpected status {response.status_code} for: {url}")
                return None

        except httpx.TimeoutException:
            logger.warning(f"Timeout for URL: {url}")
            return None
        except httpx.NetworkError as e:
            logger.warning(f"Network error for URL {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error for URL {url}: {e}")
            return None

    async def _fetch_with_retry(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Fetch URL with exponential backoff retry.

        Args:
            url: URL to fetch

        Returns:
            JSON data if successful, None if all retries failed
        """
        for attempt in range(self.settings.max_retries):
            result = await self._try_fetch_url(url)
            if result is not None:
                return result

            if attempt < self.settings.max_retries - 1:
                delay = self.settings.retry_delay * (2 ** attempt)
                logger.debug(f"Retrying {url} in {delay}s (attempt {attempt + 1})")
                await asyncio.sleep(delay)

        return None

    async def _try_time_window(self, timestamp: datetime) -> Optional[FetchResult]:
        """
        Try to fetch data for a specific time window.

        Args:
            timestamp: Local Slovak time

        Returns:
            FetchResult if successful, None if failed
        """
        # First, discover available files for this time window
        available_urls = await self._discover_available_files(timestamp)

        if not available_urls:
            logger.debug(f"No files discovered for time window: {timestamp}")
            return None

        # Try URLs in parallel for faster discovery
        tasks = [self._fetch_with_retry(url) for url in available_urls]

        try:
            # Use timeout to prevent hanging on slow responses
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.settings.timeout * 2
            )

            for i, result in enumerate(results):
                if isinstance(result, dict) and result:
                    url = available_urls[i]

                    # Validate the data structure
                    if self._validate_data_structure(result):
                        return FetchResult(
                            data=result,
                            url=url,
                            timestamp=timestamp,
                            records_count=len(result.get('data', [])),
                            stations_count=len(set(
                                r.get('ind_kli') for r in result.get('data', [])
                                if r.get('ind_kli')
                            ))
                        )

        except asyncio.TimeoutError:
            logger.warning(f"Timeout trying time window: {timestamp}")

        return None

    def _validate_data_structure(self, data: Dict[str, Any]) -> bool:
        """
        Validate that fetched data has expected structure.

        Args:
            data: JSON data from API

        Returns:
            True if data structure is valid
        """
        try:
            # Check required fields
            if not isinstance(data, dict):
                return False

            if 'data' not in data or not isinstance(data['data'], list):
                logger.warning("Invalid data structure: missing 'data' array")
                return False

            if not data['data']:
                logger.warning("Empty data array")
                return False

            # Check if records have required fields
            sample_record = data['data'][0]
            required_fields = ['ind_kli', 'minuta']

            for field in required_fields:
                if field not in sample_record:
                    logger.warning(f"Missing required field: {field}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Error validating data structure: {e}")
            return False

    async def fetch_latest_data_for_station(self, station_id: str = None) -> FetchResult:
        """
        Fetch the latest available weather data with station-specific fallback.

        Args:
            station_id: If provided, will try multiple files until one contains this station

        Returns:
            FetchResult with latest data

        Raises:
            DataUnavailableError: If no recent data is available
            NetworkError: If network issues prevent fetching
        """
        if station_id is None:
            return await self.fetch_latest_data()

        await self._ensure_client()

        # Get candidate time windows
        time_windows = get_current_time_windows()
        logger.info(f"Trying {len(time_windows)} time windows for station {station_id}")

        # Try time windows in order until we find data for the station
        for i, timestamp in enumerate(time_windows):
            logger.debug(f"Trying time window {i+1}/{len(time_windows)}: {timestamp}")

            result = await self._try_time_window(timestamp)
            if result:
                # Check if this station has data in this file
                station_records = [r for r in result.data.get('data', [])
                                 if str(r.get('ind_kli')) == str(station_id)]

                if station_records:
                    # Cache successful URL
                    self._last_successful_url = result.url
                    self._last_fetch_time = datetime.utcnow()

                    logger.info(
                        f"Successfully fetched data for station {station_id}: "
                        f"{result.records_count} records from {result.stations_count} stations"
                    )
                    return result
                else:
                    logger.debug(f"Station {station_id} not found in file {result.url}, trying older file")

        # If we get here, no data was found for the station
        raise DataUnavailableError(
            f"No weather data available for station {station_id} in the last {len(time_windows) * 5} minutes. "
            "This could indicate a temporary service issue, station maintenance, or data publication delay."
        )

    async def fetch_latest_data(self) -> FetchResult:
        """
        Fetch the latest available weather data.

        Uses smart discovery to find the most recent data file by trying
        multiple time windows and URL patterns.

        Returns:
            FetchResult with latest data

        Raises:
            DataUnavailableError: If no recent data is available
            NetworkError: If network issues prevent fetching
        """
        await self._ensure_client()

        # Get candidate time windows
        time_windows = get_current_time_windows()
        logger.info(f"Trying {len(time_windows)} time windows for latest data")

        # Try cached URL first if we have one
        if (self._last_successful_url and self._last_fetch_time and
                (datetime.utcnow() - self._last_fetch_time).seconds < 240):
            logger.debug("Trying cached URL first")
            cached_result = await self._try_fetch_url(self._last_successful_url)
            if cached_result and self._validate_data_structure(cached_result):
                return FetchResult(
                    data=cached_result,
                    url=self._last_successful_url,
                    timestamp=datetime.utcnow(),
                    records_count=len(cached_result.get('data', [])),
                    stations_count=len(set(
                        r.get('ind_kli') for r in cached_result.get('data', [])
                        if r.get('ind_kli')
                    ))
                )

        # Try time windows in order (most recent first)
        for i, timestamp in enumerate(time_windows):
            logger.debug(f"Trying time window {i+1}/{len(time_windows)}: {timestamp}")

            result = await self._try_time_window(timestamp)
            if result:
                # Cache successful URL
                self._last_successful_url = result.url
                self._last_fetch_time = datetime.utcnow()

                logger.info(
                    f"Successfully fetched data: {result.records_count} records "
                    f"from {result.stations_count} stations"
                )
                return result

        # If we get here, no data was found
        raise DataUnavailableError(
            f"No weather data available in the last {len(time_windows) * 5} minutes. "
            "This could indicate a temporary service issue or data publication delay."
        )

    async def fetch_specific_time(self, target_time: datetime) -> FetchResult:
        """
        Fetch data for a specific time.

        Args:
            target_time: Target time in Slovak local time

        Returns:
            FetchResult for the specified time

        Raises:
            DataUnavailableError: If data for specified time is not available
        """
        await self._ensure_client()

        logger.info(f"Fetching data for specific time: {target_time}")

        result = await self._try_time_window(target_time)
        if result:
            return result

        raise DataUnavailableError(
            f"No weather data available for time: {target_time}"
        )

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of the data source.

        Returns:
            Health status information
        """
        await self._ensure_client()

        start_time = datetime.utcnow()

        try:
            result = await self.fetch_latest_data()
            elapsed = (datetime.utcnow() - start_time).total_seconds()

            return {
                "status": "healthy",
                "response_time": elapsed,
                "records_count": result.records_count,
                "stations_count": result.stations_count,
                "data_timestamp": result.timestamp.isoformat(),
                "last_successful_url": result.url,
            }

        except Exception as e:
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            return {
                "status": "unhealthy",
                "response_time": elapsed,
                "error": str(e),
                "error_type": type(e).__name__,
            }