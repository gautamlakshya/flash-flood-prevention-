import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings
from backend.app.models.database import (
    SessionLocal,
    RainfallRecord,
    ProviderHealth,
    LiveAlertEvent,
    NotificationDelivery,
    PushSubscription
)
from backend.app.ingestion.base import ProviderStatus
from backend.app.ingestion.rainfall.open_meteo import OpenMeteoRainfallProvider
from backend.app.ingestion.rainfall.gpm_imerg import GPMIMERGProvider
from backend.app.alerts.evaluator import RainfallRiskEvaluator
from backend.app.alerts.web_push import WebPushNotificationChannel, VapidKeyManager
from backend.app.alerts.sms import SMSNotificationChannel
from backend.app.alerts.dispatcher import MultiChannelAlertDispatcher

@pytest.fixture
def db_session():
    db = SessionLocal()
    # Clean up test rows
    db.query(NotificationDelivery).delete()
    db.query(PushSubscription).delete()
    db.query(LiveAlertEvent).delete()
    db.query(RainfallRecord).delete()
    db.query(ProviderHealth).delete()
    db.commit()
    yield db
    db.close()

@pytest.fixture
def test_client():
    return TestClient(app)

MOCK_OPEN_METEO_PAYLOAD = {
    "latitude": 27.6,
    "longitude": 88.65,
    "elevation": 1600.0,
    "generationtime_ms": 0.5,
    "timezone": "UTC",
    "hourly": {
        "time": [
            "2026-10-21T10:00",
            "2026-10-21T11:00",
            "2026-10-21T12:00"
        ],
        "precipitation": [0.0, 12.5, 35.0]
    }
}

def test_open_meteo_response_parsing_success():
    provider = OpenMeteoRainfallProvider(latitude=27.6033, longitude=88.6475)
    records = provider.validate_and_parse_response(MOCK_OPEN_METEO_PAYLOAD)

    assert len(records) == 3
    assert records[0]["source"] == "OPEN_METEO"
    assert records[0]["data_type"] == "FORECAST"
    assert records[0]["units"] == "mm"
    assert records[1]["precipitation_mm"] == 12.5
    assert records[2]["precipitation_mm"] == 35.0
    assert records[2]["valid_time"].hour == 12
    assert records[0]["valid_time"].tzinfo is not None  # Timezone aware

def test_open_meteo_validation_negative_nan_malformed():
    provider = OpenMeteoRainfallProvider(latitude=27.6033, longitude=88.6475)

    # 1. Negative precipitation
    bad_payload = {
        "latitude": 27.6,
        "longitude": 88.65,
        "hourly": {
            "time": ["2026-10-21T10:00"],
            "precipitation": [-5.0]
        }
    }
    with pytest.raises(ValueError, match="Negative precipitation rejected"):
        provider.validate_and_parse_response(bad_payload)

    # 2. Non-finite (NaN)
    nan_payload = {
        "latitude": 27.6,
        "longitude": 88.65,
        "hourly": {
            "time": ["2026-10-21T10:00"],
            "precipitation": [float("nan")]
        }
    }
    with pytest.raises(ValueError, match="Non-finite precipitation value"):
        provider.validate_and_parse_response(nan_payload)

    # 3. Coordinate mismatch (>1.0 deg away)
    coord_payload = {
        "latitude": 10.0,
        "longitude": 50.0,
        "hourly": {
            "time": ["2026-10-21T10:00"],
            "precipitation": [5.0]
        }
    }
    with pytest.raises(ValueError, match="deviate too far"):
        provider.validate_and_parse_response(coord_payload)

def test_open_meteo_provider_timeout_and_retries(db_session):
    provider = OpenMeteoRainfallProvider(timeout_seconds=1)

    with patch("requests.get", side_effect=Exception("Connection timed out")):
        records = provider.fetch_data(db=db_session, max_retries=2)
        assert records == []
        assert "Failed to fetch Open-Meteo" in provider.error_message

        health = db_session.query(ProviderHealth).filter(
            ProviderHealth.provider_name == "OPEN_METEO"
        ).first()
        assert health is not None
        assert health.status in (ProviderStatus.ERROR, ProviderStatus.UNAVAILABLE)
        assert health.consecutive_failures == 1

