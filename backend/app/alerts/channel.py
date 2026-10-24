from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel

class DeliveryReport(BaseModel):
    channel: str
    recipient_id: str
    status: str  # SENT, FAILED, EXPIRED, SKIPPED, NOT_CONFIGURED
    timestamp: datetime
    error: Optional[str] = None
    response_metadata: Optional[Dict[str, Any]] = None

class NotificationChannel(ABC):
    """
    Abstract interface for emergency notification channels.
    Allows channels (WebPush, SMS, CAP) to be plugged in or extended
    without rewriting the alert evaluation engine.
    """
    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Name of the channel, e.g. WEB_PUSH, SMS."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Whether the channel has valid operational credentials."""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Returns readiness status and operational metadata."""
        pass

    @abstractmethod
    def dispatch(self, alert_payload: Dict[str, Any], is_test: bool = False, **kwargs) -> List[DeliveryReport]:
        """Dispatches an alert to recipients subscribed or registered for this channel."""
        pass
