from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.db.models import Sum, F


# ----------------------------
# Usuario
# ----------------------------
ROL_CHOICES = (
    ('admin', 'Administrador'),
    ('mesero', 'Mesero'),
    ('cocinero', 'Cocinero'),
    ('cajero', 'Cajero'),
)

class Usuario(AbstractUser):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    telefono = models.CharField(max_length=15, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    correo = models.EmailField(unique=True)
    rol = models.CharField(max_length=20, choices=ROL_CHOICES)
    cambio_password = models.BooleanField(default=False)

    groups = models.ManyToManyField(
        Group,
        related_name='usuarios',
        blank=True,
        help_text='Grupos a los que pertenece el usuario.',
        verbose_name='grupos',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='usuarios_permisos',
        blank=True,
        help_text='Permisos específicos para el usuario.',
        verbose_name='permisos de usuario',
    )

    USERNAME_FIELD = 'correo'
    REQUIRED_FIELDS = ['username', 'nombre', 'apellido']

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.rol})"

# ----------------------------
# Mesa
# ----------------------------
class Mesa(models.Model):
    numero = models.PositiveIntegerField(unique=True)
    capacidad = models.PositiveIntegerField(default=4)
    estado = models.CharField(max_length=20, choices=[
        ('libre', 'Libre'),
        ('ocupada', 'Ocupada'),
    ], default='libre')

    def __str__(self):
        return f"Mesa {self.numero} ({self.estado})"

# ----------------------------
# Producto / Menú
# ----------------------------
class Producto(models.Model):
    TIPOS = [
        ('desayuno', 'Desayuno'),
        ('almuerzo', 'Almuerzo'),
        ('merienda', 'Merienda'),
        ('especial', 'Especiales'),
        ('bebida', 'Bebidas'),
    ]

    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    tipo = models.CharField(max_length=20, choices=TIPOS)

    def __str__(self):
        return self.nombre


# ----------------------------
# Pedido
# ----------------------------
class Pedido(models.Model):
    ESTADOS = [
        ('en_creacion', 'En creación'), 
        ('en preparacion', 'En preparación'),
        ('listo', 'Listo'),
        ('entregado', 'Entregado'),
        ('finalizado', 'Finalizado'),
    ]

    TIPOS = [
        ('restaurante', 'Restaurante'),
        ('domicilio', 'Domicilio'),
    ]

    cliente = models.ForeignKey(
        'Usuario',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pedidos_cliente',
        limit_choices_to={'rol': 'cliente'}
    )

    mesero = models.ForeignKey(
        'Usuario',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pedidos_mesero',
        limit_choices_to={'rol': 'mesero'}
    )

    cajero = models.ForeignKey(
        'Usuario',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pedidos_cajero',
        limit_choices_to={'rol': 'cajero'}
    )


    mesa = models.ForeignKey(
        'Mesa',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='pedidos'
    )

    estado = models.CharField(max_length=20, choices=ESTADOS, default='en_creacion')
    tipo_pedido = models.CharField(max_length=20, choices=TIPOS)
    direccion_entrega = models.CharField(max_length=255, blank=True, null=True)
    contacto_cliente = models.CharField(max_length=50, blank=True, null=True)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    recargo_domicilio = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def calcular_totales(self):
        # Subtotal de productos
        subtotal_calc = self.detalles.aggregate(
            total=Sum(F('precio_unitario') * F('cantidad'))
        )['total'] or 0

        # Recargo total de productos (por cantidad)
        recargo_total = self.detalles.aggregate(
            total_recargo=Sum(F('recargo') * F('cantidad'))
        )['total_recargo'] or 0

        self.subtotal = subtotal_calc

        if self.tipo_pedido == 'domicilio':
            self.total = self.subtotal + recargo_total + self.recargo_domicilio
        else:
            self.total = self.subtotal + recargo_total

        self.save()
    def __str__(self):
        return f"Pedido {self.id}"

# ----------------------------
# Detalle de pedido
# ----------------------------
class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey('Producto', on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # NUEVO CAMPO
    observacion = models.CharField(max_length=200, blank=True, null=True)
    recargo = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # <-- nuevo campo


    def save(self, *args, **kwargs):
        # Asigna precio actual del producto si no se define
        if not self.precio_unitario:
            self.precio_unitario = self.producto.precio

        # calcula subtotal
        self.subtotal = self.cantidad * self.precio_unitario

        super().save(*args, **kwargs)

        # actualizar subtotal total del pedido
        self.pedido.calcular_totales()
    
    @property
    def recargo_total(self):
        return self.recargo * self.cantidad

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre}"

# ----------------------------
# Pago
# ----------------------------
class Pago(models.Model):
    METODOS = [
        ('efectivo', 'Efectivo'),
        ('tarjeta', 'Tarjeta'),
        ('app', 'App'),
        ('transferencia', 'Transferencia'),
    ]
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('confirmado', 'Confirmado'),
        ('fallido', 'Fallido')
    ]
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='pagos')
    total = models.DecimalField(max_digits=10, decimal_places=2)
    metodo_pago = models.CharField(max_length=20, choices=METODOS)
    referencia_transferencia = models.CharField(max_length=100, blank=True, null=True)
    estado_pago = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    fecha_hora = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Pago Pedido {self.pedido.id} - {self.total}"

# ----------------------------
# Comprobante
# ----------------------------
class Comprobante(models.Model):
    TIPOS = [
        ('boleta', 'Boleta'),
        ('factura', 'Factura'),
        ('ticket', 'Ticket')
    ]
    pago = models.ForeignKey(Pago, on_delete=models.CASCADE)
    numero_comprobante = models.CharField(max_length=50, unique=True)
    tipo_comprobante = models.CharField(max_length=20, choices=TIPOS)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    nombre_cliente = models.CharField(max_length=100, blank=True, null=True)
    direccion_cliente = models.CharField(max_length=255, blank=True, null=True)
    correo_cliente = models.EmailField(blank=True, null=True)

    def __str__(self):
        return f"{self.tipo_comprobante} {self.numero_comprobante}"

# ----------------------------
# Notificación
# ----------------------------
class Notificacion(models.Model):
    ESTADOS = [
        ('leido', 'Leído'),
        ('no leido', 'No leído')
    ]

    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, null=True, blank=True)
    usuario_destino = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=50)
    mensaje = models.TextField(blank=True, null=True)   # <-- AQUI
    estado = models.CharField(max_length=20, choices=ESTADOS, default='no leido')
    fecha_hora = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notificación a {self.usuario_destino.nombre} - {self.tipo}"

# ----------------------------
# Mensaje
# ----------------------------
class Mensaje(models.Model):
    remitente = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="mensajes_enviados"
    )
    destinatario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="mensajes_recibidos"
    )
    contenido = models.TextField()
    fecha_hora = models.DateTimeField(auto_now_add=True)
    leido = models.BooleanField(default=False)

    def __str__(self):
        return f"De {self.remitente.nombre} para {self.destinatario.nombre}"