def test_open_meteo_deduplication_in_database(db_session):
    provider = OpenMeteoRainfallProvider(latitude=27.6033, longitude=88.6475)

    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_OPEN_METEO_PAYLOAD
        mock_get.return_value = mock_resp

        # Fetch once
        provider.fetch_data(db=db_session)
        count_first = db_session.query(RainfallRecord).count()
        assert count_first == 3

        # Fetch identical payload again
        provider.fetch_data(db=db_session)
        count_second = db_session.query(RainfallRecord).count()
        # Count must remain 3 without duplicates
        assert count_second == 3

def test_risk_evaluator_rolling_calculations_and_units(db_session):
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)

    # Insert 4 hourly readings: 10mm each
    for i in range(4):
        rec = RainfallRecord(
            source="OPEN_METEO",
            data_type="FORECAST",
            latitude=27.6033,
            longitude=88.6475,
            valid_time=now_naive - timedelta(hours=i),
            retrieval_time=now_naive,
            precipitation_mm=10.0,
            units="mm"
        )
        db_session.add(rec)
    db_session.commit()

    evaluator = RainfallRiskEvaluator()
    result = evaluator.evaluate(db=db_session)

    assert result.trigger_inputs["p_1h_mm"] == 10.0
    assert result.trigger_inputs["p_3h_mm"] == 30.0
    assert result.trigger_inputs["p_6h_mm"] == 40.0
    assert result.trigger_inputs["p_24h_mm"] == 40.0

def test_risk_evaluator_threshold_boundaries(db_session):
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    evaluator = RainfallRiskEvaluator()

    # Case 1: Normal (5mm in 1h)
    r1 = RainfallRecord(
        source="OPEN_METEO",
        data_type="FORECAST",
        latitude=27.6033,
        longitude=88.6475,
        valid_time=now_naive,
        retrieval_time=now_naive,
        precipitation_mm=5.0,
        units="mm"
    )
    db_session.add(r1)
    db_session.commit()
    res1 = evaluator.evaluate(db=db_session)
    assert res1.severity == "NORMAL"

    # Case 2: Watch (16mm in 1h >= 15mm watch)
    r1.precipitation_mm = 16.0
    db_session.commit()
    res2 = evaluator.evaluate(db=db_session)
    assert res2.severity == "WATCH"

    # Case 3: Warning (35mm in 1h >= 30mm warning)
    r1.precipitation_mm = 35.0
    db_session.commit()
    res3 = evaluator.evaluate(db=db_session)
    assert res3.severity == "WARNING"

    # Case 4: Critical (55mm in 1h >= 50mm critical)
    r1.precipitation_mm = 55.0
    db_session.commit()
    res4 = evaluator.evaluate(db=db_session)
    assert res4.severity == "CRITICAL"

def test_risk_evaluator_stale_and_unknown_handling(db_session):
    evaluator = RainfallRiskEvaluator(stale_threshold_minutes=60)

    # 1. No data in DB -> UNKNOWN (never false NORMAL)
    res_empty = evaluator.evaluate(db=db_session)
    assert res_empty.severity == "UNKNOWN"
    assert "No persisted" in res_empty.description

    # 2. Data older than stale threshold -> STALE (never false NORMAL)
    stale_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=150)
    old_rec = RainfallRecord(
        source="OPEN_METEO",
        data_type="FORECAST",
        latitude=27.6033,
        longitude=88.6475,
        valid_time=stale_time,
        retrieval_time=stale_time,
        precipitation_mm=2.0,
        units="mm"
    )
    db_session.add(old_rec)
    db_session.commit()

    res_stale = evaluator.evaluate(db=db_session)
    assert res_stale.severity == "STALE"
    assert "stale" in res_stale.headline.lower()

