import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from sqlalchemy.orm import Session

from ...models.database import (
    SessionLocal,
    RainfallRecord,
    ProviderHealth,
    LiveAlertEvent
)
from ...config import settings
from ...ingestion.rainfall.open_meteo import OpenMeteoRainfallProvider
from ...ingestion.rainfall.gpm_imerg import GPMIMERGProvider
from ...alerts.evaluator import RainfallRiskEvaluator
from ...alerts.dispatcher import MultiChannelAlertDispatcher
from ...alerts.cap import generate_cap_xml

router = APIRouter()

# Mutex to prevent overlapping ingestion runs
ingestion_lock = asyncio.Lock()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_cron_secret(
    x_cron_secret: Optional[str] = Header(None, alias="X-Cron-Secret"),
    secret: Optional[str] = Query(None)
):
    """
    Validates ingestion secret if configured on the server.
    """
    expected_secret = settings.INGESTION_CRON_SECRET.strip()
    if not expected_secret:
        # If no secret is configured in environment, allow manual trigger (dev/demo convenience)
        return True

    provided = (x_cron_secret or secret or "").strip()
    if provided != expected_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or missing ingestion secret."
        )
    return True

@router.get("/")
@router.get("/latest")
async def get_latest_rainfall(db: Session = Depends(get_db)):
    """
    Returns the latest available precipitation reading, source provenance,
    rolling accumulations, and data freshness for Chungthang.
    """
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)

    # Latest valid reading
    latest_record = db.query(RainfallRecord).filter(
        RainfallRecord.source == "OPEN_METEO"
    ).order_by(RainfallRecord.valid_time.desc()).first()

    provider_health = db.query(ProviderHealth).filter(
        ProviderHealth.provider_name == "OPEN_METEO"
    ).first()

    if not latest_record:
        return {
            "status": "NO_DATA",
            "source": "OPEN_METEO",
            "data_type": "FORECAST",
            "is_forecast": True,
            "is_observation": False,
            "coordinates": {
                "latitude": settings.OPEN_METEO_LATITUDE,
                "longitude": settings.OPEN_METEO_LONGITUDE
            },
            "latest_reading": None,
            "rolling_accumulations": {
                "1h_mm": 0.0,
                "3h_mm": 0.0,
                "6h_mm": 0.0,
                "24h_mm": 0.0
            },
            "freshness_minutes": None,
            "is_fresh": False,
            "provider_status": provider_health.status if provider_health else "NOT CONFIGURED",
            "disclaimer": (
                "Hourly precipitation from Open-Meteo NWP forecast models. "
                "Explicitly labeled as model forecast data, not in-situ rain gauge observations."
            )
        }

    # Calculate rolling sums relative to anchor
    anchor_time = min(now_naive, latest_record.valid_time)

    def rolling_sum(hours: int) -> float:
        start_w = anchor_time - timedelta(hours=hours)
        total = db.query(RainfallRecord).filter(
            RainfallRecord.source == "OPEN_METEO",
            RainfallRecord.valid_time > start_w,
            RainfallRecord.valid_time <= anchor_time
        ).all()
        return round(sum(r.precipitation_mm for r in total), 2)

    retrieval_dt = latest_record.retrieval_time or latest_record.valid_time
    freshness_minutes = (now_naive - retrieval_dt).total_seconds() / 60.0
    is_fresh = freshness_minutes <= settings.RAINFALL_STALE_THRESHOLD_MINUTES

    return {
        "status": "OK" if is_fresh else "STALE",
        "source": latest_record.source,
        "data_type": latest_record.data_type,
        "is_forecast": True,
        "is_observation": False,
        "coordinates": {
            "latitude": latest_record.latitude,
            "longitude": latest_record.longitude
        },
        "latest_reading": {
            "valid_time": latest_record.valid_time.isoformat(),
            "retrieval_time": latest_record.retrieval_time.isoformat() if latest_record.retrieval_time else None,
            "precipitation_mm": latest_record.precipitation_mm,
            "units": latest_record.units
        },
        "rolling_accumulations": {
            "1h_mm": rolling_sum(1),
            "3h_mm": rolling_sum(3),
            "6h_mm": rolling_sum(6),
            "24h_mm": rolling_sum(24)
        },
        "freshness_minutes": round(freshness_minutes, 1),
        "is_fresh": is_fresh,
        "provider_status": provider_health.status if provider_health else ("CONNECTED" if is_fresh else "STALE"),
        "disclaimer": (
            "Hourly precipitation from Open-Meteo NWP forecast models. "
            "Explicitly labeled as model forecast data, not in-situ rain gauge observations."
        )
    }

