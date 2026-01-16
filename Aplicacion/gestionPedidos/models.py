from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.db.models import Sum, F, DecimalField
from django.utils import timezone    
from django.db.models import Max  
from django.conf import settings


# ----------------------------
# Usuario
# ----------------------------
ROL_CHOICES = (
    ('admin', 'Administrador'),
    ('mesero', 'Mesero'),
    ('cocinero', 'Cocinero'),
    ('cajero', 'Cajero'),
)

HORARIO_CHOICES = (
    ('lv_manana', 'L-V Mañana (06:00 - 14:00)'),
    ('lv_tarde',  'L-V Tarde (14:00 - 22:00)'),
    ('lv_noche',  'L-V Noche (22:00 - 06:00)'),

    ('sab_manana', 'Sábado Mañana (06:00 - 12:00)'),
    ('sab_tarde',  'Sábado Tarde (11:00 - 15:00)'),
    ('dom_unico',  'Domingo Único (06:00 - 13:00)'),
)

class Usuario(AbstractUser):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    telefono = models.CharField(max_length=15, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    correo = models.EmailField(unique=True)
    rol = models.CharField(max_length=20, choices=ROL_CHOICES)

    horario = models.CharField(max_length=20, choices=HORARIO_CHOICES, blank=True, null=True)

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
    
    @property
    def tiene_interacciones(self):
        """
        Devuelve True si el usuario ya ha interactuado en el sistema
        (pedidos, mensajes, notificaciones), False en caso contrario.
        """

        return (
            self.pedidos_mesero.exists() or
            self.pedidos_cajero.exists() or
            self.pedidos_cliente.exists() or
            self.mensajes_enviados.exists() or
            self.mensajes_recibidos.exists() or
            Notificacion.objects.filter(usuario_destino=self).exists()
        )

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
    activo = models.BooleanField(default=True)

    agotado_fecha = models.DateField(blank=True, null=True)  
    agotado_hora = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.nombre
    
    @property
    def agotado_hoy(self):
        return self.agotado_fecha == timezone.localdate()

    @property
    def disponible_hoy(self):
        # activo y NO agotado hoy
        return self.activo and not self.agotado_hoy

    @property
    def tiene_pedidos(self):
        # Usa el related_name por defecto del FK en DetallePedido
        return self.detallepedido_set.exists()


# ----------------------------
# Pedido
# ----------------------------
class Pedido(models.Model):
    ESTADOS = [
        ('borrador', 'Borrador'),
        ('en_creacion', 'En creación'), 
        ('en preparacion', 'En preparación'),
        ('listo', 'Listo'),
        ('finalizado', 'Finalizado'), 
    ]

    TIPOS = [
        ('restaurante', 'Restaurante'),
        ('domicilio', 'Domicilio'),
    ]

    cliente = models.ForeignKey( 'Usuario', on_delete=models.SET_NULL, null=True, blank=True, related_name='pedidos_cliente', limit_choices_to={'rol': 'cliente'} )


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
    nombre_cliente = models.CharField(max_length=150, blank=True, null=True)
    direccion_entrega = models.CharField(max_length=255, blank=True, null=True)
    contacto_cliente = models.CharField(max_length=50, blank=True, null=True)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    enviado_cocina = models.BooleanField(default=False)

    codigo_pedido = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True
    )

    def calcular_totales(self):

        # Subtotal de productos
        subtotal_calc = self.detalles.aggregate(
            total=Sum(
                F('precio_unitario') * F('cantidad'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        )['total'] or 0

        # Recargo total (recargo unitario * cantidad)
        recargo_total = self.detalles.aggregate(
            total_recargo=Sum(
                F('recargo') * F('cantidad'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        )['total_recargo'] or 0

        # Guardar subtotal
        self.subtotal = subtotal_calc

        # Total final del pedido
        self.total = self.subtotal + recargo_total

        self.save()
    
    @property
    def total_recargos(self):
        return self.detalles.aggregate(
            total=Sum(
                F('recargo') * F('cantidad'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        )['total'] or 0

    def generar_codigo(self):
        ultimo = Pedido.objects.filter(
            codigo_pedido__startswith="PCG-"
        ).aggregate(Max('codigo_pedido'))['codigo_pedido__max']

        if ultimo:
            numero = int(ultimo.replace("PCG-", "")) + 1
        else:
            numero = 1

        return f"PCG-{numero:05d}"
    
    def save(self, *args, **kwargs):
        if not self.codigo_pedido:
            self.codigo_pedido = self.generar_codigo()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Pedido {self.id}"
    
    @property
    def cliente_nombre(self):
        # 1) Si tiene cliente (FK), usar su nombre real
        if self.cliente_id:
            return f"{self.cliente.nombre} {self.cliente.apellido}".strip()

        # 2) Si no hay FK, usar el campo nombre_cliente
        if self.nombre_cliente and self.nombre_cliente.strip():
            return self.nombre_cliente.strip()

        # 3) Si no hay nada, devolver vacío (pero tú quieres sí o sí, así que esto NO debería pasar)
        return ""

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
    

    @property
    def total_con_recargo(self):
        return self.subtotal + self.recargo_total

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre}"

# ----------------------------
# Pago
# ----------------------------
class Pago(models.Model):
    METODOS = [
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia'),
    ]
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('confirmado', 'Confirmado'),
    ]

    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='pagos')
    total = models.DecimalField(max_digits=10, decimal_places=2)
    metodo_pago = models.CharField(max_length=20, choices=METODOS)
    monto_recibido = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cambio = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    referencia_transferencia = models.CharField(max_length=100, blank=True, null=True)
    estado_pago = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    fecha_hora = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Pago Pedido {self.pedido.id} - {self.total}"

# ----------------------------
# Comprobante
# ----------------------------
class Comprobante(models.Model):
    pago = models.ForeignKey(Pago, on_delete=models.CASCADE)
    numero_comprobante = models.CharField(max_length=50, unique=True)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    nombre_cliente = models.CharField(max_length=100, blank=True, null=True)
    direccion_cliente = models.CharField(max_length=255, blank=True, null=True)
    correo_cliente = models.EmailField(blank=True, null=True)

    archivo_pdf = models.FileField(
        upload_to='comprobantes/',
        blank=True,
        null=True
    )

    def __str__(self):
        return f"Comprobante {self.numero_comprobante}"

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
