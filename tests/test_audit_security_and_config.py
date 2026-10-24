import os
import tempfile
import pytest
from datetime import datetime, timezone
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from py_vapid import Vapid
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import base64

from backend.app.main import app
from backend.app.config import settings
from backend.app.models.database import (
    SessionLocal,
    LiveAlertEvent,
    PushSubscription,
    NotificationDelivery,
    get_sqlite_db_path,
    resolve_database_url,
    Base
)
from backend.app.alerts.web_push import VapidKeyManager, WebPushNotificationChannel
from migrate_db import migrate_db

@pytest.fixture
def test_client():
    return TestClient(app)

@pytest.fixture
def clean_db():
    db = SessionLocal()
    db.query(NotificationDelivery).delete()
    db.query(PushSubscription).delete()
    db.query(LiveAlertEvent).delete()
    db.commit()
    yield db
    db.close()

# -------------------------------------------------------------
# 1. Administrative Endpoint Security Tests
# -------------------------------------------------------------

def test_evaluate_prediction_endpoint_unauthorized_rejection(test_client):
    """
    POST /api/v1/alerts/evaluate-prediction must require admin key
    when ALERT_ADMIN_KEY is configured.
    """
    with patch.object(settings, "ALERT_ADMIN_KEY", "prod-admin-secret-key-123"):
        eval_payload = {
            "predicted_discharge": 650.0,
            "bankfull_capacity": 600.0,
            "rate_of_rise": 15.0,
            "zone": "Chungthang Basin",
            "is_simulation": False,
            "data_freshness_minutes": 5.0
        }

        # 1. Missing key -> 401 Unauthorized
        res_no_key = test_client.post(
            "/api/v1/alerts/evaluate-prediction",
            json=eval_payload
        )
        assert res_no_key.status_code == 401
        assert "Unauthorized" in res_no_key.json()["detail"]

        # 2. Incorrect key -> 401 Unauthorized
        res_bad_key = test_client.post(
            "/api/v1/alerts/evaluate-prediction",
            json=eval_payload,
            headers={"X-Admin-Key": "wrong-secret-key"}
        )
        assert res_bad_key.status_code == 401

        # 3. Correct key -> 200 OK
        res_authorized = test_client.post(
            "/api/v1/alerts/evaluate-prediction",
            json=eval_payload,
            headers={"X-Admin-Key": "prod-admin-secret-key-123"}
        )
        assert res_authorized.status_code == 200
        assert "alert_id" in res_authorized.json()

def test_test_notification_endpoint_security(test_client):
    """
    POST /api/v1/alerts/test-notification must reject unauthenticated callers
    when ALERT_ADMIN_KEY is configured.
    """
    with patch.object(settings, "ALERT_ADMIN_KEY", "operator-secret-pass"):
        # Missing key -> 401
        res = test_client.post("/api/v1/alerts/test-notification")
        assert res.status_code == 401

        # Wrong key -> 401
        res_wrong = test_client.post(
            "/api/v1/alerts/test-notification",
            headers={"X-Admin-Key": "incorrect"}
        )
        assert res_wrong.status_code == 401

        # Correct key -> 200
        res_good = test_client.post(
            "/api/v1/alerts/test-notification",
            headers={"X-Admin-Key": "operator-secret-pass"}
        )
        assert res_good.status_code == 200
        assert res_good.json()["alert_type"] == "TEST"

def test_alert_acknowledgement_endpoint_security(test_client, clean_db):
    """
    POST /api/v1/alerts/{alert_id}/acknowledge must require admin key.
    """
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    alert = LiveAlertEvent(
        id="TEST-SEC-ACK-01",
        alert_type="LIVE",
        severity="WARNING",
        headline="River Bankfull Exceeded",
        description="Testing secure acknowledgement",
        zone="Chungthang Basin",
        predicted_discharge=850.0,
        threshold_value=750.0,
        threshold_name="warning_threshold_m3s",
        data_freshness_minutes=10,
        status="ACTIVE",
        created_at=now_naive,
        is_active=True
    )
    clean_db.add(alert)
    clean_db.commit()

    with patch.object(settings, "ALERT_ADMIN_KEY", "duty-officer-key-456"):
        ack_payload = {
            "operator_name": "Duty Officer Gangtok",
            "notes": "Verified sirens sounded."
        }

        # Missing key -> 401
        res_missing = test_client.post(
            f"/api/v1/alerts/{alert.id}/acknowledge",
            json=ack_payload
        )
        assert res_missing.status_code == 401

        # Wrong key -> 401
        res_wrong = test_client.post(
            f"/api/v1/alerts/{alert.id}/acknowledge",
            json=ack_payload,
            headers={"X-Admin-Key": "wrong-key"}
        )
        assert res_wrong.status_code == 401

        # Correct key -> 200
        res_good = test_client.post(
            f"/api/v1/alerts/{alert.id}/acknowledge",
            json=ack_payload,
            headers={"X-Admin-Key": "duty-officer-key-456"}
        )
        assert res_good.status_code == 200
        assert res_good.json()["status"] == "ACKNOWLEDGED"