@router.get("/history")
async def get_rainfall_history(
    hours: int = Query(48, ge=1, le=168),
    db: Session = Depends(get_db)
):
    """
    Returns recent chronological precipitation readings for time-series display.
    """
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    start_time = now_naive - timedelta(hours=hours)

    records = db.query(RainfallRecord).filter(
        RainfallRecord.source == "OPEN_METEO",
        RainfallRecord.valid_time >= start_time
    ).order_by(RainfallRecord.valid_time.asc()).all()

    return [
        {
            "valid_time": r.valid_time.isoformat(),
            "precipitation_mm": r.precipitation_mm,
            "units": r.units,
            "data_type": r.data_type,
            "source": r.source
        }
        for r in records
    ]

@router.get("/provider-health")
async def get_provider_health(db: Session = Depends(get_db)):
    """
    Returns health status, last attempt, last success, and error history for external rainfall providers.
    """
    health_records = db.query(ProviderHealth).all()
    health_map = {h.provider_name: h for h in health_records}

    open_meteo_provider = OpenMeteoRainfallProvider()
    gpm_provider = GPMIMERGProvider()

    om_db = health_map.get("OPEN_METEO")
    gpm_db = health_map.get("NASA_GPM")

    return [
        {
            "provider_name": "OPEN_METEO",
            "display_name": open_meteo_provider.source_name,
            "type": open_meteo_provider.source_type,
            "status": om_db.status if om_db else open_meteo_provider.get_status(db),
            "last_attempt": om_db.last_attempt_time.isoformat() if (om_db and om_db.last_attempt_time) else None,
            "last_success": om_db.last_success_time.isoformat() if (om_db and om_db.last_success_time) else None,
            "latest_data_time": om_db.latest_data_time.isoformat() if (om_db and om_db.latest_data_time) else None,
            "consecutive_failures": om_db.consecutive_failures if om_db else 0,
            "error_message": om_db.error_message if om_db else None,
            "endpoint": open_meteo_provider.api_url,
            "notes": "Hourly numerical precipitation forecast from Open-Meteo."
        },
        {
            "provider_name": "NASA_GPM",
            "display_name": gpm_provider.source_name,
            "type": gpm_provider.source_type,
            "status": gpm_db.status if gpm_db else gpm_provider.get_status(),
            "last_attempt": gpm_db.last_attempt_time.isoformat() if (gpm_db and gpm_db.last_attempt_time) else None,
            "last_success": gpm_db.last_success_time.isoformat() if (gpm_db and gpm_db.last_success_time) else None,
            "latest_data_time": None,
            "consecutive_failures": 0,
            "error_message": gpm_provider.error_message,
            "endpoint": "NASA GES DISC (CMR API)",
            "notes": "Requires NASA Earthdata Login with GES DISC authorization."
        }
    ]

