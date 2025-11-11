import os
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack
import pedidos.routing  # importa tus rutas de websocket

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Restaurante.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            pedidos.routing.websocket_urlpatterns
        )
    ),
})