def test_risk_evaluator_hysteresis_and_deduplication(db_session):
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    evaluator = RainfallRiskEvaluator(cooldown_minutes=60)

    # 1. Create a Warning condition
    rec = RainfallRecord(
        source="OPEN_METEO",
        data_type="FORECAST",
        latitude=27.6033,
        longitude=88.6475,
        valid_time=now_naive,
        retrieval_time=now_naive,
        precipitation_mm=40.0,
        units="mm"
    )
    db_session.add(rec)
    db_session.commit()

    res_initial = evaluator.evaluate(db=db_session)
    assert res_initial.severity == "WARNING"
    assert res_initial.should_notify is True

    # Save active alert to DB
    alert_event = LiveAlertEvent(
        id="LIVE-TEST-1",
        alert_type="LIVE",
        severity="WARNING",
        headline=res_initial.headline,
        description=res_initial.description,
        trigger_rule=res_initial.trigger_rule,
        trigger_inputs=res_initial.trigger_inputs,
        threshold_config={},
        created_at=now_naive,
        is_active=True
    )
    db_session.add(alert_event)
    db_session.commit()

    # 2. Repeated evaluation 5 minutes later: same WARNING within cooldown
    eval_time_2 = now_naive + timedelta(minutes=5)
    res_repeat = evaluator.evaluate(db=db_session, now=eval_time_2.replace(tzinfo=timezone.utc))
    assert res_repeat.severity == "WARNING"
    # Deduplication check: should NOT spam duplicate notification within cooldown
    assert res_repeat.should_notify is False

    # 3. Resolution: rain recedes to 0mm
    rec.precipitation_mm = 0.0
    db_session.commit()
    res_resolved = evaluator.evaluate(db=db_session)
    assert res_resolved.severity == "NORMAL"
    assert res_resolved.is_resolution is True
    assert res_resolved.should_notify is True  # All-clear notification

def test_gpm_imerg_honest_not_configured():
    provider = GPMIMERGProvider(earthdata_token="")
    assert provider.get_status() == ProviderStatus.NOT_CONFIGURED
    assert "NASA Earthdata credentials not configured" in provider.error_message
    assert provider.fetch_data() == []

def test_vapid_key_manager_generation_and_export():
    manager = VapidKeyManager()
    pub_b64 = manager.get_public_key_b64()
    assert isinstance(pub_b64, str)
    assert len(pub_b64) >= 80  # P-256 base64url is typically ~87 chars

def test_web_push_channel_no_subscriptions(db_session):
    channel = WebPushNotificationChannel()
    reports = channel.dispatch({"headline": "Test"}, is_test=True, db=db_session)
    assert len(reports) == 1
    assert reports[0].status == "SKIPPED"
    assert "No active browser push subscriptions" in reports[0].error

def test_web_push_dispatch_mocked_success(db_session):
    # Add an active subscription
    sub = PushSubscription(
        endpoint="https://fcm.googleapis.com/fcm/send/test-device-token-12345",
        p256dh="BMaX...test-p256dh-key...",
        auth="test-auth-secret",
        user_agent="Mozilla/5.0 Test Browser",
        is_active=True
    )
    db_session.add(sub)
    db_session.commit()

    channel = WebPushNotificationChannel()
    mock_resp = MagicMock()
    mock_resp.status_code = 201

    with patch("backend.app.alerts.web_push.webpush", return_value=mock_resp):
        reports = channel.dispatch(
            {
                "id": "ALERT-PWA-1",
                "severity": "WARNING",
                "headline": "Flash Flood Warning - Chungthang",
                "description": "High discharge predicted.",
                "zone": "Chungthang Basin"
            },
            is_test=False,
            db=db_session
        )

    assert len(reports) == 1
    assert reports[0].status == "SENT"
    assert "PWA-SUB-" in reports[0].recipient_id

    # Verify database delivery record
    delivery = db_session.query(NotificationDelivery).filter(
        NotificationDelivery.channel == "WEB_PUSH"
    ).first()
    assert delivery is not None
    assert delivery.status == "SENT"
    assert "PWA-SUB-" in delivery.recipient_id

def test_web_push_dispatch_expired_subscription_deactivation(db_session):
    from pywebpush import WebPushException

    sub = PushSubscription(
        endpoint="https://updates.push.services.mozilla.com/wpush/v2/expired-endpoint-67890",
        p256dh="key",
        auth="auth",
        is_active=True
    )
    db_session.add(sub)
    db_session.commit()

    channel = WebPushNotificationChannel()

    mock_resp = MagicMock()
    mock_resp.status_code = 410  # 410 Gone / Expired
    mock_resp.text = "Subscription has expired or unsubscribed"
    mock_exception = WebPushException("Push failed: 410 Gone", response=mock_resp)

    with patch("backend.app.alerts.web_push.webpush", side_effect=mock_exception):
        reports = channel.dispatch({"headline": "Test"}, is_test=False, db=db_session)

    assert len(reports) == 1
    assert reports[0].status in ("EXPIRED", "FAILED")
    assert "410" in (reports[0].error or "") or "expired" in (reports[0].error or "").lower()

    # Subscription must have been automatically deactivated in DB
    db_session.refresh(sub)
    assert sub.is_active is False

