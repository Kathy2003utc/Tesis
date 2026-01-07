import os
import django
from django.core.asgi import get_asgi_application
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

from Aplicacion.gestionPedidos import routing  # tus rutas WebSocket

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Restaurante.settings")

# Carga Django (ok mantenerlo)
django.setup()

django_asgi_app = get_asgi_application()

application = ASGIStaticFilesHandler(
    ProtocolTypeRouter({
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(
            URLRouter(routing.websocket_urlpatterns)
        ),
    })
)
