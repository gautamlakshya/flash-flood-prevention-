from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from ..config import settings
from .channel import NotificationChannel, DeliveryReport

class SMSNotificationChannel(NotificationChannel):
    """
    Architectural interface for SMS emergency alert dissemination.

    Compliance & Legal Requirements in India:
    - Commercial Communications Customer Preference Regulations (TCCCPR, 2018) by TRAI.
    - Requires mandatory Enterprise Entity Registration on Telecom Distributed Ledger Technology (DLT)
      portals (e.g. Jio, Airtel, Vodafone Idea, BSNL/Vilpower).
    - Header/Sender ID registration (e.g. 'SKMFLW' - exactly 6 alpha characters for transactional/service alerts).
    - Template registration with approved variables for emergency/disaster alerts.

    Status Policy:
    Until official telecom DLT registration, gateway authorization, and opt-in recipient registry
    are completed, this channel reports NOT CONFIGURED and does not simulate or dispatch fake SMS.
    """

    def __init__(self):
        self.enabled = settings.SMS_ENABLED
        self.gateway_url = settings.SMS_GATEWAY_URL
        self.entity_id = settings.SMS_ENTITY_ID
        self.sender_id = settings.SMS_SENDER_ID

    @property
    def channel_name(self) -> str:
        return "SMS"

    def is_configured(self) -> bool:
        return bool(self.enabled and self.gateway_url and self.entity_id and self.sender_id)

    def get_status(self) -> Dict[str, Any]:
        return {
            "channel": self.channel_name,
            "configured": self.is_configured(),
            "enabled": self.enabled,
            "status": "READY" if self.is_configured() else "NOT CONFIGURED",
            "regulatory_framework": "TRAI TCCCPR (2018) DLT Registration Required",
            "entity_id": self.entity_id if self.entity_id else "PENDING_REGISTRATION",
            "sender_id": self.sender_id if self.sender_id else "PENDING_APPROVAL",
            "notes": (
                "SMS channel interface is architecture-ready. Gateway integration remains "
                "decommissioned until authorized by Sikkim SDMA / NDMA and registered on TRAI DLT."
            )
        }

    def dispatch(
        self,
        alert_payload: Dict[str, Any],
        is_test: bool = False,
        db: Optional[Session] = None,
        **kwargs
    ) -> List[DeliveryReport]:
        now_utc = datetime.now(timezone.utc)

        if not self.is_configured():
            return [
                DeliveryReport(
                    channel=self.channel_name,
                    recipient_id="SMS_GATEWAY",
                    status="NOT_CONFIGURED",
                    timestamp=now_utc,
                    error="SMS gateway credentials and TRAI DLT Entity ID not configured."
                )
            ]

        # When configured with authorized gateway, dispatch logic would execute here.
        return []