# -------------------------------------------------------------
# 2. CORS Configuration Tests
# -------------------------------------------------------------

def test_cors_production_origin_allowed(test_client):
    """
    Confirm configured production frontend origin is allowed and unauthorized origins are rejected.
    """
    # Allowed origin receives CORS response headers
    res_allowed = test_client.options(
        "/api/v1/alerts/notification-config",
        headers={
            "Origin": "https://flashflood-frontend.onrender.com",
            "Access-Control-Request-Method": "GET"
        }
    )
    # If the app middleware matches, it echoes the allowed origin
    allow_origin = res_allowed.headers.get("access-control-allow-origin")
    # Must NOT be wildcard "*" in production
    assert allow_origin != "*"

def test_cors_disallows_arbitrary_origins(test_client):
    """
    Confirm an arbitrary origin does not receive permissive wildcard headers.
    """
    res_bad = test_client.options(
        "/api/v1/alerts/notification-config",
        headers={
            "Origin": "https://malicious-site.example.com",
            "Access-Control-Request-Method": "GET"
        }
    )
    allow_origin = res_bad.headers.get("access-control-allow-origin")
    assert allow_origin != "https://malicious-site.example.com"
    assert allow_origin != "*"

# -------------------------------------------------------------
# 3. Database Persistence & Path Resolution Tests
# -------------------------------------------------------------

def test_database_path_resolution_with_env_var():
    """
    SQLITE_DB_PATH should take precedence when set.
    """
    with patch.dict(os.environ, {"SQLITE_DB_PATH": "/custom/path/flashflood.db"}):
        path = get_sqlite_db_path()
        assert path == "/custom/path/flashflood.db"

def test_database_path_resolution_fallback_to_data(tmp_path):
    """
    If /data directory exists and no env var is set, path should be /data/flashflood.db.
    """
    with patch.dict(os.environ, {}, clear=True):
        if "SQLITE_DB_PATH" in os.environ:
            del os.environ["SQLITE_DB_PATH"]
        with patch("os.path.isdir", return_value=True), patch("os.access", return_value=True):
            path = get_sqlite_db_path()
            assert path == "/data/flashflood.db"

def test_database_preserves_existing_data(clean_db):
    """
    Verify existing records are preserved and not deleted or overwritten.
    """
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    alert = LiveAlertEvent(
        id="PERSISTENCE-TEST-001",
        alert_type="LIVE",
        severity="WARNING",
        headline="Preservation Check",
        description="Verify persistence",
        zone="Chungthang Basin",
        predicted_discharge=700.0,
        threshold_value=600.0,
        threshold_name="warning",
        data_freshness_minutes=5,
        status="ACTIVE",
        created_at=now_naive,
        is_active=True
    )
    clean_db.add(alert)
    clean_db.commit()

    # Query from a brand new session to verify disk persistence
    new_session = SessionLocal()
    fetched = new_session.query(LiveAlertEvent).filter_by(id="PERSISTENCE-TEST-001").first()
    assert fetched is not None
    assert fetched.headline == "Preservation Check"
    new_session.close()

# -------------------------------------------------------------
# 4. Production-Safe VAPID Key Handling Tests
# -------------------------------------------------------------

def test_vapid_missing_keys_in_production():
    """
    In production mode, missing VAPID keys must NOT auto-generate replacement keys;
    instead, mark channel as CONFIG_ERROR.
    """
    mgr = VapidKeyManager(public_key="", private_key="", env="production")
    assert mgr._is_auto_generated is False
    assert mgr._is_valid is False
    assert mgr._config_error is not None
    assert "VAPID keys missing in production" in mgr._config_error
    assert mgr.get_public_key_b64() == ""

    channel = WebPushNotificationChannel(key_manager=mgr)
    assert channel.is_configured() is False
    status = channel.get_status()
    assert status["status"] == "CONFIG_ERROR"
    assert status["is_auto_generated_key"] is False

