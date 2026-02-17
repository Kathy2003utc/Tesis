from django.urls import path
from .consumers import (
    PedidosConsumer,
    CajeroPedidosConsumer,
    NotificacionesConsumer,
    ClienteEstadoPedidoConsumer
)

websocket_urlpatterns = [
    path("ws/pedidos/", PedidosConsumer.as_asgi()),               # cocina / cobros
    path("ws/pedidos-cajero/", CajeroPedidosConsumer.as_asgi()), # SOLO cajero
    path("ws/notificaciones/<int:user_id>/", NotificacionesConsumer.as_asgi()),
    path("ws/estado-pedidos/<int:user_id>/", ClienteEstadoPedidoConsumer.as_asgi()),

]
