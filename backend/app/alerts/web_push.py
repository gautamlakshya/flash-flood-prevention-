import os
import json
import base64
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid
from pywebpush import webpush, WebPushException

from ..config import settings
from ..models.database import PushSubscription, NotificationDelivery
from .channel import NotificationChannel, DeliveryReport

class VapidKeyManager:
    """
    Manages VAPID keypair for Web Push protocol (RFC 8292).
    In development mode: Generates an in-memory keypair if not provided in environment.
    In production mode: Strictly requires valid, matching VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY.
    Never silently auto-generates replacement keys in production.
    Never logs or leaks private key material.
    """
    _instance: Optional['VapidKeyManager'] = None

    def __init__(
        self,
        public_key: Optional[str] = None,
        private_key: Optional[str] = None,
        env: Optional[str] = None
    ):
        self.env = (env if env is not None else settings.ENV).lower().strip()
        self.is_production = self.env in ("production", "prod")

        raw_pub = public_key if public_key is not None else settings.VAPID_PUBLIC_KEY
        raw_priv = private_key if private_key is not None else settings.VAPID_PRIVATE_KEY

        self.public_key_b64: str = raw_pub.strip() if raw_pub else ""
        self.private_key_pem: str = raw_priv.strip() if raw_priv else ""
        self.claims: Dict[str, str] = {"sub": settings.VAPID_CLAIM_EMAIL}

        self._is_auto_generated: bool = False
        self._config_error: Optional[str] = None
        self._is_valid: bool = False

        self._initialize_and_validate_keys()

    def _initialize_and_validate_keys(self):
        # Case 1: Keys missing
        if not self.public_key_b64 or not self.private_key_pem:
            if self.is_production:
                self._config_error = (
                    "VAPID keys missing in production environment: VAPID_PUBLIC_KEY and "
                    "VAPID_PRIVATE_KEY must be provided via environment variables."
                )
                self._is_valid = False
                self._is_auto_generated = False
                self.public_key_b64 = ""
                self.private_key_pem = ""
                return
            else:
                # In development/test mode only: auto-generate in-memory keys
                try:
                    v = Vapid()
                    v.generate_keys()
                    raw_pub = v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
                    self.public_key_b64 = base64.urlsafe_b64encode(raw_pub).decode("utf-8").rstrip("=")
                    self.private_key_pem = v.private_pem().decode("utf-8")
                    self._is_auto_generated = True
                    self._is_valid = True
                    self._config_error = None
                except Exception as e:
                    self._config_error = f"Failed to generate development VAPID keys: {type(e).__name__}"
                    self._is_valid = False
                return

        # Case 2: Keys provided - validate format and pair matching
        # Note: We NEVER log, print, or leak private key material.
        pem_data = self.private_key_pem
        if os.path.exists(pem_data):
            try:
                with open(pem_data, "r", encoding="utf-8") as f:
                    pem_data = f.read().strip()
            except Exception as e:
                self._config_error = f"Failed to read VAPID private key file: {type(e).__name__}"
                self._is_valid = False
                return

        # Normalize escaped newlines from environment variables
        pem_data = pem_data.replace("\\n", "\n")

        try:
            if "BEGIN" in pem_data:
                vapid_obj = Vapid.from_pem(pem_data.encode("utf-8"))
            else:
                vapid_obj = Vapid.from_string(pem_data)
        except Exception as e:
            self._config_error = f"Invalid VAPID private key format: {type(e).__name__}"
            self._is_valid = False
            return

        try:
            raw_pub = vapid_obj.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
            derived_pub_b64 = base64.urlsafe_b64encode(raw_pub).decode("utf-8").rstrip("=")
            configured_pub_b64 = self.public_key_b64.rstrip("=")

            if derived_pub_b64 != configured_pub_b64:
                self._config_error = (
                    "VAPID key mismatch: Configured VAPID_PUBLIC_KEY does not correspond "
                    "to the configured VAPID_PRIVATE_KEY."
                )
                self._is_valid = False
                return

            # Keypair validated successfully
            self._is_valid = True
            self._config_error = None
            self.private_key_pem = pem_data
            self._is_auto_generated = False
        except Exception as e:
            self._config_error = f"Failed to validate VAPID keypair: {type(e).__name__}"
            self._is_valid = False

    def get_public_key_b64(self) -> str:
        if not self._is_valid:
            return ""
        return self.public_key_b64

    @classmethod
    def reset_instance(cls):
        cls._instance = None

    @classmethod
    def get_instance(cls) -> 'VapidKeyManager':
        if cls._instance is None:
            cls._instance = VapidKeyManager()
        return cls._instance