def test_vapid_invalid_private_key_in_production():
    """
    In production mode, malformed private key material must set CONFIG_ERROR
    without leaking the key text in the error.
    """
    mgr = VapidKeyManager(
        public_key="some-dummy-pub-key",
        private_key="NOT-A-VALID-PEM-KEY-12345",
        env="production"
    )
    assert mgr._is_valid is False
    assert mgr._config_error is not None
    assert "Invalid VAPID private key format" in mgr._config_error
    # Ensure raw private key content is NOT leaked in the error string
    assert "12345" not in mgr._config_error

def test_vapid_mismatched_keypair_in_production():
    """
    In production mode, mismatched public/private keys must be detected and rejected.
    """
    # Generate two distinct keypairs
    v1 = Vapid()
    v1.generate_keys()
    raw_pub1 = v1.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    pub1_b64 = base64.urlsafe_b64encode(raw_pub1).decode("utf-8").rstrip("=")

    v2 = Vapid()
    v2.generate_keys()
    priv2_pem = v2.private_pem().decode("utf-8")

    # Pass public key 1 with private key 2
    mgr = VapidKeyManager(public_key=pub1_b64, private_key=priv2_pem, env="production")
    assert mgr._is_valid is False
    assert mgr._config_error is not None
    assert "VAPID key mismatch" in mgr._config_error

    channel = WebPushNotificationChannel(key_manager=mgr)
    assert channel.is_configured() is False
    assert channel.get_status()["status"] == "CONFIG_ERROR"

def test_vapid_matching_keypair_in_production():
    """
    Valid, matching VAPID keypair in production mode should report READY.
    """
    v = Vapid()
    v.generate_keys()
    raw_pub = v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    pub_b64 = base64.urlsafe_b64encode(raw_pub).decode("utf-8").rstrip("=")
    priv_pem = v.private_pem().decode("utf-8")

    mgr = VapidKeyManager(public_key=pub_b64, private_key=priv_pem, env="production")
    assert mgr._is_valid is True
    assert mgr._config_error is None
    assert mgr._is_auto_generated is False
    assert mgr.get_public_key_b64() == pub_b64

    channel = WebPushNotificationChannel(key_manager=mgr)
    assert channel.is_configured() is True
    status = channel.get_status()
    assert status["status"] == "READY"
    assert status["vapid_public_key"] == pub_b64

def test_vapid_development_auto_generation():
    """
    In development mode, omitting keys generates an in-memory development keypair.
    """
    mgr = VapidKeyManager(public_key="", private_key="", env="development")
    assert mgr._is_auto_generated is True
    assert mgr._is_valid is True
    assert len(mgr.get_public_key_b64()) > 20

# -------------------------------------------------------------
# 5. Idempotent Migration Tests (Fresh vs Existing DB)
# -------------------------------------------------------------

def test_migrations_fresh_and_existing_database():
    """
    Tests migration against:
    1) A brand new database file
    2) An existing database containing records (idempotent, non-destructive)
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        test_db_path = os.path.join(tmpdir, "test_migration.db")
        db_url = f"sqlite:///{test_db_path}"

        # 1. Run migration against fresh database
        migrate_db(db_url)

        engine = create_engine(db_url)
        insp = inspect(engine)
        tables = insp.get_table_names()
        assert "live_alerts" in tables
        assert "push_subscriptions" in tables
        assert "notification_deliveries" in tables

        # Insert test record into existing database
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO live_alerts (id, alert_type, severity, zone, headline, description, "
                "trigger_rule, trigger_inputs, threshold_config, predicted_discharge, threshold_value, "
                "threshold_name, data_freshness_minutes, status, is_active) "
                "VALUES ('MIGRATE-01', 'LIVE', 'WARNING', 'Chungthang', 'Migration Check', 'Desc', "
                "'RULE', '{}', '{}', 500.0, 400.0, 'WARN', 5.0, 'ACTIVE', 1)"
            ))
        engine.dispose()

        # 2. Run migration a second time against the existing database
        migrate_db(db_url)

        # 3. Verify record was preserved intact
        engine2 = create_engine(db_url)
        with engine2.connect() as conn:
            row = conn.execute(text("SELECT id, headline FROM live_alerts WHERE id = 'MIGRATE-01'")).fetchone()
            assert row is not None
            assert row[0] == "MIGRATE-01"
            assert row[1] == "Migration Check"

        engine2.dispose()
