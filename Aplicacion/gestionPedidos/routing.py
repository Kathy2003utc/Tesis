from django.urls import path
from .consumers import PedidosConsumer, NotificacionesConsumer

websocket_urlpatterns = [
    path("ws/pedidos/", PedidosConsumer.as_asgi()),
    path("ws/notificaciones/<int:user_id>/", NotificacionesConsumer.as_asgi()),
]
