from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from .channel import NotificationChannel, DeliveryReport
from .web_push import WebPushNotificationChannel
from .sms import SMSNotificationChannel

class MultiChannelAlertDispatcher:
    """
    Coordinates alert delivery across all registered and configured notification channels
    (Web Push, SMS, CAP exports).
    """

    def __init__(self, channels: Optional[List[NotificationChannel]] = None):
        self.channels: Dict[str, NotificationChannel] = {}
        if channels:
            for c in channels:
                self.channels[c.channel_name] = c
        else:
            web_push = WebPushNotificationChannel()
            sms = SMSNotificationChannel()
            self.channels[web_push.channel_name] = web_push
            self.channels[sms.channel_name] = sms

    def get_channel_statuses(self) -> List[Dict[str, Any]]:
        return [c.get_status() for c in self.channels.values()]

    def dispatch_all(
        self,
        alert_payload: Dict[str, Any],
        is_test: bool = False,
        db: Optional[Session] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        results = {}
        for name, channel in self.channels.items():
            reports = channel.dispatch(alert_payload, is_test=is_test, db=db)
            results[name] = [r.model_dump() for r in reports]
        return results

    def dispatch_channel(
        self,
        channel_name: str,
        alert_payload: Dict[str, Any],
        is_test: bool = False,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        channel = self.channels.get(channel_name.upper())
        if not channel:
            raise ValueError(f"Unknown notification channel: {channel_name}")
        reports = channel.dispatch(alert_payload, is_test=is_test, db=db)
        return [r.model_dump() for r in reports]
