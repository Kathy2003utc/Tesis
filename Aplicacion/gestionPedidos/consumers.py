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
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "nuevo_pedido",
                "pedido": data["pedido"],
            }
        )
    async def nuevo_pedido(self, event):
        await self.send(text_data=json.dumps({
            "type": "nuevo_pedido",
            "pedido": event["pedido"]
        }))

    async def actualizar_pedido(self, event):
        await self.send(text_data=json.dumps({
            "type": "actualizar_pedido",
            "pedido": event["pedido"]
        }))

    async def eliminar_pedido(self, event): 
        await self.send(text_data=json.dumps({
            "type": "eliminar_pedido",
            "pedido_id": event["pedido_id"],
            "origen": event.get("origen", ""),
            "accion": event.get("accion", "")
        }))

    async def nuevo_cobro(self, event):
        await self.send(text_data=json.dumps({
            "type": "nuevo_cobro",
            "origen": event.get("origen"),  
            "pedido_id": event["pedido_id"],

            "codigo_pedido": event.get("codigo_pedido"),
            
            # PARA RESTAURANTE:
            "mesa": event.get("mesa"),

            # PARA DOMICILIO:
            "cliente": event.get("cliente"),

            "mesero": event.get("mesero"),
            "total": event["total"],
            "estado_pago": event.get("estado_pago", "pendiente"),
            
        }))

    async def nuevo_pagado(self, event):
        await self.send(text_data=json.dumps({
            "type": "nuevo_pagado",
            "origen": event.get("origen"), 
            "pedido_id": event["pedido_id"],

            "codigo_pedido": event.get("codigo_pedido"),

            # RESTAURANTE:
            "mesa": event.get("mesa"),

            # DOMICILIO:
            "cliente": event.get("cliente"),

            "mesero": event.get("mesero"),
            "total": event["total"],
            "fecha": event["fecha"],
            "estado_pago": event.get("estado_pago", "confirmado"),

            "comprobante_url": event.get("comprobante_url", ""),
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
            "tipo": event.get("tipo"),
            "mensaje": event.get("mensaje"),

            "pedido": event.get("pedido"),

            "codigo_pedido": event.get("codigo_pedido"),

            "mesa": event.get("mesa"),

            "id": event.get("id"),
            "fecha": event.get("fecha"),
        }))

class CajeroPedidosConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = "pedidos_cajero"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def nuevo_pedido_cajero(self, event):
        await self.send(text_data=json.dumps({
            "type": "nuevo_pedido",
            "pedido": event["pedido"]
        }))


class ClienteEstadoPedidoConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope["url_route"]["kwargs"]["user_id"]
        self.group_name = f"estado_pedidos_cliente_{self.user_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def actualizar_estado(self, event):
        await self.send(text_data=json.dumps({
            "pedido": event["pedido"],
            "estado": event["estado"],
            "comprobante_url": event.get("comprobante_url")
        }))

