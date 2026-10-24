import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...models.database import (
    SessionLocal,
    LiveAlertEvent,
    NotificationDelivery,
    PushSubscription
)
from ...alerts.channel import DeliveryReport
from ...alerts.web_push import WebPushNotificationChannel
from ...alerts.sms import SMSNotificationChannel
from ...alerts.dispatcher import MultiChannelAlertDispatcher
from ...alerts.evaluator import RainfallRiskEvaluator
from ...alerts.cap import generate_cap_xml
from ...config import settings

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_admin_key(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    x_cron_secret: Optional[str] = Header(None, alias="X-Cron-Secret"),
    secret: Optional[str] = Query(None)
):
    """
    Validates administrative authentication for alert management and push dispatches.
    Rejects missing or incorrect admin keys whenever ALERT_ADMIN_KEY (or INGESTION_CRON_SECRET) is configured.
    """
    valid_keys = [k.strip() for k in [settings.ALERT_ADMIN_KEY, settings.INGESTION_CRON_SECRET] if k and k.strip()]
    if not valid_keys:
        # In development/prototype mode without configured keys, allow with audit
        return True

    provided = (x_admin_key or x_cron_secret or secret or "").strip()
    if not provided or provided not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Valid X-Admin-Key or ingestion secret required."
        )
    return True

# Request models
class AcknowledgeRequest(BaseModel):
    operator_name: Optional[str] = None
    acknowledged_by: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=500)

class EvaluatePredictionRequest(BaseModel):
    predicted_discharge: Optional[float] = None
    predicted_discharge_m3s: Optional[float] = None
    bankfull_capacity: float = 900.0
    rate_of_rise: float = 0.0
    zone: str = "Chungthang Basin (Teesta River)"
    is_simulation: bool = True
    data_freshness_minutes: Optional[float] = 10.0
    reason: Optional[str] = None

class PushSubscriptionKeys(BaseModel):
    p256dh: str
    auth: str

class PushSubscriptionRequest(BaseModel):
    endpoint: str
    keys: PushSubscriptionKeys
    user_agent: Optional[str] = None

class PushUnsubscribeRequest(BaseModel):
    endpoint: str


def _serialize_alert(a: LiveAlertEvent) -> Dict[str, Any]:
    deliveries = [
        {
            "id": d.id,
            "channel": d.channel,
            "status": d.status,
            "attempt_time": d.attempt_time.isoformat() if d.attempt_time else None,
            "recipient": d.recipient_id,
            "error": d.error_message
        }
        for d in a.deliveries
    ]
    return {
        "id": a.id,
        "alert_type": a.alert_type,
        "severity": a.severity,
        "zone": a.zone or "Chungthang Basin (Teesta River)",
        "headline": a.headline,
        "description": a.description,
        "trigger_rule": a.trigger_rule,
        "trigger_inputs": a.trigger_inputs,
        "predicted_discharge": a.predicted_discharge,
        "threshold_value": a.threshold_value,
        "threshold_name": a.threshold_name,
        "data_freshness_minutes": a.data_freshness_minutes,
        "status": a.status or ("ACTIVE" if a.is_active else "RESOLVED"),
        "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
        "acknowledged_by": a.acknowledged_by,
        "acknowledgement_notes": a.acknowledgement_notes,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
        "is_active": a.is_active,
        "has_cap_xml": bool(a.cap_xml),
        "cap_xml": a.cap_xml,
        "deliveries": deliveries
    }

