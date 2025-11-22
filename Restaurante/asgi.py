import os
import django
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
from Aplicacion.gestionPedidos import routing  # importa tus rutas de WebSocket

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Restaurante.settings')

# 🔹 Aseguramos que Django esté cargado antes de usar las rutas
django.setup()

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            routing.websocket_urlpatterns
        )
    ),
})