@router.post("/ingest-and-evaluate")
async def ingest_and_evaluate(
    authorized: bool = Depends(verify_cron_secret),
    db: Session = Depends(get_db)
):
    """
    Protected endpoint to ingest fresh external rainfall data from Open-Meteo,
    evaluate risk, persist alert events, and dispatch multi-channel alert notifications (Web Push, SMS) if thresholds are met.

    Safe against overlapping concurrent runs via async mutex lock.
    """
    if ingestion_lock.locked():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Ingestion workflow is already in progress. Please retry after current run completes."
        )

    async with ingestion_lock:
        provider = OpenMeteoRainfallProvider()
        now_utc = datetime.now(timezone.utc)

        # 1. Fetch and persist Open-Meteo readings
        fetched_records = provider.fetch_data(db=db, past_hours=24, forecast_hours=48)

        # 2. Evaluate risk
        evaluator = RainfallRiskEvaluator()
        eval_result = evaluator.evaluate(db=db, now=now_utc)

        alert_event_id = None
        alert_created = False
        cap_xml_doc = None

        # 3. If significant risk or resolution, persist LiveAlertEvent
        if eval_result.severity in ("WATCH", "WARNING", "CRITICAL") or eval_result.is_resolution:
            prefix = "FCST" if eval_result.alert_type == "FORECAST" else "LIVE"
            alert_event_id = f"{prefix}-{now_utc.strftime('%Y%m%d%H%M')}-{uuid.uuid4().hex[:6]}"

            # Generate CAP v1.2 XML
            polygon_coords = "27.58,88.63 27.58,88.66 27.62,88.66 27.62,88.63 27.58,88.63"
            cap_xml_doc = generate_cap_xml(
                identifier=alert_event_id,
                sender="FFEWS-CHUNGTHANG",
                event=eval_result.headline,
                urgency="Immediate" if eval_result.severity in ("WARNING", "CRITICAL") else "Expected",
                severity="Extreme" if eval_result.severity == "CRITICAL" else ("Severe" if eval_result.severity == "WARNING" else "Moderate"),
                certainty="Observed" if eval_result.alert_type == "LIVE" else "Likely",
                headline=eval_result.headline,
                description=eval_result.description,
                instruction="Monitor local emergency channels. Move away from Teesta river banks if water rises.",
                polygon_coordinates=polygon_coords,
                area_desc="Chungthang Basin, Mangan District, Sikkim"
            )

            new_alert = LiveAlertEvent(
                id=alert_event_id,
                alert_type=eval_result.alert_type,
                severity=eval_result.severity,
                zone=eval_result.zone,
                headline=eval_result.headline,
                description=eval_result.description,
                trigger_rule=eval_result.trigger_rule,
                trigger_inputs=eval_result.trigger_inputs,
                threshold_config=eval_result.threshold_config,
                threshold_value=eval_result.threshold_value,
                threshold_name=eval_result.threshold_name,
                data_freshness_minutes=eval_result.data_freshness_minutes,
                status="RESOLVED" if eval_result.is_resolution else ("ACTIVE" if eval_result.severity != "NORMAL" else "RESOLVED"),
                created_at=now_utc.replace(tzinfo=None),
                is_active=(eval_result.severity in ("WATCH", "WARNING", "CRITICAL")),
                cap_xml=cap_xml_doc
            )
            db.add(new_alert)
            db.commit()
            alert_created = True
            eval_result.alert_event_id = alert_event_id

        # 4. Dispatch Multi-Channel Notifications (Web Push, SMS) if alert warrants notification
        dispatcher = MultiChannelAlertDispatcher()
        notification_results = {}

        if eval_result.should_notify and (eval_result.severity in ("WARNING", "CRITICAL") or eval_result.is_resolution):
            alert_payload = {
                "id": alert_event_id,
                "severity": eval_result.severity,
                "zone": eval_result.zone,
                "headline": eval_result.headline,
                "description": eval_result.description,
                "trigger_inputs": eval_result.trigger_inputs
            }
            notification_results = dispatcher.dispatch_all(alert_payload, is_test=False, db=db)

        return {
            "status": "success",
            "timestamp": now_utc.isoformat(),
            "ingestion": {
                "records_fetched": len(fetched_records),
                "source": provider.source_name,
                "provider_status": provider.get_status(db),
                "error": provider.error_message
            },
            "evaluation": {
                "severity": eval_result.severity,
                "headline": eval_result.headline,
                "description": eval_result.description,
                "trigger_rule": eval_result.trigger_rule,
                "trigger_inputs": eval_result.trigger_inputs,
                "disclaimer": eval_result.disclaimer
            },
            "alert": {
                "created": alert_created,
                "alert_id": alert_event_id,
                "severity": eval_result.severity,
                "has_cap_xml": bool(cap_xml_doc)
            },
            "notifications": notification_results
        }