def test_sms_channel_honest_not_configured(db_session):
    channel = SMSNotificationChannel()
    status = channel.get_status()
    assert "NOT CONFIGURED" in status["status"]
    assert "TRAI" in status["regulatory_framework"]

    reports = channel.dispatch({"headline": "Test"}, is_test=True, db=db_session)
    assert len(reports) == 1
    assert reports[0].status == "NOT_CONFIGURED"
    assert "TRAI DLT" in (reports[0].error or "")

def test_notification_config_endpoint_never_exposes_secrets(test_client):
    res = test_client.get("/api/v1/alerts/notification-config")
    assert res.status_code == 200
    data = res.json()
    assert "channels" in data
    channel_names = [c["channel"] for c in data["channels"]]
    assert "WEB_PUSH" in channel_names
    assert "SMS" in channel_names
    assert "TELEGRAM" not in channel_names

    # Ensure zero secrets leaked in config response
    json_str = str(data)
    assert "private" not in json_str.lower()
    assert "secret" not in json_str.lower()

def test_push_subscription_endpoints(test_client, db_session):
    # 1. Get VAPID public key
    res_key = test_client.get("/api/v1/alerts/push/vapid-public-key")
    assert res_key.status_code == 200
    key_data = res_key.json()
    assert "publicKey" in key_data or "public_key" in key_data
    pub_val = key_data.get("public_key") or key_data.get("publicKey")
    assert len(pub_val) >= 60

    # 2. Subscribe
    sub_payload = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/my-pwa-endpoint",
        "keys": {
            "p256dh": "dummy-p256dh-key",
            "auth": "dummy-auth-key"
        },
        "user_agent": "TestBrowser"
    }
    res_sub = test_client.post("/api/v1/alerts/push/subscribe", json=sub_payload)
    assert res_sub.status_code == 200
    assert res_sub.json()["status"] == "subscribed"

    # Verify stored in DB
    sub = db_session.query(PushSubscription).filter(
        PushSubscription.endpoint == sub_payload["endpoint"]
    ).first()
    assert sub is not None
    assert sub.is_active is True

    # 3. Unsubscribe
    res_unsub = test_client.post(
        "/api/v1/alerts/push/unsubscribe",
        json={"endpoint": sub_payload["endpoint"]}
    )
    assert res_unsub.status_code == 200
    assert res_unsub.json()["status"] == "unsubscribed"

    db_session.refresh(sub)
    assert sub.is_active is False

def test_evaluate_prediction_endpoint_stale_rejection(test_client):
    # Stale data (> 180 min) must be rejected with 422
    stale_payload = {
        "zone": "Chungthang Basin",
        "predicted_discharge_m3s": 950.0,
        "data_freshness_minutes": 240,  # Stale
        "is_simulation": False
    }
    res = test_client.post("/api/v1/alerts/evaluate-prediction", json=stale_payload)
    assert res.status_code == 422
    err_detail = str(res.json().get("detail", ""))
    assert "stale" in err_detail.lower()

