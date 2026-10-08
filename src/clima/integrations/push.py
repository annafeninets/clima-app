"""RFC 8030 Web Push delivery via pywebpush."""

import json
import os

from clima.errors import ServiceUnavailableError
from clima.models.value_objects import PushSubscription


class PushService:
    def send(
        self,
        subscription: PushSubscription,
        title: str,
        body: str,
        url: str = "/",
        tag: str = "daily-outfit",
    ) -> None:
        private_key = os.environ.get("CLIMA_VAPID_PRIVATE_KEY")
        subject = os.environ.get("CLIMA_VAPID_SUBJECT", "mailto:admin@localhost")
        if not private_key:
            raise ServiceUnavailableError("Не настроен ключ CLIMA_VAPID_PRIVATE_KEY для push")
        try:
            from pywebpush import WebPushException, webpush

            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=json.dumps({
                    "title": title[:40],
                    "body": body[:120],
                    "icon": "/icon-192.svg",
                    "badge": "/badge.svg",
                    "url": url,
                    "tag": tag,
                }, ensure_ascii=False),
                vapid_private_key=private_key,
                vapid_claims={"sub": subject},
                ttl=3600,
            )
        except ImportError as error:
            raise ServiceUnavailableError("Установите зависимость pywebpush для доставки push") from error
        except WebPushException as error:
            raise ServiceUnavailableError("Push-провайдер не принял уведомление") from error