@router.get("/")
async def list_alerts(
    alert_type: Optional[str] = Query(None, description="LIVE, FORECAST, SIMULATION, or TEST"),
    severity: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Lists persisted alert events with delivery history and lifecycle states.
    """
    query = db.query(LiveAlertEvent)
    if alert_type:
        query = query.filter(LiveAlertEvent.alert_type == alert_type.upper())
    if severity:
        query = query.filter(LiveAlertEvent.severity == severity.upper())
    if status_filter:
        query = query.filter(LiveAlertEvent.status == status_filter.upper())

    alerts = query.order_by(LiveAlertEvent.created_at.desc()).limit(limit).all()
    return [_serialize_alert(a) for a in alerts]

@router.get("/active")
async def get_active_alert(db: Session = Depends(get_db)):
    """
    Returns the current active flood alert record for the Chungthang basin,
    or the latest alert record if no threat is currently active.
    Ensures map, dashboard, and notification services share an identical backend record.
    """
    active_threat = db.query(LiveAlertEvent).filter(
        LiveAlertEvent.is_active == True,
        LiveAlertEvent.status.in_(["ACTIVE", "ACKNOWLEDGED"]),
        LiveAlertEvent.severity.in_(["WATCH", "WARNING", "CRITICAL"])
    ).order_by(LiveAlertEvent.created_at.desc()).first()

    if active_threat:
        return {
            "has_active_threat": True,
            "alert": _serialize_alert(active_threat)
        }

    latest = db.query(LiveAlertEvent).order_by(LiveAlertEvent.created_at.desc()).first()
    return {
        "has_active_threat": False,
        "alert": _serialize_alert(latest) if latest else None
    }

@router.get("/detail/{alert_id}")
async def get_alert_detail(alert_id: str, db: Session = Depends(get_db)):
    """
    Returns full details, trigger inputs, CAP XML, and delivery audit log for a single alert.
    """
    alert = db.query(LiveAlertEvent).filter(LiveAlertEvent.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert '{alert_id}' not found."
        )
    return _serialize_alert(alert)

@router.get("/history")
async def get_alert_history(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db)
):
    """
    Returns chronological alert history for auditing.
    """
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    alerts = db.query(LiveAlertEvent).filter(
        LiveAlertEvent.created_at >= cutoff
    ).order_by(LiveAlertEvent.created_at.desc()).all()

    return [
        {
            "id": a.id,
            "alert_type": a.alert_type,
            "severity": a.severity,
            "zone": a.zone,
            "headline": a.headline,
            "status": a.status,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "delivery_count": len(a.deliveries)
        }
        for a in alerts
    ]

@router.get("/notification-config")
async def get_notification_config(db: Session = Depends(get_db)):
    """
    Returns multi-channel status (Web Push, SMS, CAP).
    Strictly redacts private keys and tokens.
    """
    web_push = WebPushNotificationChannel()
    sms = SMSNotificationChannel()

    sub_count = db.query(PushSubscription).filter(PushSubscription.is_active == True).count()

    push_status = web_push.get_status()
    push_status["active_subscriptions"] = sub_count

    return {
        "channels": [
            push_status,
            sms.get_status(),
            {
                "channel": "CAP_XML",
                "status": "READY",
                "standard": "Common Alerting Protocol v1.2 (WMO / NDMA)",
                "notes": "Compliant XML documents generated for all Warning and Critical events."
            }
        ]
    }

@router.get("/push/vapid-public-key")
async def get_vapid_public_key():
    """
    Returns the VAPID Public Key required by the browser Service Worker
    to subscribe for push notifications via pushManager.subscribe().
    """
    web_push = WebPushNotificationChannel()
    pub = web_push.get_public_key()
    status_str = "READY" if web_push.is_configured() else ("CONFIG_ERROR" if web_push.key_mgr._config_error else "NOT CONFIGURED")
    return {
        "publicKey": pub,
        "public_key": pub,
        "status": status_str,
        "error": web_push.key_mgr._config_error
    }

@router.post("/push/subscribe")
async def subscribe_push(
    sub_req: PushSubscriptionRequest,
    db: Session = Depends(get_db)
):
    """
    Registers or updates a browser Web Push subscription.
    """
    if not sub_req.endpoint or not sub_req.keys.p256dh or not sub_req.keys.auth:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing endpoint, p256dh key, or auth key."
        )

    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    existing = db.query(PushSubscription).filter(
        PushSubscription.endpoint == sub_req.endpoint
    ).first()

    if existing:
        existing.p256dh = sub_req.keys.p256dh
        existing.auth = sub_req.keys.auth
        existing.user_agent = sub_req.user_agent
        existing.is_active = True
        existing.created_at = now_naive
        db.commit()
        return {"status": "updated", "id": existing.id}
    else:
        new_sub = PushSubscription(
            endpoint=sub_req.endpoint,
            p256dh=sub_req.keys.p256dh,
            auth=sub_req.keys.auth,
            user_agent=sub_req.user_agent,
            created_at=now_naive,
            is_active=True
        )
        db.add(new_sub)
        db.commit()
        db.refresh(new_sub)
        return {"status": "subscribed", "id": new_sub.id}

@router.post("/push/unsubscribe")
async def unsubscribe_push(
    unsub_req: PushUnsubscribeRequest,
    db: Session = Depends(get_db)
):
    """
    Deactivates a browser Web Push subscription.
    """
    sub = db.query(PushSubscription).filter(
        PushSubscription.endpoint == unsub_req.endpoint
    ).first()
    if sub:
        sub.is_active = False
        db.commit()
    return {"status": "unsubscribed"}

@router.get("/push/subscriptions")
async def get_push_subscriptions(
    authorized: bool = Depends(verify_admin_key),
    db: Session = Depends(get_db)
):
    """
    Protected audit endpoint to review registered push endpoints.
    """
    subs = db.query(PushSubscription).all()
    return {
        "total_registered": len(subs),
        "active_count": sum(1 for s in subs if s.is_active),
        "subscriptions": [
            {
                "id": s.id,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "is_active": s.is_active,
                "last_delivery_at": s.last_delivery_at.isoformat() if s.last_delivery_at else None,
                "endpoint_preview": s.endpoint[:40] + "..." if len(s.endpoint) > 40 else s.endpoint
            }
            for s in subs
        ]
    }

@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    ack_req: AcknowledgeRequest,
    authorized: bool = Depends(verify_admin_key),
    db: Session = Depends(get_db)
):
    """
    Acknowledges an active alert with the operator's name and optional response notes.
    """
    alert = db.query(LiveAlertEvent).filter(LiveAlertEvent.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert '{alert_id}' not found."
        )

    op_name = (ack_req.operator_name or ack_req.acknowledged_by or "Operator").strip()
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    alert.status = "ACKNOWLEDGED"
    alert.acknowledged_at = now_naive
    alert.acknowledged_by = op_name
    alert.acknowledgement_notes = ack_req.notes
    db.commit()

    return {
        "status": "ACKNOWLEDGED",
        "alert_id": alert_id,
        "new_status": "ACKNOWLEDGED",
        "acknowledged_by": op_name,
        "acknowledgement_notes": ack_req.notes,
        "acknowledged_at": now_naive.isoformat()
    }

@router.post("/evaluate-prediction")
async def evaluate_prediction(
    eval_req: EvaluatePredictionRequest,
    authorized: bool = Depends(verify_admin_key),
    db: Session = Depends(get_db)
):
    """
    Evaluates a hydrological model prediction (discharge vs bankfull capacity),
    persists the alert record, and dispatches multi-channel alerts if thresholds are breached.
    """
    discharge_val = eval_req.predicted_discharge if eval_req.predicted_discharge is not None else eval_req.predicted_discharge_m3s
    if discharge_val is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either predicted_discharge or predicted_discharge_m3s must be provided."
        )

    freshness = eval_req.data_freshness_minutes if eval_req.data_freshness_minutes is not None else 10.0
    if freshness > settings.RAINFALL_STALE_THRESHOLD_MINUTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Source data is stale ({freshness:.0f} min > {settings.RAINFALL_STALE_THRESHOLD_MINUTES} min limit). Cannot evaluate live warning."
        )

    evaluator = RainfallRiskEvaluator(zone=eval_req.zone)
    eval_res = evaluator.evaluate_prediction(
        predicted_discharge=discharge_val,
        bankfull_capacity=eval_req.bankfull_capacity,
        rate_of_rise=eval_req.rate_of_rise,
        is_simulation=eval_req.is_simulation,
        data_freshness_minutes=freshness,
        db=db
    )

    now_utc = datetime.now(timezone.utc)
    prefix = "SIM" if eval_req.is_simulation else "LIVE"
    alert_id = f"{prefix}-{now_utc.strftime('%Y%m%d%H%M')}-{uuid.uuid4().hex[:6]}"

    cap_xml_doc = None
    if eval_res.severity in ("WATCH", "WARNING", "CRITICAL"):
        cap_xml_doc = generate_cap_xml(
            identifier=alert_id,
            sender="FFEWS-CHUNGTHANG",
            event=eval_res.headline,
            urgency="Immediate" if eval_res.severity in ("WARNING", "CRITICAL") else "Expected",
            severity="Extreme" if eval_res.severity == "CRITICAL" else ("Severe" if eval_res.severity == "WARNING" else "Moderate"),
            certainty="Observed" if not eval_req.is_simulation else "Possible",
            headline=eval_res.headline,
            description=eval_res.description,
            instruction="Follow designated high-ground corridors away from Teesta river channel.",
            polygon_coordinates="27.58,88.63 27.58,88.66 27.62,88.66 27.62,88.63 27.58,88.63",
            area_desc=eval_req.zone
        )

    alert_event = LiveAlertEvent(
        id=alert_id,
        alert_type=eval_res.alert_type,
        severity=eval_res.severity,
        zone=eval_res.zone,
        headline=eval_res.headline,
        description=eval_res.description,
        trigger_rule=eval_res.trigger_rule,
        trigger_inputs=eval_res.trigger_inputs,
        threshold_config=eval_res.threshold_config,
        predicted_discharge=eval_res.predicted_discharge,
        threshold_value=eval_res.threshold_value,
        threshold_name=eval_res.threshold_name,
        data_freshness_minutes=eval_res.data_freshness_minutes,
        status="ACTIVE" if eval_res.severity != "NORMAL" else "RESOLVED",
        created_at=now_utc.replace(tzinfo=None),
        is_active=(eval_res.severity in ("WATCH", "WARNING", "CRITICAL")),
        cap_xml=cap_xml_doc
    )
    db.add(alert_event)
    db.commit()

    # Dispatch to multi-channel dispatcher if warning
    dispatcher = MultiChannelAlertDispatcher()
    dispatch_reports = {}
    if eval_res.should_notify:
        alert_payload = {
            "id": alert_id,
            "severity": eval_res.severity,
            "zone": eval_res.zone,
            "headline": eval_res.headline,
            "description": eval_res.description,
            "predicted_discharge": eval_res.predicted_discharge
        }
        dispatch_reports = dispatcher.dispatch_all(alert_payload, is_test=False, db=db)

    return {
        "id": alert_id,
        "alert_id": alert_id,
        "alert_type": eval_res.alert_type,
        "severity": eval_res.severity,
        "headline": eval_res.headline,
        "description": eval_res.description,
        "evaluation": eval_res.model_dump(),
        "dispatches": dispatch_reports
    }

@router.post("/test-notification")
async def send_test_notification(
    authorized: bool = Depends(verify_admin_key),
    db: Session = Depends(get_db)
):
    """
    Sends a standards-based test Web Push notification to registered browser endpoints.
    Explicitly marked TEST and never confused with a genuine flood event.
    """
    now_utc = datetime.now(timezone.utc)
    test_id = f"TEST-{now_utc.strftime('%Y%m%d%H%M')}-{uuid.uuid4().hex[:4]}"

    test_event = LiveAlertEvent(
        id=test_id,
        alert_type="TEST",
        severity="NORMAL",
        zone="Chungthang Basin (Test Domain)",
        headline="Multi-Channel Verification Ping",
        description="Operator initiated browser Web Push test verification.",
        trigger_rule="MANUAL_TEST_VERIFICATION",
        trigger_inputs={"initiated_by": "operator_console"},
        threshold_config={},
        predicted_discharge=0.0,
        threshold_value=0.0,
        threshold_name="Verification Ping",
        data_freshness_minutes=0.0,
        status="RESOLVED",
        created_at=now_utc.replace(tzinfo=None),
        is_active=False
    )
    db.add(test_event)
    db.commit()

    dispatcher = MultiChannelAlertDispatcher()
    payload = {
        "id": test_id,
        "severity": "TEST",
        "zone": "Chungthang Basin",
        "headline": "Browser Web Push Verification",
        "description": "Browser push notification verified successfully."
    }

    results = dispatcher.dispatch_all(payload, is_test=True, db=db)

    return {
        "test_event_id": test_id,
        "alert_type": "TEST",
        "dispatches": results
    }
