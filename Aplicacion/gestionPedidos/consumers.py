import json
from channels.generic.websocket import AsyncWebsocketConsumer

class PedidosConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = "pedidos_activos"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)

        # reenviar a todos los cocineros conectados
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "nuevo_pedido",
                "pedido": data["pedido"],
            }
        )

    async def nuevo_pedido(self, event):
        await self.send(text_data=json.dumps({
            "pedido": event["pedido"]
        }))

class NotificacionesConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope["url_route"]["kwargs"]["user_id"]
        self.group_name = f"notificaciones_{self.user_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        pass  # no recibimos nada desde frontend aquí

    async def enviar_notificacion(self, event):
        await self.send(text_data=json.dumps({
            "mensaje": event["mensaje"],
            "pedido": event["pedido"],
        }))
