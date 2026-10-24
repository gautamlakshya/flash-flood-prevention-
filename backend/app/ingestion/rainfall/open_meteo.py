import os
import math
import time
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from ..base import DataProvider, ProviderStatus
from ...config import settings
from ...models.database import RainfallRecord, ProviderHealth

class OpenMeteoRainfallProvider(DataProvider):
    """
    Ingests numerical weather prediction (NWP) precipitation forecasts from Open-Meteo
    for the Chungthang basin study area.

    IMPORTANT: These values are FORECAST/MODEL outputs from global/regional numerical
    weather prediction models (ECMWF, GFS, ICON). They are strictly labeled as FORECAST
    data and are NOT in-situ rain gauge observations.
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        timeout_seconds: Optional[int] = None,
        stale_threshold_minutes: Optional[int] = None
    ):
        super().__init__()
        self.source_name = "Open-Meteo Forecast NWP"
        self.source_type = "NUMERICAL_WEATHER_PREDICTION"
        self.data_type = "FORECAST"

        self.api_url = api_url or settings.OPEN_METEO_API_URL
        self.latitude = latitude if latitude is not None else settings.OPEN_METEO_LATITUDE
        self.longitude = longitude if longitude is not None else settings.OPEN_METEO_LONGITUDE
        self.timeout_seconds = timeout_seconds or settings.OPEN_METEO_TIMEOUT_SECONDS
        self.stale_threshold_minutes = stale_threshold_minutes or settings.RAINFALL_STALE_THRESHOLD_MINUTES
        self.latest_data_time: Optional[datetime] = None

    def _parse_timestamp(self, ts_str: str) -> datetime:
        """
        Parses an ISO 8601 timestamp string from Open-Meteo into a timezone-aware UTC datetime.
        """
        if not ts_str or not isinstance(ts_str, str):
            raise ValueError(f"Invalid timestamp format: {ts_str}")

        # Open-Meteo returns 'YYYY-MM-DDTHH:MM' or 'YYYY-MM-DDTHH:MM:SSZ'
        clean_ts = ts_str.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def validate_and_parse_response(self, raw_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Validates Open-Meteo response structure, coordinates, and numeric values.
        Rejects negative, non-finite, missing, or malformed data.
        """
        if not isinstance(raw_json, dict):
            raise ValueError("Response root must be a JSON object.")

        if "hourly" not in raw_json or not isinstance(raw_json["hourly"], dict):
            raise ValueError("Response missing 'hourly' section.")

        hourly = raw_json["hourly"]
        times = hourly.get("time")
        precip_list = hourly.get("precipitation")

        if not isinstance(times, list) or not isinstance(precip_list, list):
            raise ValueError("Invalid 'time' or 'precipitation' lists in 'hourly' section.")

        if len(times) != len(precip_list):
            raise ValueError(
                f"Mismatch between time count ({len(times)}) and precipitation count ({len(precip_list)})."
            )

        # Verify grid coordinate sanity
        resp_lat = float(raw_json.get("latitude", self.latitude))
        resp_lon = float(raw_json.get("longitude", self.longitude))
        if abs(resp_lat - self.latitude) > 1.0 or abs(resp_lon - self.longitude) > 1.0:
            raise ValueError(
                f"Returned coordinates ({resp_lat}, {resp_lon}) deviate too far from requested ({self.latitude}, {self.longitude})."
            )

        now_utc = datetime.now(timezone.utc)
        records = []

        for ts_str, p_val in zip(times, precip_list):
            valid_dt = self._parse_timestamp(ts_str)

            # Numeric validation
            if p_val is None:
                continue  # skip missing entry

            try:
                precip_float = float(p_val)
            except (ValueError, TypeError):
                raise ValueError(f"Malformed non-numeric precipitation value: {p_val} at {ts_str}")

            if math.isnan(precip_float) or math.isinf(precip_float):
                raise ValueError(f"Non-finite precipitation value: {precip_float} at {ts_str}")

            if precip_float < 0.0:
                raise ValueError(f"Negative precipitation rejected: {precip_float} mm at {ts_str}")

            # Physical cap check for atmospheric rainfall (e.g. max world record ~400mm/hr)
            if precip_float > 500.0:
                raise ValueError(f"Precipitation exceeds physical ceiling (>500mm/hr): {precip_float} at {ts_str}")

            # Distinguish historical/previous hours vs future forecast hours
            is_past = valid_dt < now_utc
            horizon_hours = round((valid_dt - now_utc).total_seconds() / 3600.0, 1)
            time_horizon = "HISTORICAL" if is_past else "FORECAST"

            records.append({
                "source": "OPEN_METEO",
                "data_type": "FORECAST",
                "latitude": self.latitude,
                "longitude": self.longitude,
                "valid_time": valid_dt,
                "retrieval_time": now_utc,
                "precipitation_mm": round(precip_float, 2),
                "units": "mm",
                "raw_metadata": {
                    "grid_latitude": resp_lat,
                    "grid_longitude": resp_lon,
                    "elevation": raw_json.get("elevation"),
                    "generationtime_ms": raw_json.get("generationtime_ms"),
                    "timezone": raw_json.get("timezone", "UTC"),
                    "model": "open_meteo_ecmwf_gfs_ensemble",
                    "time_horizon": time_horizon,
                    "is_past": is_past,
                    "horizon_hours": horizon_hours
                }
            })

        if not records:
            raise ValueError("No valid precipitation records extracted from Open-Meteo payload.")

        return records

    def fetch_data(
        self,
        db: Optional[Session] = None,
        past_hours: int = 24,
        forecast_hours: int = 48,
        max_retries: int = 3,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Fetches hourly precipitation from Open-Meteo API with bounded retries and exponential backoff.
        Persists non-duplicate records to the database if a Session is provided.
        """
        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "hourly": "precipitation",
            "past_hours": past_hours,
            "forecast_hours": forecast_hours,
            "timezone": "UTC"
        }

        last_exception = None
        now_utc = datetime.now(timezone.utc)

        for attempt in range(1, max_retries + 1):
            try:
                response = requests.get(
                    self.api_url,
                    params=params,
                    timeout=self.timeout_seconds
                )
                if response.status_code != 200:
                    raise requests.HTTPError(
                        f"HTTP {response.status_code}: {response.text[:200]}",
                        response=response
                    )

                raw_json = response.json()
                records = self.validate_and_parse_response(raw_json)

                # Fetch succeeded
                self.last_updated = now_utc
                self.error_message = None
                if records:
                    self.latest_data_time = max(r["valid_time"] for r in records)

                # Persist to database if db session provided
                if db is not None:
                    self._persist_records(db, records, now_utc)
                    self._update_provider_health(db, status=ProviderStatus.CONNECTED, now_utc=now_utc, error=None)

                return records

            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    # Bounded exponential backoff (0.5s, 1.0s, 2.0s)
                    time.sleep(0.5 * (2 ** (attempt - 1)))

        # If all retries failed:
        err_msg = f"Failed to fetch Open-Meteo after {max_retries} attempts: {str(last_exception)}"
        self.error_message = err_msg

        if db is not None:
            self._update_provider_health(db, status=ProviderStatus.ERROR, now_utc=now_utc, error=err_msg)

        return []

    def _persist_records(self, db: Session, records: List[Dict[str, Any]], now_utc: datetime):
        """
        Persists records without inserting duplicates for (source, latitude, longitude, valid_time).
        """
        if not records:
            return

        # Convert valid_time to naive UTC for consistent SQLite storage if needed
        for r in records:
            v_time = r["valid_time"]
            if hasattr(v_time, "tzinfo") and v_time.tzinfo is not None:
                # store naive UTC
                v_time_naive = v_time.astimezone(timezone.utc).replace(tzinfo=None)
            else:
                v_time_naive = v_time

            ret_naive = now_utc.astimezone(timezone.utc).replace(tzinfo=None)

            existing = db.query(RainfallRecord).filter(
                RainfallRecord.source == r["source"],
                RainfallRecord.latitude == r["latitude"],
                RainfallRecord.longitude == r["longitude"],
                RainfallRecord.valid_time == v_time_naive
            ).first()

            if existing:
                # Update existing forecast sample with fresher retrieval
                existing.precipitation_mm = r["precipitation_mm"]
                existing.retrieval_time = ret_naive
                existing.raw_metadata = r["raw_metadata"]
            else:
                new_record = RainfallRecord(
                    source=r["source"],
                    data_type=r["data_type"],
                    latitude=r["latitude"],
                    longitude=r["longitude"],
                    valid_time=v_time_naive,
                    retrieval_time=ret_naive,
                    precipitation_mm=r["precipitation_mm"],
                    units=r["units"],
                    raw_metadata=r["raw_metadata"]
                )
                db.add(new_record)

        db.commit()

    def _update_provider_health(
        self,
        db: Session,
        status: str,
        now_utc: datetime,
        error: Optional[str]
    ):
        """
        Updates the provider_health table with current status, failures, and freshness.
        """
        now_naive = now_utc.astimezone(timezone.utc).replace(tzinfo=None)
        health = db.query(ProviderHealth).filter(
            ProviderHealth.provider_name == "OPEN_METEO"
        ).first()

        if not health:
            health = ProviderHealth(
                provider_name="OPEN_METEO",
                status=status,
                consecutive_failures=0
            )
            db.add(health)

        health.last_attempt_time = now_naive

        if status == ProviderStatus.CONNECTED:
            health.last_success_time = now_naive
            health.consecutive_failures = 0
            health.error_message = None
            health.status = ProviderStatus.CONNECTED
            if self.latest_data_time:
                latest_naive = self.latest_data_time
                if hasattr(latest_naive, "tzinfo") and latest_naive.tzinfo is not None:
                    latest_naive = latest_naive.astimezone(timezone.utc).replace(tzinfo=None)
                health.latest_data_time = latest_naive
        else:
            health.consecutive_failures += 1
            health.error_message = error
            # Check staleness if last_success_time is known
            if health.last_success_time:
                age_minutes = (now_naive - health.last_success_time).total_seconds() / 60.0
                if age_minutes > self.stale_threshold_minutes:
                    health.status = ProviderStatus.STALE
                elif health.consecutive_failures >= 3:
                    health.status = ProviderStatus.UNAVAILABLE
                else:
                    health.status = ProviderStatus.ERROR
            else:
                health.status = ProviderStatus.ERROR

        db.commit()

    def get_status(self, db: Optional[Session] = None) -> str:
        """
        Determines whether the provider is CONNECTED, STALE, UNAVAILABLE, or NOT CONFIGURED.
        An external source is only CONNECTED if a real validated fetch succeeded recently.
        """
        if not self.api_url:
            return ProviderStatus.NOT_CONFIGURED

        if db is not None:
            health = db.query(ProviderHealth).filter(
                ProviderHealth.provider_name == "OPEN_METEO"
            ).first()
            if health:
                if health.last_success_time:
                    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
                    age_minutes = (now_naive - health.last_success_time).total_seconds() / 60.0
                    if age_minutes > self.stale_threshold_minutes:
                        return ProviderStatus.STALE
                    if health.status == ProviderStatus.CONNECTED:
                        return ProviderStatus.CONNECTED
                    return health.status
                elif health.consecutive_failures > 0:
                    return ProviderStatus.UNAVAILABLE if health.consecutive_failures >= 3 else ProviderStatus.ERROR
                else:
                    return "CONFIGURED"

        if self.last_updated:
            now_utc = datetime.now(timezone.utc)
            age_minutes = (now_utc - self.last_updated).total_seconds() / 60.0
            if age_minutes > self.stale_threshold_minutes:
                return ProviderStatus.STALE
            return ProviderStatus.CONNECTED

        if self.error_message:
            return ProviderStatus.ERROR

        return "CONFIGURED"

    def get_metadata(self, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Returns rich metadata for data source auditing and UI display.
        """
        status = self.get_status(db=db)
        last_updated_str = None
        latest_data_str = None
        err = self.error_message

        if db is not None:
            health = db.query(ProviderHealth).filter(
                ProviderHealth.provider_name == "OPEN_METEO"
            ).first()
            if health:
                if health.last_success_time:
                    last_updated_str = health.last_success_time.isoformat() + "Z"
                if health.latest_data_time:
                    latest_data_str = health.latest_data_time.isoformat() + "Z"
                if health.error_message:
                    err = health.error_message
        elif self.last_updated:
            last_updated_str = self.last_updated.isoformat()
            if self.latest_data_time:
                latest_data_str = self.latest_data_time.isoformat()

        return {
            "name": self.source_name,
            "type": self.source_type,
            "data_category": self.data_type,
            "status": status,
            "coordinates": {"latitude": self.latitude, "longitude": self.longitude},
            "endpoint": self.api_url,
            "units": "mm",
            "is_forecast": True,
            "is_observation": False,
            "stale_threshold_minutes": self.stale_threshold_minutes,
            "last_updated": last_updated_str,
            "latest_data_time": latest_data_str,
            "error": err,
            "notes": "Hourly numerical precipitation forecast from Open-Meteo (ECMWF/GFS ensemble). Explicitly labeled as model forecast, not physical in-situ rain gauge observation."
        }

