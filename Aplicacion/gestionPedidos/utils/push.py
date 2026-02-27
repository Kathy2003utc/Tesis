from pywebpush import webpush
from django.conf import settings
from ..models import PushSubscription
import json

def enviar_push(usuario, titulo, mensaje, url="/cajero/dashboard/"):

    subs = PushSubscription.objects.filter(usuario=usuario)

    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh,
                        "auth": sub.auth,
                    },
                },
                data=json.dumps({
                    "title": titulo,
                    "message": mensaje,
                    "url": url
                }),
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": "mailto:tuemail@gmail.com"},
            )
        except Exception:
            sub.delete()