class WebPushNotificationChannel(NotificationChannel):
    """
    Standards-based Web Push Notification Channel (W3C Push API / IETF Web Push).
    Sends browser push notifications directly to subscribed devices (PWA on desktop, Android, iOS).
    """

    def __init__(self, key_manager: Optional[VapidKeyManager] = None):
        self.key_mgr = key_manager or VapidKeyManager.get_instance()
        self.enabled = settings.WEB_PUSH_ENABLED

    @property
    def channel_name(self) -> str:
        return "WEB_PUSH"

    def is_configured(self) -> bool:
        return bool(self.key_mgr._is_valid and self.enabled and not self.key_mgr._config_error)

    def get_public_key(self) -> str:
        """Returns the public key required by the browser pushManager.subscribe()."""
        return self.key_mgr.get_public_key_b64()

    def get_status(self) -> Dict[str, Any]:
        if self.key_mgr._config_error:
            status_str = "CONFIG_ERROR"
        elif self.is_configured():
            status_str = "READY"
        else:
            status_str = "NOT CONFIGURED"

        return {
            "channel": self.channel_name,
            "configured": self.is_configured(),
            "enabled": self.enabled,
            "vapid_public_key": self.get_public_key(),
            "claim_email": self.key_mgr.claims.get("sub"),
            "status": status_str,
            "is_auto_generated_key": getattr(self.key_mgr, "_is_auto_generated", False),
            "config_error": self.key_mgr._config_error,
            "notes": (
                self.key_mgr._config_error
                if self.key_mgr._config_error
                else "Standards-based Web Push for PWA. Requires browser permission and active subscription."
            )
        }

    def _format_payload(self, alert_payload: Dict[str, Any], is_test: bool = False) -> Dict[str, Any]:
        severity = alert_payload.get("severity", "WARNING").upper()
        zone = alert_payload.get("zone", "Chungthang Basin (Teesta River)")
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        if is_test:
            return {
                "title": "🧪 CHUNGTHANG FFEWS — TEST PUSH",
                "body": f"Push delivery verified successfully for {zone}. No emergency action required.",
                "zone": zone,
                "severity": "TEST",
                "timestamp": now_str,
                "tag": "ffews-test-alert",
                "data": {
                    "url": "/alerts",
                    "type": "TEST"
                }
            }

        headline = alert_payload.get("headline", "Flash Flood Warning")
        description = alert_payload.get("description", "")
        q_pred = alert_payload.get("predicted_discharge")
        q_str = f" | Peak Q: {q_pred:.0f} m³/s" if q_pred else ""

        icon_prefix = "🚨" if severity in ("WARNING", "CRITICAL") else ("⚠️" if severity == "WATCH" else "ℹ️")

        return {
            "title": f"{icon_prefix} {severity}: {zone}",
            "body": f"{headline}{q_str}. {description[:120]} Action: Move away from low-lying Teesta riverbanks.",
            "zone": zone,
            "severity": severity,
            "timestamp": now_str,
            "tag": f"ffews-alert-{alert_payload.get('id', 'live')}",
            "data": {
                "url": "/alerts",
                "alert_id": alert_payload.get("id"),
                "severity": severity
            }
        }

    def dispatch(
        self,
        alert_payload: Dict[str, Any],
        is_test: bool = False,
        db: Optional[Session] = None,
        **kwargs
    ) -> List[DeliveryReport]:
        """
        Dispatches push notifications to all active subscriptions in the database.
        """
        now_utc = datetime.now(timezone.utc)
        alert_id = alert_payload.get("id") or alert_payload.get("alert_event_id")

        if not self.enabled:
            return [
                DeliveryReport(
                    channel=self.channel_name,
                    recipient_id="ALL",
                    status="SKIPPED",
                    timestamp=now_utc,
                    error="WEB_PUSH_ENABLED is set to false."
                )
            ]

        if not self.is_configured():
            err_msg = self.key_mgr._config_error or "Web Push channel is not configured with valid VAPID keys."
            return [
                DeliveryReport(
                    channel=self.channel_name,
                    recipient_id="ALL",
                    status="SKIPPED",
                    timestamp=now_utc,
                    error=err_msg
                )
            ]

        if not db:
            return [
                DeliveryReport(
                    channel=self.channel_name,
                    recipient_id="UNKNOWN",
                    status="SKIPPED",
                    timestamp=now_utc,
                    error="Database session required to fetch subscriptions."
                )
            ]

        # Fetch active subscriptions
        subscriptions = db.query(PushSubscription).filter(
            PushSubscription.is_active == True
        ).all()

        if not subscriptions:
            report = DeliveryReport(
                channel=self.channel_name,
                recipient_id="NONE",
                status="SKIPPED",
                timestamp=now_utc,
                error="No active browser push subscriptions registered."
            )
            self._persist_delivery(db, alert_id, "NONE", "SKIPPED", report.error, None)
            return [report]

        payload_dict = self._format_payload(alert_payload, is_test=is_test)
        payload_json = json.dumps(payload_dict)

        reports = []

        for sub in subscriptions:
            # Mask recipient for privacy & auditing
            endpoint_hash = hashlib.sha256(sub.endpoint.encode("utf-8")).hexdigest()[:12]
            masked_recipient = f"PWA-SUB-{endpoint_hash}"

            subscription_info = {
                "endpoint": sub.endpoint,
                "keys": {
                    "p256dh": sub.p256dh,
                    "auth": sub.auth
                }
            }

            try:
                # webpush
                response = webpush(
                    subscription_info=subscription_info,
                    data=payload_json,
                    vapid_private_key=self.key_mgr.private_key_pem,
                    vapid_claims=self.key_mgr.claims,
                    timeout=5
                )

                if response.status_code in (200, 201):
                    sub.last_delivery_at = now_utc.replace(tzinfo=None)
                    rep = DeliveryReport(
                        channel=self.channel_name,
                        recipient_id=masked_recipient,
                        status="SENT",
                        timestamp=now_utc,
                        response_metadata={"status_code": response.status_code}
                    )
                    self._persist_delivery(db, alert_id, masked_recipient, "SENT", None, {"status_code": response.status_code})
                elif response.status_code in (404, 410):
                    # Subscription has expired or user unsubscribed at browser level
                    sub.is_active = False
                    rep = DeliveryReport(
                        channel=self.channel_name,
                        recipient_id=masked_recipient,
                        status="EXPIRED",
                        timestamp=now_utc,
                        error=f"Push endpoint expired (HTTP {response.status_code}). Subscription deactivated."
                    )
                    self._persist_delivery(db, alert_id, masked_recipient, "EXPIRED", rep.error, None)
                else:
                    rep = DeliveryReport(
                        channel=self.channel_name,
                        recipient_id=masked_recipient,
                        status="FAILED",
                        timestamp=now_utc,
                        error=f"Push service rejected: HTTP {response.status_code}"
                    )
                    self._persist_delivery(db, alert_id, masked_recipient, "FAILED", rep.error, None)

            except WebPushException as e:
                # Check if it was 404/410
                is_expired = False
                if hasattr(e, "response") and e.response is not None:
                    if e.response.status_code in (404, 410):
                        sub.is_active = False
                        is_expired = True

                status = "EXPIRED" if is_expired else "FAILED"
                err_text = str(e)
                rep = DeliveryReport(
                    channel=self.channel_name,
                    recipient_id=masked_recipient,
                    status=status,
                    timestamp=now_utc,
                    error=err_text
                )
                self._persist_delivery(db, alert_id, masked_recipient, status, err_text, None)

            except Exception as e:
                err_text = f"Delivery error: {str(e)}"
                rep = DeliveryReport(
                    channel=self.channel_name,
                    recipient_id=masked_recipient,
                    status="FAILED",
                    timestamp=now_utc,
                    error=err_text
                )
                self._persist_delivery(db, alert_id, masked_recipient, "FAILED", err_text, None)

            reports.append(rep)

        db.commit()
        return reports

    def _persist_delivery(
        self,
        db: Session,
        alert_id: Optional[str],
        recipient_id: str,
        status: str,
        error_msg: Optional[str],
        response_json: Optional[Dict[str, Any]]
    ):
        try:
            deliv = NotificationDelivery(
                alert_id=alert_id,
                channel=self.channel_name,
                recipient_id=recipient_id,
                status=status,
                attempt_time=datetime.now(timezone.utc).replace(tzinfo=None),
                error_message=error_msg,
                response_json=response_json
            )
            db.add(deliv)
            db.commit()
        except Exception:
            db.rollback()