def test_evaluate_prediction_simulation_vs_live(test_client, db_session):
    # 1. Simulation evaluation: 950 m³/s >= 900 m³/s bankfull capacity -> WARNING
    sim_payload = {
        "zone": "Chungthang Basin",
        "predicted_discharge_m3s": 950.0,
        "data_freshness_minutes": 15,
        "is_simulation": True,
        "reason": "Test cloudburst simulation run"
    }
    res_sim = test_client.post("/api/v1/alerts/evaluate-prediction", json=sim_payload)
    assert res_sim.status_code == 200
    data_sim = res_sim.json()
    assert data_sim["severity"] == "WARNING"
    assert data_sim["alert_type"] == "SIMULATION"
    assert "SIMULATION" in data_sim["headline"]

    # Verify persisted in DB with alert_type == "SIMULATION"
    sim_alert = db_session.query(LiveAlertEvent).filter(
        LiveAlertEvent.id == data_sim["id"]
    ).first()
    assert sim_alert is not None
    assert sim_alert.alert_type == "SIMULATION"

    # 2. Live evaluation: 1400 m³/s >= 1350 m³/s (150% bankfull capacity) -> CRITICAL
    live_payload = {
        "zone": "Lachen Sub-Basin",
        "predicted_discharge_m3s": 1400.0,
        "data_freshness_minutes": 5,
        "is_simulation": False,
        "reason": "Observed rapid sensor runoff surge"
    }
    res_live = test_client.post("/api/v1/alerts/evaluate-prediction", json=live_payload)
    assert res_live.status_code == 200
    data_live = res_live.json()
    assert data_live["severity"] == "CRITICAL"
    assert data_live["alert_type"] == "LIVE"

    live_alert = db_session.query(LiveAlertEvent).filter(
        LiveAlertEvent.id == data_live["id"]
    ).first()
    assert live_alert is not None
    assert live_alert.alert_type == "LIVE"

def test_alert_acknowledgement_endpoint(test_client, db_session):
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    alert = LiveAlertEvent(
        id="ALERT-ACK-TEST-001",
        alert_type="LIVE",
        severity="WARNING",
        headline="High River Stage Alert",
        description="Discharge exceeds threshold",
        zone="Chungthang Basin",
        predicted_discharge=820.0,
        threshold_value=750.0,
        threshold_name="warning_threshold_m3s",
        data_freshness_minutes=10,
        status="ACTIVE",
        created_at=now_naive,
        is_active=True
    )
    db_session.add(alert)
    db_session.commit()

    # Acknowledge
    ack_payload = {
        "acknowledged_by": "Officer R. Sharma (Sikkim SDMA)",
        "notes": "Emergency response team deployed to Chungthang dam axis."
    }
    res = test_client.post(f"/api/v1/alerts/{alert.id}/acknowledge", json=ack_payload)
    assert res.status_code == 200
    ack_data = res.json()
    assert ack_data["status"] == "ACKNOWLEDGED"
    assert ack_data["acknowledged_by"] == ack_payload["acknowledged_by"]
    assert ack_data["acknowledgement_notes"] == ack_payload["notes"]

    # Verify persisted in DB
    db_session.refresh(alert)
    assert alert.status == "ACKNOWLEDGED"
    assert alert.acknowledged_by == ack_payload["acknowledged_by"]
    assert alert.acknowledged_at is not None

def test_data_sources_status_includes_open_meteo_and_gpm(test_client):
    res = test_client.get("/api/v1/data_sources")
    assert res.status_code == 200
    sources = res.json()
    names = [s["name"] for s in sources]
    assert any("Open-Meteo" in name for name in names)
    assert any("NASA GPM" in name for name in names)

def test_ingest_and_evaluate_endpoint_protection(test_client):
    with patch.object(settings, "INGESTION_CRON_SECRET", "super-secret-cron-key"):
        bad_res = test_client.post(
            "/api/v1/rainfall/ingest-and-evaluate",
            headers={"X-Cron-Secret": "wrong-secret"}
        )
        assert bad_res.status_code == 401

        with patch.object(OpenMeteoRainfallProvider, "fetch_data", return_value=[]):
            good_res = test_client.post(
                "/api/v1/rainfall/ingest-and-evaluate",
                headers={"X-Cron-Secret": "super-secret-cron-key"}
            )
            assert good_res.status_code == 200
            assert good_res.json()["status"] == "success"

def test_manual_test_notification_endpoint(test_client, db_session):
    res = test_client.post("/api/v1/alerts/test-notification")
    assert res.status_code == 200
    data = res.json()
    assert "test_event_id" in data
    assert data["alert_type"] == "TEST"

    # Check audit event in DB
    test_event = db_session.query(LiveAlertEvent).filter(
        LiveAlertEvent.alert_type == "TEST"
    ).first()
    assert test_event is not None
    assert test_event.alert_type == "TEST"
    # Must NEVER be active to avoid confusing with live alerts
    assert test_event.is_active is False

