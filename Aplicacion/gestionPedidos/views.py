import json
import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from .decorators import rol_requerido
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password
from .models import Usuario, Mesa, Pedido, DetallePedido, Producto, Notificacion, Mensaje, Pago, Comprobante
from django.contrib.auth.hashers import make_password
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.db.models import Sum, F
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.views.decorators.csrf import csrf_protect
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import localtime
from django.db.models import Exists, OuterRef
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.http import HttpResponse
from django.template.loader import get_template
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Image
import os
from django.conf import settings
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.drawing.image import Image as ExcelImage
from django.utils import timezone
from weasyprint import HTML
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
import tempfile
from django.views.decorators.http import require_POST

# ----------------------------
# Login (pantalla)
# ----------------------------
def login_view(request):
    return render(request, "login/login.html")

# ----------------------------
# Iniciar sesión
# ----------------------------
def iniciar_sesion(request):
    if request.method == 'POST':
        correo = request.POST.get('correo')
        password = request.POST.get('password')

        usuario = authenticate(request, correo=correo, password=password)

        if usuario is not None:
            auth_login(request, usuario)

            # Guardar datos en sesión
            request.session['usuario_id'] = usuario.id
            request.session['usuario_rol'] = usuario.rol
            request.session['usuario_nombre'] = f"{usuario.nombre} {usuario.apellido}"

            # 👇 Si es su primer ingreso, debe cambiar su contraseña
            if not usuario.cambio_password:
                return redirect('cambiar_password_primera_vez')

            # Redirección según rol
            if usuario.rol == 'admin':
                return redirect('dashboard_admin')
            elif usuario.rol == 'mesero':
                return redirect('dashboard_mesero')
            elif usuario.rol == 'cocinero':
                return redirect('vista_cocina')
            elif usuario.rol == 'cajero':
                return redirect('dashboard_cajero')
            else:
                messages.error(request, "Rol desconocido.")
        else:
            messages.error(request, "Correo o contraseña incorrectos.")

    return render(request, 'login/login.html')

# ----------------------------
# Cerrar sesión
# ----------------------------
@login_required(login_url='login')
def cerrar_sesion(request):
    auth_logout(request)
    request.session.flush()
    return redirect('login')

# ----------------------------
# Cambio de contraseña
# ----------------------------
@login_required(login_url='login')
def cambiar_password_primera_vez(request):
    if request.method == 'POST':
        nueva = request.POST.get('nueva')
        confirmar = request.POST.get('confirmar')

        if nueva and confirmar and nueva == confirmar:
            request.user.set_password(nueva)
            request.user.cambio_password = True
            request.user.save()
            messages.success(request, "Contraseña cambiada correctamente. Inicia sesión nuevamente.")
            return redirect('login')
        else:
            messages.error(request, "Las contraseñas no coinciden.")

    return render(request, 'login/cambiar_password_primera_vez.html')

# ----------------------------
# Dashboards protegidos por rol
# ----------------------------
@login_required(login_url='login')
def dashboard_admin(request):
    if request.user.rol != 'admin':
        messages.error(request, "No tienes permisos para acceder a esta página.")
        return redirect('login')
    return render(request, 'administrador/dashboard.html')

@login_required(login_url='login')
def dashboard_mesero(request):
    if request.user.rol != 'mesero':
        messages.error(request, "No tienes permisos para acceder a esta página.")
        return redirect('login')
    return render(request, 'mesero/dashboard.html')

@login_required(login_url='login')
def dashboard_cocinero(request):
    if request.user.rol != 'cocinero':
        messages.error(request, "No tienes permisos para acceder a esta página.")
        return redirect('login')
    return render(request, 'cocinero/dashboard.html')

@login_required(login_url='login')
def dashboard_cajero(request):
    if request.user.rol != 'cajero':
        messages.error(request, "No tienes permisos para acceder a esta página.")
        return redirect('login')
    return render(request, 'cajero/dashboard.html')

# ----------------------------
# Admin-Perfil
# ----------------------------
@login_required(login_url='login')
@rol_requerido('admin')
def perfil_admin(request):
    usuario = request.user   # usuario logueado
    return render(request, "administrador/perfil.html", {"usuario": usuario})

@login_required(login_url='login')
@rol_requerido('admin')
def editar_perfil_admin(request):
    usuario = request.user  # administrador logueado

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        apellido = request.POST.get("apellido", "").strip()
        correo = request.POST.get("correo", "").strip()
        telefono = request.POST.get("telefono", "").strip()
        direccion = request.POST.get("direccion", "").strip()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")

        # -----------------------------
        # VALIDACIONES BACKEND
        # -----------------------------

        # Nombre y apellido: solo letras
        if not re.match(r'^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$', nombre):
            messages.error(request, "El nombre solo debe contener letras.")
            return render(request, "administrador/editar_perfil_admin.html", {"usuario": usuario})

        if not re.match(r'^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$', apellido):
            messages.error(request, "El apellido solo debe contener letras.")
            return render(request, "administrador/editar_perfil_admin.html", {"usuario": usuario})

        # Correo obligatorio + válido
        if not correo:
            messages.error(request, "El correo es obligatorio.")
            return render(request, "administrador/editar_perfil_admin.html", {"usuario": usuario})

        if not re.match(r"^[^@]+@[^@]+\.[^@]+$", correo):
            messages.error(request, "El formato del correo no es válido.")
            return render(request, "administrador/editar_perfil_admin.html", {"usuario": usuario})

        # Validar correo no repetido (excepto el mismo usuario)
        if Usuario.objects.exclude(id=usuario.id).filter(correo=correo).exists():
            messages.error(request, "Ya existe un usuario con ese correo.")
            return render(request, "administrador/editar_perfil_admin.html", {"usuario": usuario})

        # -----------------------------
        # Teléfono obligatorio + validación
        # -----------------------------
        if not telefono:
            messages.error(request, "El teléfono es obligatorio.")
            return render(request, "administrador/editar_perfil_admin.html", {"usuario": usuario})

        if not telefono.isdigit():
            messages.error(request, "El teléfono solo debe contener números.")
            return render(request, "administrador/editar_perfil_admin.html", {"usuario": usuario})

        if len(telefono) != 10:
            messages.error(request, "El teléfono debe tener 10 dígitos.")
            return render(request, "administrador/editar_perfil_admin.html", {"usuario": usuario})

        # -----------------------------
        # Dirección obligatoria
        # -----------------------------
        if not direccion:
            messages.error(request, "La dirección es obligatoria.")
            return render(request, "administrador/editar_perfil_admin.html", {"usuario": usuario})

        # -----------------------------
        # Contraseñas (opcionales)
        # -----------------------------
        if password or password2:
            if len(password) < 6:
                messages.error(request, "La contraseña debe tener mínimo 6 caracteres.")
                return render(request, "administrador/editar_perfil_admin.html", {"usuario": usuario})

            if password != password2:
                messages.error(request, "Las contraseñas no coinciden.")
                return render(request, "administrador/editar_perfil_admin.html", {"usuario": usuario})

            usuario.password = make_password(password)

        # -----------------------------
        # Guardar cambios
        # -----------------------------
        usuario.nombre = nombre
        usuario.apellido = apellido
        usuario.correo = correo
        usuario.username = correo
        usuario.telefono = telefono
        usuario.direccion = direccion
        usuario.save()

        messages.success(request, "Perfil actualizado correctamente.")
        return redirect("perfil_admin")

    return render(request, "administrador/editar_perfil_admin.html", {"usuario": usuario})

# ----------------------------
# Admin-Gestion de trabajadores
# ----------------------------
@login_required(login_url='login')
@rol_requerido('admin')
def listar_trabajadores(request):
    # Filtrar todos los usuarios que no sean clientes ni admin
    trabajadores = Usuario.objects.exclude(rol__in=['cliente', 'admin'])
    return render(request, 'administrador/trabajadores/trabajadores.html', {'trabajadores': trabajadores})

@login_required(login_url='login')
@rol_requerido('admin')
def crear_trabajador(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        apellido = request.POST.get('apellido', '').strip()
        correo = request.POST.get('correo', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        direccion = request.POST.get('direccion', '').strip()
        rol = request.POST.get('rol', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')

        # ========== VALIDACIONES BACKEND ==========

        # Campos obligatorios
        if not all([nombre, apellido, correo, telefono, direccion, rol, password, password2]):
            messages.error(request, "Todos los campos son obligatorios.")
            return render(request, 'administrador/trabajadores/crear_trabajador.html')

        # Validar solo letras
        solo_letras = r'^[a-zA-ZÁÉÍÓÚáéíóúÑñ\s]+$'
        if not re.match(solo_letras, nombre):
            messages.error(request, "El nombre solo debe contener letras.")
            return render(request, 'administrador/trabajadores/crear_trabajador.html')

        if not re.match(solo_letras, apellido):
            messages.error(request, "El apellido solo debe contener letras.")
            return render(request, 'administrador/trabajadores/crear_trabajador.html')

        # Validar email
        try:
            validate_email(correo)
        except ValidationError:
            messages.error(request, "Ingrese un correo electrónico válido.")
            return render(request, 'administrador/trabajadores/crear_trabajador.html')

        # Validar correo duplicado
        if Usuario.objects.filter(correo=correo).exists():
            messages.error(request, "Ya existe un usuario con este correo.")
            return render(request, 'administrador/trabajadores/crear_trabajador.html')

        # Validar teléfono (solo números, 10 dígitos)
        if not telefono.isdigit() or len(telefono) != 10:
            messages.error(request, "El teléfono debe tener exactamente 10 números.")
            return render(request, 'administrador/trabajadores/crear_trabajador.html')

        # Validar contraseñas
        if len(password) < 6:
            messages.error(request, "La contraseña debe tener al menos 6 caracteres.")
            return render(request, 'administrador/trabajadores/crear_trabajador.html')

        if password != password2:
            messages.error(request, "Las contraseñas no coinciden.")
            return render(request, 'administrador/trabajadores/crear_trabajador.html')
        
        trabajador = Usuario(
            nombre=nombre,
            apellido=apellido,
            correo=correo,
            username=correo,
            telefono=telefono,
            direccion=direccion,
            rol=rol
        )
        trabajador.set_password(password)
        trabajador.save()

        messages.success(request, f"Trabajador {nombre} {apellido} creado con éxito.")
        return redirect('listar_trabajadores')

    return render(request, 'administrador/trabajadores/crear_trabajador.html')

@login_required(login_url='login')
@rol_requerido('admin')
def editar_trabajador(request, trabajador_id):
    trabajador = get_object_or_404(Usuario, id=trabajador_id)

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        apellido = request.POST.get('apellido', '').strip()
        correo = request.POST.get('correo', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        direccion = request.POST.get('direccion', '').strip()
        rol = request.POST.get('rol', '').strip()

        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')

        # ========== VALIDACIONES BACKEND ==========

        # Validar solo letras
        solo_letras = r'^[a-zA-ZÁÉÍÓÚáéíóúÑñ\s]+$'
        if not re.match(solo_letras, nombre):
            messages.error(request, "El nombre solo debe contener letras.")
            return render(request, 'administrador/trabajadores/editar_trabajador.html', {'trabajador': trabajador})

        if not re.match(solo_letras, apellido):
            messages.error(request, "El apellido solo debe contener letras.")
            return render(request, 'administrador/trabajadores/editar_trabajador.html', {'trabajador': trabajador})

        # Validar email
        try:
            validate_email(correo)
        except ValidationError:
            messages.error(request, "Ingrese un correo electrónico válido.")
            return render(request, 'administrador/trabajadores/editar_trabajador.html', {'trabajador': trabajador})

        # Validar que el correo no exista en otro usuario
        if Usuario.objects.exclude(id=trabajador.id).filter(correo=correo).exists():
            messages.error(request, "Ya existe un usuario con este correo.")
            return render(request, 'administrador/trabajadores/editar_trabajador.html', {'trabajador': trabajador})

        # Validar teléfono
        if not telefono.isdigit() or len(telefono) != 10:
            messages.error(request, "El teléfono debe tener exactamente 10 números.")
            return render(request, 'administrador/trabajadores/editar_trabajador.html', {'trabajador': trabajador})

        # Validar contraseñas si se ingresan
        if password or password2:
            if password != password2:
                messages.error(request, "Las contraseñas no coinciden.")
                return render(request, 'administrador/trabajadores/editar_trabajador.html', {'trabajador': trabajador})

            if len(password) < 6:
                messages.error(request, "La contraseña debe tener al menos 6 caracteres.")
                return render(request, 'administrador/trabajadores/editar_trabajador.html', {'trabajador': trabajador})

            trabajador.set_password(password)

        # ========== GUARDAR CAMBIOS ==========
        trabajador.nombre = nombre
        trabajador.apellido = apellido
        trabajador.correo = correo
        trabajador.telefono = telefono
        trabajador.direccion = direccion
        trabajador.rol = rol
        trabajador.save()

        messages.success(request, f"Trabajador {trabajador.nombre} actualizado con éxito.")
        return redirect('listar_trabajadores')

    return render(request, 'administrador/trabajadores/editar_trabajador.html', {'trabajador': trabajador})

@login_required(login_url='login')
@rol_requerido('admin')
def eliminar_trabajador(request, trabajador_id):
    """
    Si el trabajador nunca ha interactuado en el sistema, se elimina.
    Si ya tiene interacciones (pedidos, mensajes, notificaciones),
    solo se desactiva (is_active = False).
    """
    if request.method == 'POST':
        trabajador = get_object_or_404(Usuario, id=trabajador_id)
        nombre_trabajador = f"{trabajador.nombre} {trabajador.apellido}"

        # Solo aplicar a roles de trabajador
        if trabajador.rol not in ['mesero', 'cocinero', 'cajero']:
            messages.error(request, "No se puede eliminar este usuario.")
            return redirect('listar_trabajadores')

        # Usamos la propiedad del modelo
        tiene_interacciones = trabajador.tiene_interacciones

        if tiene_interacciones:
            # NO se elimina, solo se desactiva
            if trabajador.is_active:
                trabajador.is_active = False
                trabajador.save()
                messages.warning(
                    request,
                    f"El trabajador {nombre_trabajador} tiene registros asociados, "
                    "por lo que no se eliminó. Se desactivó su cuenta."
                )
            else:
                messages.info(
                    request,
                    f"El trabajador {nombre_trabajador} ya estaba desactivado."
                )
        else:
            # Sin interacciones → se puede eliminar físicamente
            trabajador.delete()
            messages.success(
                request,
                f"Trabajador {nombre_trabajador} eliminado correctamente."
            )

    return redirect('listar_trabajadores')

# ----------------------------
# Admin - Gestión de Mesas
# ----------------------------
# Listar mesas
@login_required(login_url='login')
@rol_requerido('admin')
def listar_mesas(request):
    mesas = Mesa.objects.all().order_by('numero')
    return render(request, 'administrador/mesas/listar_mesas.html', {'mesas': mesas})

#crear una mesa
@login_required(login_url='login')
@rol_requerido('admin')
def registrar_mesa(request):
    # Obtener el último número de mesa
    ultima_mesa = Mesa.objects.order_by('-numero').first()
    siguiente_numero = ultima_mesa.numero + 1 if ultima_mesa else 1

    if request.method == 'POST':
        numero = request.POST.get('numero')
        capacidad = request.POST.get('capacidad')

        # Validar campos vacíos
        if not numero or not capacidad:
            messages.error(request, "Todos los campos son obligatorios.")
            return render(request, 'administrador/mesas/registrar_mesa.html', {
                'siguiente_numero': siguiente_numero
            })

        # Validar que sean números enteros
        if not numero.isdigit() or not capacidad.isdigit():
            messages.error(request, "El número y la capacidad deben ser valores numéricos.")
            return render(request, 'administrador/mesas/registrar_mesa.html', {
                'siguiente_numero': siguiente_numero
            })

        # Convertir a int para validaciones
        numero = int(numero)
        capacidad = int(capacidad)

        # Validar que sean positivos
        if numero < 1 or capacidad < 1:
            messages.error(request, "Número y capacidad deben ser mayores o iguales a 1.")
            return render(request, 'administrador/mesas/registrar_mesa.html', {
                'siguiente_numero': siguiente_numero
            })

        # Validar número único
        if Mesa.objects.filter(numero=numero).exists():
            messages.error(request, "Ya existe una mesa con ese número.")
            return render(request, 'administrador/mesas/registrar_mesa.html', {
                'siguiente_numero': siguiente_numero
            })

        # Crear mesa
        Mesa.objects.create(
            numero=numero,
            capacidad=capacidad,
        )
        messages.success(request, f"Mesa {numero} registrada correctamente.")
        return redirect('listar_mesas')

    return render(request, 'administrador/mesas/registrar_mesa.html', {
        'siguiente_numero': siguiente_numero
    })

# Editar mesa
@login_required(login_url='login')
@rol_requerido('admin')
def editar_mesa(request, mesa_id):
    mesa = get_object_or_404(Mesa, id=mesa_id)

    if request.method == 'POST':
        numero = request.POST.get('numero')
        capacidad = request.POST.get('capacidad')

        # Evitar que alteren el número
        if str(mesa.numero) != str(numero):
            messages.error(request, "No es posible modificar el número de mesa.")
            return render(request, 'administrador/mesas/editar_mesa.html', {
                'mesa': mesa
            })

        # Validar campos vacíos
        if not capacidad:
            messages.error(request, "La capacidad es obligatoria.")
            return render(request, 'administrador/mesas/editar_mesa.html', {
                'mesa': mesa
            })

        # Validar numérico
        if not capacidad.isdigit():
            messages.error(request, "La capacidad debe ser un número válido.")
            return render(request, 'administrador/mesas/editar_mesa.html', {
                'mesa': mesa
            })

        capacidad = int(capacidad)

        # Validar mínimo
        if capacidad < 1:
            messages.error(request, "La capacidad debe ser mínimo 1.")
            return render(request, 'administrador/mesas/editar_mesa.html', {
                'mesa': mesa
            })

        mesa.capacidad = capacidad
        mesa.save()

        messages.success(request, f"Mesa {mesa.numero} actualizada correctamente.")
        return redirect('listar_mesas')

    return render(request, 'administrador/mesas/editar_mesa.html', {
        'mesa': mesa
    })

# Eliminar mesa
@login_required(login_url='login')
@rol_requerido('admin')
def eliminar_mesa(request, mesa_id):
    mesa = get_object_or_404(Mesa, id=mesa_id)

    if request.method == 'POST':
        # ====== VALIDAR SI LA MESA ESTÁ OCUPADA ======
        # pedidos que aún no han terminado
        pedidos_activos = Pedido.objects.filter(
            mesa=mesa
        ).exclude(
            estado__in=['finalizado', 'cancelado']  # <-- ajusta a tus estados reales
        ).exists()

        if pedidos_activos:
            messages.error(
                request,
                f"No puedes eliminar la mesa {mesa.numero} porque tiene pedidos activos (mesa ocupada)."
            )
            return redirect('listar_mesas')

        # Si no tiene pedidos activos, se puede eliminar
        numero = mesa.numero
        mesa.delete()
        messages.success(request, f"Mesa {numero} eliminada correctamente.")
        return redirect('listar_mesas')

    # Confirmación opcional
    return render(request, 'administrador/mesas/confirmar_eliminar.html', {'mesa': mesa})

# ----------------------------
# Admin - Gestión de Menú / Productos
# ----------------------------
# Listar productos
@login_required(login_url='login')
@rol_requerido('admin')
def listar_menu(request):
    productos = Producto.objects.all().order_by('nombre')
    tipo = request.GET.get("tipo")
    if tipo:
        productos = productos.filter(tipo=tipo)
    return render(request, 'administrador/menu/listar_menu.html', {'productos': productos})

# Registrar producto
@login_required(login_url='login')
@rol_requerido('admin')
def registrar_menu(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        precio = request.POST.get('precio', '').strip()
        tipo = request.POST.get('tipo', '').strip()

        # 1. VALIDAR CAMPOS VACÍOS PRIMERO
        if not nombre or not precio or not tipo:
            messages.error(request, "Todos los campos son obligatorios.")
            return render(request, 'administrador/menu/registrar_menu.html', {
                'nombre': nombre,
                'descripcion': descripcion,
                'precio': precio,
                'tipo': tipo,
            })

        # 2. VALIDAR SOLO LETRAS
        if not re.match(r'^[A-Za-zÁÉÍÓÚáéíóúÑñ ]+$', nombre):
            messages.error(request, "El nombre solo debe contener letras.")
            return render(request, 'administrador/menu/registrar_menu.html', {
                'nombre': nombre,
                'descripcion': descripcion,
                'precio': precio,
                'tipo': tipo,
            })

        # 3. VALIDAR PRECIO
        try:
            precio = float(precio)
            if precio <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, "El precio debe ser un número válido mayor a 0.")
            return render(request, 'administrador/menu/registrar_menu.html', {
                'nombre': nombre,
                'descripcion': descripcion,
                'precio': precio,
                'tipo': tipo,
            })

        # 4. VALIDAR NOMBRE DUPLICADO
        if Producto.objects.filter(nombre__iexact=nombre).exists():
            messages.error(request, "Ya existe un producto con ese nombre.")
            return render(request, 'administrador/menu/registrar_menu.html', {
                'descripcion': descripcion,
                'precio': precio,
                'tipo': tipo,
            })

        # 5. CREAR PRODUCTO
        Producto.objects.create(
            nombre=nombre,
            descripcion=descripcion,
            precio=precio,
            tipo=tipo,
        )

        messages.success(request, f"Producto {nombre} registrado correctamente.")
        return redirect('listar_menu')

    return render(request, 'administrador/menu/registrar_menu.html')

# Editar producto
@login_required(login_url='login')
@rol_requerido('admin')
def editar_menu(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        precio = request.POST.get('precio', '').strip()
        tipo = request.POST.get('tipo', '').strip()

        # -------- VALIDACIONES BACKEND --------

        # Validar campos obligatorios
        if not nombre or not precio or not tipo:
            messages.error(request, "Todos los campos obligatorios deben completarse.")
            return render(request, 'administrador/menu/editar_menu.html', {
                'producto': producto,
                'nombre': nombre,
                'descripcion': descripcion,
                'precio': precio,
                'tipo': tipo,
            })

        # Validar que el nombre contenga solo letras
        if not re.match(r'^[A-Za-zÁÉÍÓÚáéíóúÑñ ]+$', nombre):
            messages.error(request, "El nombre solo debe contener letras.")
            return render(request, 'administrador/menu/editar_menu.html', {
                'producto': producto,
                'nombre': nombre,
                'descripcion': descripcion,
                'precio': precio,
                'tipo': tipo,
            })

        # Validar precio numérico > 0
        try:
            precio_float = float(precio)
            if precio_float <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, "El precio debe ser un número válido mayor a 0.")
            return render(request, 'administrador/menu/editar_menu.html', {
                'producto': producto,
                'nombre': nombre,
                'descripcion': descripcion,
                'precio': precio,
                'tipo': tipo,
            })

        # Validar nombre repetido excepto el item actual
        if Producto.objects.exclude(id=producto.id).filter(nombre__iexact=nombre).exists():
            messages.error(request, "Ya existe otro producto con ese nombre.")
            return render(request, 'administrador/menu/editar_menu.html', {
                'producto': producto,
                'nombre': nombre,
                'descripcion': descripcion,
                'precio': precio,
                'tipo': tipo,
            })

        producto.nombre = nombre
        producto.descripcion = descripcion
        producto.precio = precio
        producto.tipo = tipo
        producto.save()

        messages.success(request, f"Producto {nombre} actualizado correctamente.")
        return redirect('listar_menu')

    return render(request, 'administrador/menu/editar_menu.html', {'producto': producto})

# Eliminar producto
@login_required(login_url='login')
@rol_requerido('admin')
def eliminar_menu(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)

    # Solo debería llegar por POST desde el formulario con SweetAlert
    if request.method != 'POST':
        return redirect('listar_menu')

    # Verificar si el producto tiene detalles de pedido asociados
    tiene_pedidos = producto.tiene_pedidos

    if tiene_pedidos:
        # No eliminar, solo desactivar
        if producto.activo:
            producto.activo = False
            producto.save()
            messages.warning(
                request,
                f"El producto {producto.nombre} tiene pedidos asociados, "
                "por lo que no se eliminó. Se desactivó del menú."
            )
        else:
            messages.info(
                request,
                f"El producto {producto.nombre} ya estaba desactivado."
            )
    else:
        nombre = producto.nombre
        producto.delete()
        messages.success(
            request,
            f"Producto '{nombre}' eliminado correctamente."
        )

    return redirect('listar_menu')

# ----------------------------
# Mesero-Pedidos
# ----------------------------
@login_required(login_url='login')
@rol_requerido('mesero')
def api_estados_pedidos(request):
    pedidos = Pedido.objects.filter(
        tipo_pedido='restaurante',
        mesero=request.user
    ).values(
        'id',
        'estado',
        'mesa_id',
        'mesa__estado'
    )
    return JsonResponse(list(pedidos), safe=False)

# Listar pedidos
@login_required(login_url='login')
@rol_requerido('mesero')
def listar_pedidos(request):

    hoy = timezone.localdate()  # Fecha del sistema
    pedidos = Pedido.objects.filter(
        tipo_pedido='restaurante',
        mesero=request.user,
        fecha_hora__date=hoy      
    ).order_by('-id')

    return render(request, 'mesero/pedidos/listar_pedidos.html', {
        'pedidos': pedidos
    })

# Crear pedido
@login_required(login_url='login')
@rol_requerido('mesero')
def crear_pedido(request):
    if request.method == 'POST':
        mesero_id = request.user.id
        mesa_id = request.POST.get('mesa')

        if not mesa_id:
            messages.error(request, "Debe seleccionar una mesa.")
            return redirect('crear_pedido')

        # Crear el pedido
        pedido = Pedido.objects.create(
            mesero_id=mesero_id,
            mesa_id=mesa_id,
            tipo_pedido="restaurante",
            estado="en_creacion"
        )

        #CAMBIAR MESA A OCUPADA
        mesa = Mesa.objects.get(id=mesa_id)
        mesa.estado = "ocupada"
        mesa.save()

        return redirect('agregar_detalles', pedido_id=pedido.id)

    #SOLO MOSTRAR MESAS LIBRES
    mesas = Mesa.objects.filter(estado="libre")

    return render(request, 'mesero/pedidos/crear_pedido.html', {
        'mesas': mesas,
        'user': request.user
    })

# Ver pedido
@login_required(login_url='login')
@rol_requerido('mesero')
def ver_pedido(request, pedido_id):
    pedido = get_object_or_404(
        Pedido,
        id=pedido_id,
        mesero=request.user,
        tipo_pedido='restaurante'
    )

    # Validación: no permitir ver pedido sin productos
    if not pedido.detalles.exists():
        messages.error(request, "Debe agregar al menos un producto antes de finalizar.")
        return redirect('agregar_detalles', pedido_id=pedido.id)

    # SOLO la primera vez (cuando aún es en_creacion) se manda a cocina
    if pedido.estado == 'en_creacion':
        pedido.estado = 'en preparacion'
        pedido.save()
        enviar_pedido_cocina(pedido)

    # IMPORTANTE: NO mandar actualizar aquí
    # (porque "Ver" se abre muchas veces y eso genera duplicados)

    return render(request, 'mesero/pedidos/ver_pedido.html', {'pedido': pedido})


# Editar pedido
@login_required(login_url='login')
@rol_requerido('mesero')
def editar_pedido(request, pedido_id):

    pedido = get_object_or_404(Pedido, id=pedido_id)

    if request.method == 'POST':

        nueva_mesa_id = request.POST.get('mesa')
        mesa_anterior_id = pedido.mesa_id

        # ---------------------------------------------
        # 1. CAMBIO DE MESA → Liberar anterior y ocupar nueva
        # ---------------------------------------------
        if str(mesa_anterior_id) != str(nueva_mesa_id):

            # Liberar mesa anterior
            if mesa_anterior_id:
                mesa_old = Mesa.objects.get(id=mesa_anterior_id)
                mesa_old.estado = "libre"
                mesa_old.save()

            # Ocupar nueva mesa
            mesa_new = Mesa.objects.get(id=nueva_mesa_id)
            mesa_new.estado = "ocupada"
            mesa_new.save()

            pedido.mesa_id = nueva_mesa_id

        # ---------------------------------------------
        # 2. Estado siempre vuelve a en preparación
        # ---------------------------------------------
        pedido.estado = "en preparacion"
        pedido.save()

        # ---------------------------------------------
        # 3. ENVIAR ACTUALIZACIÓN A COCINA
        # ---------------------------------------------
        enviar_actualizacion_cocina(pedido)

        return JsonResponse({
            "success": True,
            "mensaje": f"Pedido #{pedido.id} actualizado correctamente.",
            "pedido_id": pedido.id
        })

    # SOLO MESAS LIBRES + LA MESA ACTUAL
    mesas = Mesa.objects.filter(estado="libre") | Mesa.objects.filter(id=pedido.mesa_id)
    productos = Producto.objects.filter(activo=True)


    return render(request, 'mesero/pedidos/editar_pedido.html', {
        'pedido': pedido,
        'mesas': mesas,
        'productos': productos
    })

def enviar_actualizacion_cocina(pedido):
    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        "pedidos_activos",
        {
            "type": "actualizar_pedido",
            "pedido": {
                "id": pedido.id,
                # Mantener título igual al original
                "mesa": pedido.mesa.numero if pedido.mesa else "Domicilio",

                # Mostrar correctamente quién atendió
                "mesero": pedido.mesero.nombre if pedido.tipo_pedido == 'restaurante' else f"Cajero: {pedido.cajero.nombre}",

                # Productos del pedido
                "productos": [
                    {
                        "nombre": d.producto.nombre,
                        "cantidad": d.cantidad,
                        "observacion": d.observacion,
                    }
                    for d in pedido.detalles.all()
                ],

                # MUY IMPORTANTE: indicar tipo de pedido
                "tipo": pedido.tipo_pedido
            }
        }
    )

# Eliminar pedido
@login_required(login_url='login')
@rol_requerido('mesero')
def eliminar_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)

    if pedido.estado != 'en preparacion':
        return JsonResponse({"success": False, "message": "No se puede eliminar un pedido listo o finalizado."})

    if request.method == 'POST':

        #LIBERAR LA MESA
        if pedido.mesa:
            pedido.mesa.estado = "libre"
            pedido.mesa.save()

        #ELIMINAR PEDIDO
        pedido_id = pedido.id
        pedido.delete()

        #ENVIAR A COCINA QUE SE ELIMINÓ
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "pedidos_activos",
            {
                "type": "eliminar_pedido",
                "pedido_id": pedido_id
            }
        )

        return JsonResponse({"success": True})

    return JsonResponse({"success": False})

#finalizar un pedido
@login_required(login_url='login')
@rol_requerido('mesero')
def finalizar_pedido(request, pedido_id):

    if request.method != 'POST':
        return JsonResponse({"success": False, "message": "Método no permitido."})

    pedido = get_object_or_404(Pedido, id=pedido_id)

    # CAMBIAR ESTADO DEL PEDIDO
    pedido.estado = "finalizado"
    pedido.save()

    # LIBERAR MESA
    if pedido.mesa:
        pedido.mesa.estado = "libre"
        pedido.mesa.save()

    return JsonResponse({
        "success": True,
        "message": f"El pedido #{pedido.id} ha sido finalizado y la mesa está libre."
    })

# ----------------------------
# Detalles con AJAX
# ----------------------------
# Agregar detalles con AJAX
@login_required(login_url='login')
@rol_requerido('mesero')
def agregar_detalles(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    
    # SOLO productos activos
    productos = Producto.objects.filter(activo=True)

    return render(request, 'mesero/pedidos/agregar_detalles.html', {
        'pedido': pedido,
        'productos': productos
    })

@login_required(login_url='login')
@rol_requerido('mesero')
def agregar_detalle_ajax(request, pedido_id):
    if request.method == 'POST':
        import json
        data = json.loads(request.body)

        producto_id = data.get('producto_id')
        cantidad = int(data.get('cantidad', 1))
        observacion = data.get("observacion", '')

        # 🔹 1) VERIFICAR SI YA EXISTE ESE PRODUCTO EN EL PEDIDO
        if DetallePedido.objects.filter(pedido_id=pedido_id, producto_id=producto_id).exists():
            return JsonResponse({
                'success': False,
                'mensaje': 'Este producto ya fue agregado al pedido. Edítelo en la tabla.'
            })

        # 🔹 2) CREAR DETALLE (SIN RECARGOS)
        detalle = DetallePedido.objects.create(
            pedido_id=pedido_id,
            producto_id=producto_id,
            cantidad=cantidad,
            observacion=observacion
        )

        # 🔹 3) ACTUALIZAR TOTALES
        pedido = get_object_or_404(Pedido, id=pedido_id)
        pedido.calcular_totales()

        # 🔹 4) ORDENAR DETALLES POR ORDEN DE REGISTRO
        detalles = pedido.detalles.order_by('id')

        tabla_html = render_to_string('mesero/pedidos/tabla_detalles.html', {
            'pedido': pedido,
            'detalles': detalles
        })

        return JsonResponse({
            'success': True,
            'mensaje': 'Producto agregado.',
            'tabla': tabla_html
        })

    return JsonResponse({'success': False, 'mensaje': 'Error al agregar producto'})

@login_required(login_url='login')
@rol_requerido('mesero')
def editar_detalle_ajax(request, detalle_id):
    detalle = get_object_or_404(DetallePedido, id=detalle_id)
    pedido = detalle.pedido

    if request.method == 'POST':
        import json
        data = json.loads(request.body)

        detalle.cantidad = int(data.get("cantidad", detalle.cantidad))
        detalle.observacion = data.get("observacion", detalle.observacion)

        detalle.save()

        # 🔹 RECALCULAR TOTALES
        pedido.calcular_totales()

        # 🔹 ORDENAR DETALLES POR ID (ORDEN DE REGISTRO)
        detalles = pedido.detalles.order_by('id')

        tabla_html = render_to_string('mesero/pedidos/tabla_detalles.html', {
            'pedido': pedido,
            'detalles': detalles
        })

        return JsonResponse({
            'success': True,
            'mensaje': 'Detalle actualizado correctamente.',
            'tabla': tabla_html
        })

    return JsonResponse({'success': False, 'mensaje': 'Error al actualizar detalle.'})

@login_required(login_url='login')
@rol_requerido('mesero')
def eliminar_detalle_ajax(request, detalle_id):
    detalle = get_object_or_404(DetallePedido, id=detalle_id)
    pedido = detalle.pedido

    if request.method == 'POST':
        detalle.delete()

        # 🔹 RECALCULAR TOTALES
        pedido.calcular_totales()

        # 🔹 ORDENAR DETALLES POR ID
        detalles = pedido.detalles.order_by('id')

        tabla_html = render_to_string('mesero/pedidos/tabla_detalles.html', {
            'pedido': pedido,
            'detalles': detalles
        })

        return JsonResponse({
            'success': True,
            'mensaje': 'Producto eliminado correctamente.',
            'tabla': tabla_html
        })

    return JsonResponse({'success': False, 'mensaje': 'Error al eliminar producto.'})

# ----------------------------
# Cocinero marca pedido como listo
# ----------------------------

@login_required(login_url='login')
@rol_requerido('cocinero')
def vista_cocina(request):
    hoy = timezone.localdate()

    pedidos_restaurante = Pedido.objects.filter(
        estado='en preparacion',
        tipo_pedido='restaurante',
        fecha_hora__date=hoy
    ).order_by('id')

    pedidos_domicilio = Pedido.objects.filter(
        estado='en preparacion',
        tipo_pedido='domicilio',
        fecha_hora__date=hoy
    ).order_by('id')

    meseros = Usuario.objects.filter(rol='mesero')
    cajeros = Usuario.objects.filter(rol='cajero')

    return render(request, 'cocinero/pedido.html', {
        'pedidos_restaurante': pedidos_restaurante,
        'pedidos_domicilio': pedidos_domicilio, 
        'meseros': meseros,
        'cajeros': cajeros,
    })

@login_required(login_url='login')
@rol_requerido('cocinero')
@csrf_protect
def marcar_pedido_listo(request, pedido_id):
    if request.method == "POST":
        pedido = get_object_or_404(Pedido, id=pedido_id)
        pedido.estado = "listo"
        pedido.save()

        # Destinatario de la notificación (mesero si restaurante, cajero si domicilio)
        destinatario = pedido.mesero if pedido.tipo_pedido == 'restaurante' else pedido.cajero

        # Guardar y obtener la instancia de la notificación
        notif = Notificacion.objects.create(
            usuario_destino=destinatario,
            tipo="pedido_listo",
            mensaje=f"El pedido {pedido.codigo_pedido} está listo.",
            pedido=pedido
        )

        # ==========================================
        # 1) NOTIFICACIÓN NORMAL (mesero / cajero)
        # ==========================================
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"notificaciones_{destinatario.id}",
            {
                "type": "enviar_notificacion",
                "tipo": "pedido_listo",
                "mensaje": f"El pedido {pedido.codigo_pedido} está listo.",
                "mesa": pedido.mesa.numero if pedido.mesa else None,
                "pedido": pedido.id,
                # 👇 NUEVO: mandamos también el código
                "codigo_pedido": pedido.codigo_pedido,
                "id": notif.id,
                "fecha": localtime(notif.fecha_hora).strftime("%d/%m/%Y %H:%M"),
            }
        )

        # ==========================================
        # 2) EVENTO PARA LA TABLA DE COBROS (cajero)
        #    → nuevo_cobro (WebSocket)
        # ==========================================

        # Nombre que se mostrará en "mesa"
        mesa_texto = pedido.mesa.numero if pedido.mesa else "Domicilio"

        # Quien aparece como "mesero" en la tabla de cobro
        if pedido.tipo_pedido == 'restaurante' and pedido.mesero:
            nombre_atendio = pedido.mesero.nombre
        elif pedido.tipo_pedido == 'domicilio' and pedido.cajero:
            nombre_atendio = f"Cajero: {pedido.cajero.nombre}"
        else:
            nombre_atendio = "N/A"

        async_to_sync(channel_layer.group_send)(
            "pedidos_activos",
            {
                "type": "nuevo_cobro",
                "origen": "domicilio" if pedido.tipo_pedido == "domicilio" else "restaurante",
                "pedido_id": pedido.id,
                # también aquí mandamos el código
                "codigo_pedido": pedido.codigo_pedido,
                "mesa": mesa_texto,
                "mesero": nombre_atendio,
                "total": float(pedido.total),
                "estado_pago": "pendiente",
            }
        )

        return JsonResponse({"success": True})


def _payload_pedido_cocina(pedido):
    return {
        "id": pedido.id,
        "codigo_pedido": pedido.codigo_pedido,
        "tipo": pedido.tipo_pedido,
        "mesa": pedido.mesa.numero if pedido.mesa else None,
        "mesero": pedido.mesero.nombre if pedido.mesero else None,
        "cajero": pedido.cajero.nombre if pedido.cajero else None,
        "productos": [
            {
                "nombre": d.producto.nombre,
                "cantidad": d.cantidad,
                "observacion": d.observacion or ""
            }
            for d in pedido.detalles.all()
        ]
    }

def enviar_pedido_cocina(pedido):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "pedidos_activos",
        {
            "type": "nuevo_pedido",
            "pedido": _payload_pedido_cocina(pedido),
        }
    )

def enviar_actualizacion_cocina(pedido):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "pedidos_activos",
        {
            "type": "actualizar_pedido",
            "pedido": _payload_pedido_cocina(pedido),
        }
    )

@login_required(login_url='login')
@rol_requerido('cocinero')
@require_POST
@csrf_protect
def enviar_mensaje_mesero(request):
    data = json.loads(request.body)

    usuario_id = data.get("usuario_id")
    mensaje = (data.get("mensaje") or "").strip()

    if not usuario_id or not mensaje:
        return JsonResponse({"success": False, "mensaje": "Datos incompletos."}, status=400)

    destinatario = get_object_or_404(Usuario, id=usuario_id)

    # ahora request.user SIEMPRE será Usuario (porque login_required)
    msg = Mensaje.objects.create(
        remitente=request.user,
        destinatario=destinatario,
        contenido=mensaje
    )

    notif = Notificacion.objects.create(
        usuario_destino=destinatario,
        tipo="mensaje",
        mensaje=mensaje
    )

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"notificaciones_{destinatario.id}",
        {
            "type": "enviar_notificacion",
            "tipo": "mensaje",
            "mensaje": mensaje,
            "id": notif.id,
            "fecha": notif.fecha_hora.strftime("%d/%m/%Y %H:%M"),
            "pedido": None,
            "mesa": None,
        }
    )

    return JsonResponse({"success": True})

#-------------------------------------
# MESERO - MODULO NOTIFICACIONES
#-------------------------------------

def notificaciones_mesero(request):
    notificaciones = Notificacion.objects.filter(
        usuario_destino=request.user
    ).order_by('-fecha_hora')

    return render(request, "mesero/notificacion/notificaciones.html", {
        "notificaciones": notificaciones
    })

def obtener_notificaciones(request):
    notifs = Notificacion.objects.filter(usuario_destino=request.user).order_by('-fecha_hora')
    return JsonResponse([
        {
            "id": n.id,
            "tipo": n.tipo,
            "mensaje": n.mensaje,
            "pedido": n.pedido_id if n.pedido else None,
            "mesa": n.pedido.mesa.numero if n.pedido and n.pedido.mesa else None,
            "fecha": localtime(n.fecha_hora).strftime("%d/%m/%Y %H:%M"),
        }
        for n in notifs
    ], safe=False)

@csrf_exempt
def eliminar_notificacion(request, notif_id):
    if request.method == "POST":
        notif = get_object_or_404(Notificacion, id=notif_id)
        notif.delete()
        return JsonResponse({"success": True})

    return JsonResponse({"success": False}, status=400)

# ----------------------------
# Cajero - Pedidos a domicilio
# ----------------------------
@login_required(login_url='login')
@rol_requerido('cajero')
def cajero_listar_pedidos(request):

    hoy = timezone.localdate()

    pedidos = Pedido.objects.filter(
        tipo_pedido='domicilio',
        cajero=request.user,
        fecha_hora__date=hoy
    ).exclude(estado__in=['borrador', 'en_creacion']).order_by('-id')

    return render(request, 'cajero/pedidos/listar_pedidos.html', {
        'pedidos': pedidos
    })

@login_required(login_url='login')
@rol_requerido('cajero')
def cajero_crear_pedido(request):
    """
    Crea el pedido a domicilio: SOLO datos del cliente.
    El recargo por producto se pedirá al agregar cada detalle.
    """
    if request.method == 'POST':
        nombre_cliente = request.POST.get('nombre_cliente', '').strip()
        contacto_cliente = request.POST.get('contacto_cliente', '').strip()
        direccion_entrega = request.POST.get('direccion_entrega', '').strip()

        # Validaciones básicas
        if not nombre_cliente or not contacto_cliente or not direccion_entrega:
            messages.error(request, "Todos los datos del cliente son obligatorios.")
            return render(request, 'cajero/pedidos/crear_pedido.html', {
                'user': request.user,
                'nombre_cliente': nombre_cliente,
                'contacto_cliente': contacto_cliente,
                'direccion_entrega': direccion_entrega,
            })

        # Crear pedido a domicilio (sin recargo, se usará recargo por detalle)
        pedido = Pedido.objects.create(
            cajero=request.user,
            tipo_pedido='domicilio',
            estado='borrador',
            nombre_cliente=nombre_cliente,
            contacto_cliente=contacto_cliente,
            direccion_entrega=direccion_entrega,
            # recargo_domicilio = 0 por defecto si existe el campo
        )

        return redirect('cajero_agregar_detalles', pedido_id=pedido.id)

    return render(request, 'cajero/pedidos/crear_pedido.html', {
        'user': request.user
    })

@login_required(login_url='login')
@rol_requerido('cajero')
def cajero_agregar_detalles(request, pedido_id):

    pedido = get_object_or_404(
        Pedido,
        id=pedido_id,
        tipo_pedido='domicilio',
        cajero=request.user,
        estado__in=['borrador', 'en_creacion']
    )
    productos = Producto.objects.filter(activo=True)
    
    # CALCULAR RECARGOS AQUi
    total_recargos = pedido.detalles.aggregate(
        total=Sum(F('recargo') * F('cantidad'))
    )['total'] or 0

    return render(request, 'cajero/pedidos/agregar_detalles.html', {
        'pedido': pedido,
        'productos': productos,
        'total_recargos': total_recargos
    })

@login_required(login_url='login')
@rol_requerido('cajero')
def cajero_agregar_detalle_ajax(request, pedido_id):
    """
    Agrega productos al pedido a domicilio.
    VALIDACIÓN: si el producto ya existe en el pedido, NO se vuelve a agregar.
    """
    if request.method == 'POST':
        import json
        data = json.loads(request.body)

        producto_id = data.get('producto_id')
        cantidad = int(data.get('cantidad', 1))
        observacion = data.get("observacion", '')

        recargo_unitario = float(data.get("recargo_unitario", 0))
        recargo_total = float(data.get("recargo_total", 0))  # (no es necesario guardarlo)

        # VALIDAR DUPLICADO
        if DetallePedido.objects.filter(pedido_id=pedido_id, producto_id=producto_id).exists():
            return JsonResponse({
                'success': False,
                'mensaje': 'Este producto ya fue agregado al pedido. Edítelo en la tabla.'
            })

        # CREAR DETALLE (SIN DUPLICAR)
        DetallePedido.objects.create(
            pedido_id=pedido_id,
            producto_id=producto_id,
            cantidad=cantidad,
            observacion=observacion,
            recargo=recargo_unitario
        )

        pedido = get_object_or_404(Pedido, id=pedido_id)
        pedido.calcular_totales()

        total_recargos = pedido.detalles.aggregate(
            total=Sum(F('recargo') * F('cantidad'))
        )['total'] or 0

        # ORDEN ORIGINAL (por id ascendente)
        detalles = pedido.detalles.order_by('id')

        tabla_html = render_to_string('cajero/pedidos/tabla_detalles_acciones.html', {
            'pedido': pedido,
            'total_recargos': total_recargos,
            'detalles': detalles
        })

        return JsonResponse({
            'success': True,
            'mensaje': 'Producto agregado con recargo.',
            'tabla': tabla_html
        })

    return JsonResponse({'success': False, 'mensaje': 'Método no permitido.'})

@login_required(login_url='login')
@rol_requerido('cajero')
def cajero_editar_detalle_ajax(request, detalle_id):
    detalle = get_object_or_404(DetallePedido, id=detalle_id)
    pedido = detalle.pedido

    if pedido.tipo_pedido != 'domicilio' or pedido.cajero != request.user:
        return JsonResponse({'success': False, 'mensaje': 'No autorizado.'}, status=403)

    if request.method == 'POST':
        import json
        data = json.loads(request.body)

        detalle.cantidad = int(data.get("cantidad", detalle.cantidad))
        detalle.observacion = data.get("observacion", detalle.observacion)
        detalle.recargo = float(data.get("recargo", detalle.recargo))
        detalle.save()

        # recalcular totales del pedido
        pedido.calcular_totales()

        total_recargos = pedido.detalles.aggregate(
            total=Sum(F('recargo') * F('cantidad'))
        )['total'] or 0

        # ORDEN ORIGINAL
        detalles = pedido.detalles.order_by('id')

        tabla_html = render_to_string('cajero/pedidos/tabla_detalles_acciones.html', {
            'pedido': pedido,
            'total_recargos': total_recargos,
            'detalles': detalles
        })

        return JsonResponse({
            'success': True,
            'mensaje': 'Detalle actualizado correctamente.',
            'tabla': tabla_html
        })

    return JsonResponse({'success': False, 'mensaje': 'Método no permitido.'})

@login_required(login_url='login')
@rol_requerido('cajero')
def cajero_eliminar_detalle_ajax(request, detalle_id):
    detalle = get_object_or_404(DetallePedido, id=detalle_id)
    pedido = detalle.pedido

    if pedido.tipo_pedido != 'domicilio' or pedido.cajero != request.user:
        return JsonResponse({'success': False, 'mensaje': 'No autorizado.'}, status=403)

    if request.method == 'POST':
        detalle.delete()

        #  recalcular totales
        pedido.calcular_totales()

        total_recargos = pedido.detalles.aggregate(
            total=Sum(F('recargo') * F('cantidad'))
        )['total'] or 0

        #  ORDEN ORIGINAL
        detalles = pedido.detalles.order_by('id')

        tabla_html = render_to_string('cajero/pedidos/tabla_detalles_acciones.html', {
            'pedido': pedido,
            'total_recargos': total_recargos,
            'detalles': detalles
        })

        return JsonResponse({
            'success': True,
            'mensaje': 'Producto eliminado correctamente.',
            'tabla': tabla_html
        })

    return JsonResponse({'success': False, 'mensaje': 'Método no permitido.'})

@login_required(login_url='login')
@rol_requerido('cajero')
def cajero_ver_pedido(request, pedido_id):

    pedido = get_object_or_404(
        Pedido,
        id=pedido_id,
        tipo_pedido='domicilio',
        cajero=request.user
    )

    if not pedido.detalles.exists():
        messages.error(
            request,
            "No se puede enviar a cocina un pedido sin productos."
        )
        return redirect('cajero_agregar_detalles', pedido_id=pedido.id)

    # Solo la PRIMERA vez lo mando a cocina
    if pedido.estado in ['borrador', 'en_creacion']:
        pedido.estado = 'en preparacion'
        pedido.save()
        enviar_pedido_cocina(pedido)   # solo una vez
    # si ya está en preparación/listo/finalizado, NO lo vuelves a mandar

    return render(request, 'cajero/pedidos/ver_pedido.html', {
        'pedido': pedido
    })

@login_required(login_url='login')
@rol_requerido('cajero')
def cajero_api_estados_pedidos(request):
    pedidos = Pedido.objects.filter(
        tipo_pedido='domicilio',
        cajero=request.user
    ).values(
        'id',
        'estado'
    )
    return JsonResponse(list(pedidos), safe=False)

@login_required(login_url='login')
@rol_requerido('cajero')
def cajero_eliminar_pedido(request, pedido_id):
    pedido = get_object_or_404(
        Pedido,
        id=pedido_id,
        tipo_pedido='domicilio',
        cajero=request.user
    )

    # Solo dejar eliminar si está en preparación
    if pedido.estado != 'en preparacion':
        return JsonResponse({
            "success": False,
            "message": "Solo se puede eliminar un pedido que esté en preparación."
        })

    if request.method == 'POST':
        pedido_id = pedido.id
        pedido.delete()

        # Avisar a cocina que se eliminó (opcional)
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "pedidos_activos",
            {
                "type": "eliminar_pedido",
                "pedido_id": pedido_id
            }
        )

        return JsonResponse({"success": True})

    return JsonResponse({"success": False})

@login_required(login_url='login')
@rol_requerido('cajero')
def cajero_finalizar_pedido(request, pedido_id):

    if request.method != 'POST':
        return JsonResponse({"success": False, "message": "Método no permitido."})

    pedido = get_object_or_404(
        Pedido,
        id=pedido_id,
        tipo_pedido='domicilio',
        cajero=request.user
    )

    # (opcional) solo permitir si ya está "listo"
    if pedido.estado != "listo":
        return JsonResponse({
            "success": False,
            "message": "Solo se puede finalizar un pedido que ya esté listo."
        })

    pedido.estado = "finalizado"
    pedido.save()

    return JsonResponse({
        "success": True,
        "message": f"El pedido #{pedido.id} ha sido finalizado."
    })

@login_required(login_url='login')
@rol_requerido('cajero')
def cajero_editar_pedido(request, pedido_id):

    pedido = get_object_or_404(
        Pedido,
        id=pedido_id,
        tipo_pedido='domicilio',
        cajero=request.user
    )

    # NECESARIOS PARA QUE SE VEAN LOS PRODUCTOS Y DETALLES
    productos = Producto.objects.filter(activo=True)
    detalles = pedido.detalles.all()

    if request.method == "POST":

        nombre_cliente = request.POST.get('nombre_cliente', '').strip()
        contacto_cliente = request.POST.get('contacto_cliente', '').strip()
        direccion_entrega = request.POST.get('direccion_entrega', '').strip()
        recargo_domicilio = request.POST.get('recargo_domicilio', '0').strip()

        # Validaciones
        if not nombre_cliente or not contacto_cliente or not direccion_entrega:
            return JsonResponse({
                "success": False,
                "mensaje": "Todos los campos son obligatorios."
            })

        try:
            recargo_decimal = float(recargo_domicilio)
        except:
            return JsonResponse({
                "success": False,
                "mensaje": "El recargo debe ser un número válido."
            })

        # Guardar cambios
        pedido.nombre_cliente = nombre_cliente
        pedido.contacto_cliente = contacto_cliente
        pedido.direccion_entrega = direccion_entrega
        pedido.recargo_domicilio = recargo_decimal
        pedido.save()
        pedido.calcular_totales()

        enviar_actualizacion_cocina(pedido)


        return JsonResponse({
            "success": True,
            "mensaje": f"Pedido #{pedido.id} actualizado correctamente.",
            "pedido_id": pedido.id
        })

    # SE ENVÍAN LOS PRODUCTOS Y DETALLES AQUÍ
    return render(request, 'cajero/pedidos/editar_pedido.html', {
        'pedido': pedido,
        'productos': productos,    # ← NECESARIO
        'detalles': detalles       # ← NECESARIO
    })

@login_required(login_url='login')
@rol_requerido('cajero')
def cajero_cancelar_pedido(request, pedido_id):

    pedido = get_object_or_404(
        Pedido,
        id=pedido_id,
        tipo_pedido='domicilio',
        cajero=request.user,
        estado='borrador'
    )

    pedido.delete()

    messages.info(request, "Pedido cancelado correctamente.")
    return redirect('cajero_listar_pedidos')

@login_required(login_url='login')
@rol_requerido('cajero')
def cajero_notificaciones(request):
    notificaciones = Notificacion.objects.filter(
        usuario_destino=request.user
    ).order_by('-fecha_hora')

    return render(request, "cajero/notificaciones/listar.html", {
        "notificaciones": notificaciones
    })

@login_required(login_url='login')
@rol_requerido('cajero')
def cajero_restaurante_cobros(request):

    pagos_confirmados = Pago.objects.filter(
        pedido=OuterRef('pk'),
        estado_pago='confirmado'
    )

    hoy = timezone.localdate()

    # ---------- PEDIDOS PENDIENTES DE COBRO (SOLO HOY) ----------
    pedidos_cobrar = (
        Pedido.objects
        .filter(
            tipo_pedido='restaurante',
            estado__in=['listo', 'finalizado'],
            fecha_hora__date=hoy
        )
        .annotate(tiene_pago=Exists(pagos_confirmados))
        .filter(tiene_pago=False)
        .order_by('-id')
    )

    # ---------- PEDIDOS PAGADOS (SOLO HOY) + COMPROBANTES ----------
    pedidos_pagados = (
        Pedido.objects
        .filter(
            tipo_pedido='restaurante',
            pagos__estado_pago='confirmado',
            pagos__fecha_hora__date=hoy
        )
        .prefetch_related('pagos__comprobante_set')  # para acceder a los PDFs
        .distinct()
        .order_by('-id')
    )

    # añadir el último pago confirmado a cada pedido (igual que domicilio)
    for p in pedidos_pagados:
        p.pago_confirmado = (
            p.pagos
             .filter(estado_pago='confirmado')
             .order_by('-id')
             .first()
        )

    return render(request, "cajero/pago/cobros_restaurante.html", {
        "pedidos_cobrar": pedidos_cobrar,
        "pedidos_pagados": pedidos_pagados
    })

# ============================================================
#                    REGISTRAR PAGO DEL PEDIDO
# ============================================================
@login_required(login_url='login')
@rol_requerido('cajero')
def cajero_restaurante_pagar(request, pedido_id):

    if request.method != "POST":
        return JsonResponse({"success": False})

    pedido = get_object_or_404(Pedido, id=pedido_id)

    data = json.loads(request.body)
    metodo = data.get("metodo")
    recibido_raw = data.get("recibido", "")
    referencia = data.get("referencia", "")

    # Solo permitir cobrar pedidos listos o finalizados
    if pedido.estado not in ['listo', 'finalizado']:
        return JsonResponse({"success": False, "message": "El pedido no puede ser pagado."})

    # Convertir valores en Decimal (sin errores de float)
    try:
        total = Decimal(str(pedido.total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if recibido_raw not in ["", None]:
            recibido = Decimal(str(recibido_raw)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            recibido = None

    except:
        return JsonResponse({"success": False, "message": "El monto ingresado no es válido."})

    # =====================================================
    #                VALIDACIONES SEGÚN MÉTODO
    # =====================================================

    # TRANSFERENCIA
    if metodo == "transferencia":

        if recibido is None:
            return JsonResponse({"success": False, "message": "Debe ingresar el monto de la transferencia."})

        if recibido != total:
            return JsonResponse({"success": False, "message": "El monto debe ser EXACTO para transferencias."})

        if not referencia:
            return JsonResponse({"success": False, "message": "Debe ingresar el número de comprobante."})

        cambio = Decimal("0.00")

    # EFECTIVO
    elif metodo == "efectivo":

        if recibido is None:
            return JsonResponse({"success": False, "message": "Debe ingresar el monto recibido."})

        if recibido < total:
            return JsonResponse({"success": False, "message": "El cliente no puede pagar menos del total."})

        cambio = recibido - total

    else:
        return JsonResponse({"success": False, "message": "Método de pago no válido."})

    # =====================================================
    #                 REGISTRAR EL PAGO
    # =====================================================
    pago = Pago.objects.create(
        pedido=pedido,
        total=total,
        monto_recibido=recibido,
        metodo_pago=metodo,
        referencia_transferencia=referencia if metodo == "transferencia" else "",
        cambio=cambio,
        estado_pago="confirmado"
    )

    # =====================================================
    #     CREAR COMPROBANTE AUTOMÁTICAMENTE
    # =====================================================
    numero = f"C-{pedido.id}-{pago.id}"

    comprobante = Comprobante.objects.create(
        pago=pago,
        numero_comprobante=numero,
        nombre_cliente="Consumidor final",
        direccion_cliente=pedido.direccion_entrega if pedido.direccion_entrega else "N/A",
        correo_cliente=None
    )

    generar_comprobante_pdf(comprobante)

    # URL segura del PDF
    comprobante_url = comprobante.archivo_pdf.url if comprobante.archivo_pdf else ""

    # =====================================================
    #               WEBSOCKET: ACTUALIZAR TABLAS
    # =====================================================
    channel_layer = get_channel_layer()

    # eliminar de pendientes
    async_to_sync(channel_layer.group_send)(
        "pedidos_activos",
        {
            "type": "eliminar_pedido",
            "pedido_id": pedido.id
        }
    )

    # agregar a pagados (con fecha en zona local)
    fecha_local = timezone.localtime(pago.fecha_hora).strftime("%d/%m/%Y %H:%M")

    async_to_sync(channel_layer.group_send)(
        "pedidos_activos",
        {
            "type": "nuevo_pagado",
            "origen": "restaurante",                      # IMPORTANTE
            "pedido_id": pedido.id,
            "codigo_pedido": pedido.codigo_pedido,        # para mostrar el código en tiempo real
            "mesa": pedido.mesa.numero if pedido.mesa else "Domicilio",
            "mesero": pedido.mesero.nombre if pedido.mesero else "",
            "total": float(total),
            "fecha": fecha_local,
            "estado_pago": "confirmado",
            "comprobante_url": comprobante_url,           # para el botón "Ver PDF"
        }
    )

    # =====================================================
    # RESPUESTA CON LINK PARA IMPRIMIR
    # =====================================================
    return JsonResponse({
        "success": True,
        "message": "Pago registrado correctamente.",
        "comprobante_url": comprobante_url,
        "codigo_pedido": pedido.codigo_pedido           # opcional pero útil en el JS del front
    })

@login_required(login_url='login')
@rol_requerido('cajero')
def cajero_domicilio_cobros(request):

    pagos_confirmados = Pago.objects.filter(
        pedido=OuterRef('pk'),
        estado_pago='confirmado'
    )

    # FECHA DE HOY
    hoy = timezone.localdate()

    # PEDIDOS PENDIENTES DE COBRO
    pedidos_cobrar = Pedido.objects.filter(
        tipo_pedido='domicilio',
        estado__in=['listo', 'finalizado'],
        cajero=request.user,
        fecha_hora__date=hoy  
    ).annotate(
        tiene_pago=Exists(pagos_confirmados)
    ).filter(tiene_pago=False).order_by('-id')

    # AQUÍ ESTABA EL PROBLEMA:
    # antes solo hacías un filter simple.
    # Usa la MISMA lógica que en tabla_pedidos_pagados_domicilio:

    pedidos_pagados = (
        Pedido.objects
        .filter(
            tipo_pedido='domicilio',
            cajero=request.user,
            pagos__estado_pago='confirmado',
            pagos__fecha_hora__date=hoy 
        )
        .prefetch_related('pagos__comprobante_set')  # para acceder a los comprobantes sin más queries
        .distinct()
        .order_by('-id')
    )

    # añadir el último pago confirmado a cada pedido
    for p in pedidos_pagados:
        p.pago_confirmado = (
            p.pagos
            .filter(estado_pago='confirmado')
            .order_by('-id')
            .first()
        )

    return render(request, "cajero/pago/cobros_domicilio.html", {
        "pedidos_cobrar": pedidos_cobrar,
        "pedidos_pagados": pedidos_pagados
    })

@login_required(login_url='login')
@rol_requerido('cajero')
def cajero_domicilio_pagar(request, pedido_id):

    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Método no permitido."})

    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"success": False, "message": "Datos inválidos."})

    metodo = data.get("metodo")
    recibido = data.get("recibido")
    referencia = data.get("referencia", "")

    try:
        pedido = Pedido.objects.get(id=pedido_id, tipo_pedido="domicilio")
    except Pedido.DoesNotExist:
        return JsonResponse({"success": False, "message": "Pedido no encontrado."})

    total = float(pedido.total)

    # ================================
    # VALIDACIÓN DE MÉTODO DE PAGO
    # ================================
    if metodo not in ["efectivo", "transferencia"]:
        return JsonResponse({"success": False, "message": "Método de pago inválido."})

    if metodo == "efectivo":
        try:
            recibido = float(recibido)
        except:
            return JsonResponse({"success": False, "message": "Monto recibido inválido."})

        if recibido < total:
            return JsonResponse({"success": False, "message": "El monto recibido es insuficiente."})

    if metodo == "transferencia":
        if not referencia:
            return JsonResponse({"success": False, "message": "Debe ingresar número de comprobante."})

        try:
            recibido = float(recibido)
        except:
            return JsonResponse({"success": False, "message": "Monto transferido inválido."})

        if recibido < total:
            return JsonResponse({"success": False, "message": "El monto transferido es insuficiente."})

    fecha_local = timezone.localtime(timezone.now())

    # ================================
    # REGISTRO DEL PAGO (CORREGIDO)
    # ================================
    with transaction.atomic():
        pago = Pago.objects.create(
            pedido=pedido,
            total=total,                    
            metodo_pago=metodo,             
            monto_recibido=recibido,
            cambio=recibido - total if metodo == "efectivo" else 0,
            referencia_transferencia=referencia if metodo == "transferencia" else "",  # <-- CAMBIO AQUÍ
            estado_pago="confirmado",
            fecha_hora=fecha_local,
        )

        # Cambiar estado del pedido
        pedido.estado = "finalizado"
        pedido.save()

    # ================================
    # WEBSOCKET → NOTIFICAR AL CAJERO
    # ================================
    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        "pedidos_activos",
        {
            "type": "nuevo_pagado",
            "origen": "domicilio",
            "pedido_id": pedido.id,
            "cliente": pedido.nombre_cliente,
            "total": float(total),
            "fecha": fecha_local.strftime("%d/%m/%Y %H:%M"),
            "estado_pago": "confirmado",
        }
    )

    # ================================
    # COMPROBANTE
    # ================================
    numero = f"D-{pedido.id}-{pago.id}"

    comprobante = Comprobante.objects.create(
        pago=pago,
        numero_comprobante=numero,
        nombre_cliente="Consumidor final",
        direccion_cliente=pedido.direccion_entrega,
        correo_cliente=None
    )

    generar_comprobante_pdf(comprobante)

    return JsonResponse({
        "success": True,
        "message": "Pago registrado correctamente.",
        "comprobante_url": comprobante.archivo_pdf.url
    })

@login_required(login_url='login')
def ver_comprobante(request, comp_id):

    comprobante = get_object_or_404(Comprobante, id=comp_id)
    pago = comprobante.pago
    pedido = pago.pedido
    detalles = pedido.detalles.all()

    # Seleccionar comprobante según tipo de pedido
    if pedido.tipo_pedido == "restaurante":
        template = "cajero/comprobantes/comprobante_restaurante.html"
    else:
        template = "cajero/comprobantes/comprobante_domicilio.html"

    return render(request, template, {
        "comprobante": comprobante,
        "pago": pago,
        "pedido": pedido,
        "detalles": detalles
    })

def generar_comprobante_pdf(comprobante):
    pago = comprobante.pago
    pedido = pago.pedido
    detalles = pedido.detalles.all()

    # seleccionar plantilla
    if pedido.tipo_pedido == "restaurante":
        template = "cajero/comprobantes/comprobante_restaurante.html"
    else:
        template = "cajero/comprobantes/comprobante_domicilio.html"

    html_string = render_to_string(template, {
        "comprobante": comprobante,
        "pago": pago,
        "pedido": pedido,
        "detalles": detalles
    })

    pdf_file = HTML(string=html_string).write_pdf()

    nombre_archivo = f"{comprobante.numero_comprobante}.pdf"
    comprobante.archivo_pdf.save(
        nombre_archivo,
        ContentFile(pdf_file),
        save=True
    )

#-----------------------------
# Reportes
#-----------------------------
def reportes_general(request):
    return render(request, 'administrador/reportes/reportes_general.html')

@login_required(login_url='login')
@rol_requerido('admin')
def reporte_pagos_restaurante(request):

    pagos = Pago.objects.filter(
        pedido__tipo_pedido='restaurante',
        estado_pago='confirmado'
    ).select_related('pedido')

    fecha_inicio = request.GET.get("inicio")
    fecha_fin = request.GET.get("fin")
    metodo = request.GET.get("metodo")
    mesero_id = request.GET.get("mesero")

    if fecha_inicio:
        pagos = pagos.filter(fecha_hora__date__gte=fecha_inicio)

    if fecha_fin:
        pagos = pagos.filter(fecha_hora__date__lte=fecha_fin)

    if metodo and metodo != "todos":
        pagos = pagos.filter(metodo_pago=metodo)

    if mesero_id and mesero_id != "todos":
        pagos = pagos.filter(pedido__mesero_id=mesero_id)

    total_recaudado = pagos.aggregate(total=Sum('total'))['total'] or 0

    meseros = Usuario.objects.filter(rol='mesero')

    return render(request, "administrador/reportes/reporte_restaurante.html", {
        "pagos": pagos,
        "total_recaudado": total_recaudado,
        "meseros": meseros,
    })

@login_required(login_url='login')
@rol_requerido('admin')
def reporte_pagos_domicilio(request):

    pagos = Pago.objects.filter(
        pedido__tipo_pedido='domicilio',
        estado_pago='confirmado'
    ).select_related('pedido')

    fecha_inicio = request.GET.get("inicio")
    fecha_fin = request.GET.get("fin")
    metodo = request.GET.get("metodo")
    cajero_id = request.GET.get("cajero")

    if fecha_inicio:
        pagos = pagos.filter(fecha_hora__date__gte=fecha_inicio)

    if fecha_fin:
        pagos = pagos.filter(fecha_hora__date__lte=fecha_fin)

    if metodo and metodo != "todos":
        pagos = pagos.filter(metodo_pago=metodo)

    if cajero_id and cajero_id != "todos":
        pagos = pagos.filter(pedido__cajero_id=cajero_id)

    total_recaudado = pagos.aggregate(total=Sum('total'))['total'] or 0

    cajeros = Usuario.objects.filter(rol='cajero')

    return render(request, "administrador/reportes/reporte_domicilio.html", {
        "pagos": pagos,
        "total_recaudado": total_recaudado,
        "cajeros": cajeros,
    })

@login_required(login_url='login')
@rol_requerido('admin')
def reporte_pedidos_restaurante(request):

    pedidos = Pedido.objects.filter(
        tipo_pedido='restaurante'
    ).select_related('mesa', 'mesero').prefetch_related('detalles')

    # ----------- FILTROS -----------
    fecha_inicio = request.GET.get("inicio")
    fecha_fin = request.GET.get("fin")
    estado = request.GET.get("estado")
    mesero_id = request.GET.get("mesero")

    if fecha_inicio:
        pedidos = pedidos.filter(fecha_hora__date__gte=fecha_inicio)

    if fecha_fin:
        pedidos = pedidos.filter(fecha_hora__date__lte=fecha_fin)

    if estado and estado != "todos":
        pedidos = pedidos.filter(estado=estado)

    if mesero_id and mesero_id != "todos":
        pedidos = pedidos.filter(mesero_id=mesero_id)

    # ----------- RESÚMENES -----------
    total_pedidos = pedidos.count()
    total_ventas = pedidos.aggregate(total=Sum('total'))['total'] or 0

    meseros = Usuario.objects.filter(rol='mesero')

    return render(request, "administrador/reportes/reporte_pedidos_restaurante.html", {
        "pedidos": pedidos.order_by('-fecha_hora'),
        "total_pedidos": total_pedidos,
        "total_ventas": total_ventas,
        "meseros": meseros,
    })

@login_required(login_url='login')
@rol_requerido('admin')
def reporte_pedidos_domicilio(request):

    pedidos = Pedido.objects.filter(
        tipo_pedido='domicilio'
    ).select_related('cajero')

    # Filtros
    fecha_inicio = request.GET.get("inicio")
    fecha_fin = request.GET.get("fin")
    estado = request.GET.get("estado")
    cajero_id = request.GET.get("cajero")

    if fecha_inicio:
        pedidos = pedidos.filter(fecha_hora__date__gte=fecha_inicio)

    if fecha_fin:
        pedidos = pedidos.filter(fecha_hora__date__lte=fecha_fin)

    if estado and estado != "todos":
        pedidos = pedidos.filter(estado=estado)

    if cajero_id and cajero_id != "todos":
        pedidos = pedidos.filter(cajero_id=cajero_id)

    total_pedidos = pedidos.count()
    total_ventas = pedidos.aggregate(total=Sum('total'))['total'] or 0

    cajeros = Usuario.objects.filter(rol='cajero')

    return render(request, "administrador/reportes/reporte_pedidos_domicilio.html", {
        "pedidos": pedidos,
        "total_pedidos": total_pedidos,
        "total_ventas": total_ventas,
        "cajeros": cajeros,
    })

def obtener_logo():
    logo_path = os.path.join(settings.MEDIA_ROOT, 'logo', 'logo.jpeg')
    if os.path.exists(logo_path):
        return Image(logo_path, width=110, height=100)
    return None

#-----------------------------
#Exportar en pdf
#-----------------------------
@login_required
@rol_requerido('admin')
def exportar_pedidos_restaurante_pdf(request):

    pedidos = Pedido.objects.filter(
        tipo_pedido='restaurante'
    ).select_related('mesa', 'mesero')

    # ======= FILTROS (IGUAL QUE EL REPORTE HTML) =======
    inicio = request.GET.get("inicio")
    fin = request.GET.get("fin")
    estado = request.GET.get("estado")
    mesero = request.GET.get("mesero")

    if inicio:
        pedidos = pedidos.filter(fecha_hora__date__gte=inicio)
    if fin:
        pedidos = pedidos.filter(fecha_hora__date__lte=fin)
    if estado and estado != "todos":
        pedidos = pedidos.filter(estado=estado)
    if mesero and mesero != "todos":
        pedidos = pedidos.filter(mesero_id=mesero)

    total_final = pedidos.aggregate(total=Sum('total'))['total'] or 0
    fecha_reporte = timezone.localtime().strftime("%d/%m/%Y %H:%M")

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="pedidos_restaurante.pdf"'
    doc = SimpleDocTemplate(response, pagesize=A4)

    elementos = []

    # LOGO
    logo = obtener_logo()
    if logo:
        elementos.append(logo)

    elementos.append(Spacer(1, 8))

    elementos.append(Table(
        [["CAFÉ RESTAURANTE PRODUCTOS CARLOS GERARDO"]],
        colWidths=[480],
        style=[
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONT', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 14),
        ]
    ))

    elementos.append(Spacer(1, 6))
    elementos.append(Table([[f"Fecha de reporte: {fecha_reporte}"]], colWidths=[480]))
    elementos.append(Spacer(1, 10))

    elementos.append(Table(
        [["REPORTE DE PEDIDOS - RESTAURANTE"]],
        colWidths=[480],
        style=[
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#cd966c")),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONT', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 13),
        ]
    ))

    elementos.append(Spacer(1, 10))

    data = [["Pedido", "Fecha", "Mesa", "Mesero", "Estado", "Total"]]

    for p in pedidos:
        data.append([
            p.codigo_pedido,
            p.fecha_hora.strftime("%d/%m/%Y %H:%M"),
            p.mesa.numero if p.mesa else "—",
            p.mesero.nombre if p.mesero else "",
            p.estado.capitalize(),
            f"$ {p.total:.2f}"
        ])

    tabla = Table(data, colWidths=[60, 90, 50, 90, 80, 60])
    tabla.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#b4764f")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONT', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,1), (-1,-1), 'CENTER'),
    ]))

    elementos.append(tabla)
    elementos.append(Spacer(1, 12))

    elementos.append(Table(
        [["TOTAL GENERAL", f"$ {total_final:.2f}"]],
        colWidths=[350, 130],
        style=[
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#3E7A3F")),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.white),
            ('FONT', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ]
    ))

    doc.build(elementos)
    return response

@login_required
@rol_requerido('admin')
def exportar_pedidos_domicilio_pdf(request):

    pedidos = Pedido.objects.filter(
        tipo_pedido='domicilio'
    ).select_related('cajero')

    # ===== FILTROS =====
    inicio = request.GET.get("inicio")
    fin = request.GET.get("fin")
    estado = request.GET.get("estado")
    cajero = request.GET.get("cajero")

    if inicio:
        pedidos = pedidos.filter(fecha_hora__date__gte=inicio)
    if fin:
        pedidos = pedidos.filter(fecha_hora__date__lte=fin)
    if estado and estado != "todos":
        pedidos = pedidos.filter(estado=estado)
    if cajero and cajero != "todos":
        pedidos = pedidos.filter(cajero_id=cajero)

    total_final = pedidos.aggregate(total=Sum('total'))['total'] or 0
    fecha_reporte = timezone.localtime().strftime("%d/%m/%Y %H:%M")

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="pedidos_domicilio.pdf"'
    doc = SimpleDocTemplate(response, pagesize=A4)

    elementos = []

    logo = obtener_logo()
    if logo:
        elementos.append(logo)

    elementos.append(Spacer(1, 8))

    elementos.append(Table(
        [["CAFÉ RESTAURANTE PRODUCTOS CARLOS GERARDO"]],
        colWidths=[480],
        style=[
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONT', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 14),
        ]
    ))

    elementos.append(Spacer(1, 6))
    elementos.append(Table([[f"Fecha de reporte: {fecha_reporte}"]], colWidths=[480]))
    elementos.append(Spacer(1, 10))

    elementos.append(Table(
        [["REPORTE DE PEDIDOS - DOMICILIO"]],
        colWidths=[480],
        style=[
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#cd966c")),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONT', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 13),
        ]
    ))

    elementos.append(Spacer(1, 10))

    data = [["Pedido", "Cliente", "Cajero", "Estado", "Fecha", "Total"]]

    for p in pedidos:
        data.append([
            p.codigo_pedido,
            p.nombre_cliente,
            p.cajero.nombre if p.cajero else "",
            p.estado.capitalize(),
            p.fecha_hora.strftime("%d/%m/%Y %H:%M"),
            f"$ {p.total:.2f}"
        ])

    tabla = Table(data, colWidths=[60, 140, 90, 80, 90, 60])
    tabla.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#b4764f")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONT', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,1), (-1,-1), 'CENTER'),
    ]))

    elementos.append(tabla)
    elementos.append(Spacer(1, 12))

    elementos.append(Table(
        [["TOTAL GENERAL", f"$ {total_final:.2f}"]],
        colWidths=[350, 130],
        style=[
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#3E7A3F")),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.white),
            ('FONT', (0,0), (-1,-1), 'Helvetica-Bold'),
        ]
    ))

    doc.build(elementos)
    return response

@login_required
@rol_requerido('admin')
def exportar_cobros_domicilio_pdf(request):

    pagos = Pago.objects.filter(
        pedido__tipo_pedido='domicilio',
        estado_pago='confirmado'
    ).select_related('pedido', 'pedido__cajero')

    # ================= FILTROS =================
    if request.GET.get("inicio"):
        pagos = pagos.filter(fecha_hora__date__gte=request.GET["inicio"])

    if request.GET.get("fin"):
        pagos = pagos.filter(fecha_hora__date__lte=request.GET["fin"])

    if request.GET.get("metodo") and request.GET["metodo"] != "todos":
        pagos = pagos.filter(metodo_pago=request.GET["metodo"])

    if request.GET.get("cajero") and request.GET["cajero"] != "todos":
        pagos = pagos.filter(pedido__cajero_id=request.GET["cajero"])
    # ===========================================

    total_final = pagos.aggregate(total=Sum('total'))['total'] or 0
    fecha_reporte = timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="cobros_domicilio.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4)
    elementos = []

    logo = obtener_logo()
    if logo:
        elementos.append(logo)

    elementos.append(Spacer(1, 10))

    elementos.append(Table(
        [["CAFÉ RESTAURANTE PRODUCTOS CARLOS GERARDO"]],
        colWidths=[480],
        style=[
            ('ALIGN',(0,0),(-1,-1),'CENTER'),
            ('FONT',(0,0),(-1,-1),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,-1),13),
        ]
    ))

    elementos.append(Spacer(1, 6))
    elementos.append(Table([[f"Fecha de reporte: {fecha_reporte}"]], colWidths=[480]))
    elementos.append(Spacer(1, 10))

    elementos.append(Table(
        [["REPORTE DE COBROS - DOMICILIO"]],
        colWidths=[480],
        style=[
            ('BACKGROUND',(0,0),(-1,-1),colors.HexColor("#cd966c")),
            ('TEXTCOLOR',(0,0),(-1,-1),colors.white),
            ('ALIGN',(0,0),(-1,-1),'CENTER'),
            ('FONT',(0,0),(-1,-1),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,-1),14),
        ]
    ))

    elementos.append(Spacer(1, 10))

    data = [["Pedido", "Cliente", "Cajero", "Método", "Total", "Fecha"]]

    for p in pagos:
        data.append([
            p.pedido.codigo_pedido,
            p.pedido.nombre_cliente,
            p.pedido.cajero.nombre if p.pedido.cajero else "",
            p.metodo_pago.capitalize(),
            f"$ {p.total:.2f}",
            p.fecha_hora.strftime("%d/%m/%Y %H:%M")
        ])

    tabla = Table(data, colWidths=[60,120,90,80,60,90])
    tabla.setStyle(TableStyle([
        ('GRID',(0,0),(-1,-1),1,colors.black),
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor("#b4764f")),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONT',(0,0),(-1,0),'Helvetica-Bold'),
        ('ALIGN',(0,1),(-1,-1),'CENTER'),
    ]))

    elementos.append(tabla)
    elementos.append(Spacer(1, 12))

    elementos.append(Table(
        [["TOTAL RECAUDADO", f"$ {total_final:.2f}"]],
        colWidths=[350,130],
        style=[
            ('BACKGROUND',(0,0),(-1,-1),colors.HexColor("#3E7A3F")),
            ('TEXTCOLOR',(0,0),(-1,-1),colors.white),
            ('FONT',(0,0),(-1,-1),'Helvetica-Bold'),
            ('ALIGN',(1,0),(1,0),'RIGHT'),
        ]
    ))

    doc.build(elementos)
    return response

@login_required
@rol_requerido('admin')
def exportar_cobros_restaurante_pdf(request):

    pagos = Pago.objects.filter(
        pedido__tipo_pedido='restaurante',
        estado_pago='confirmado'
    ).select_related('pedido', 'pedido__mesero', 'pedido__mesa')

    # ================= FILTROS (IGUALES AL HTML) =================
    inicio = request.GET.get("inicio")
    fin = request.GET.get("fin")
    metodo = request.GET.get("metodo")
    mesero_id = request.GET.get("mesero")

    if inicio:
        pagos = pagos.filter(fecha_hora__date__gte=inicio)

    if fin:
        pagos = pagos.filter(fecha_hora__date__lte=fin)

    if metodo and metodo != "todos":
        pagos = pagos.filter(metodo_pago=metodo)

    if mesero_id and mesero_id != "todos":
        pagos = pagos.filter(pedido__mesero_id=mesero_id)

    # ================= TOTALES =================
    total_final = pagos.aggregate(total=Sum('total'))['total'] or 0
    fecha_reporte = timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")

    # ================= PDF =================
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="cobros_restaurante.pdf"'
    doc = SimpleDocTemplate(response, pagesize=A4)

    elementos = []

    # LOGO
    logo = obtener_logo()
    if logo:
        elementos.append(logo)

    elementos.append(Spacer(1, 10))

    elementos.append(Table(
        [["CAFÉ RESTAURANTE PRODUCTOS CARLOS GERARDO"]],
        colWidths=[480],
        style=[
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONT', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 13),
        ]
    ))

    elementos.append(Spacer(1, 6))

    elementos.append(Table(
        [[f"Fecha de reporte: {fecha_reporte}"]],
        colWidths=[480],
        style=[('ALIGN', (0,0), (-1,-1), 'CENTER')]
    ))

    elementos.append(Spacer(1, 10))

    elementos.append(Table(
        [["REPORTE DE COBROS - RESTAURANTE"]],
        colWidths=[480],
        style=[
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#cd966c")),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONT', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 14),
        ]
    ))

    elementos.append(Spacer(1, 10))

    # ================= TABLA =================
    data = [["Pedido", "Mesa", "Mesero", "Método", "Total", "Fecha"]]

    for p in pagos:
        data.append([
            p.pedido.codigo_pedido,
            p.pedido.mesa.numero if p.pedido.mesa else "—",
            p.pedido.mesero.nombre if p.pedido.mesero else "",
            p.metodo_pago.capitalize(),
            f"$ {p.total:.2f}",
            p.fecha_hora.strftime("%d/%m/%Y %H:%M")
        ])

    tabla = Table(data, colWidths=[60, 60, 90, 80, 60, 90])
    tabla.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#b4764f")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONT', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,1), (-1,-1), 'CENTER'),
    ]))

    elementos.append(tabla)
    elementos.append(Spacer(1, 12))

    # ================= TOTAL =================
    elementos.append(Table(
        [["TOTAL RECAUDADO", f"$ {total_final:.2f}"]],
        colWidths=[350, 130],
        style=[
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#3E7A3F")),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.white),
            ('FONT', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ]
    ))

    doc.build(elementos)
    return response

#---------------------------
#exportar en excel
#---------------------------
def estilos_tabla():
    header_fill = PatternFill("solid", fgColor="CD966C")
    header_font = Font(bold=True, color="FFFFFF")
    center = Alignment(horizontal="center", vertical="center")
    border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    return header_fill, header_font, center, border

@login_required
@rol_requerido('admin')
def exportar_pedidos_restaurante_excel(request):

    pedidos = Pedido.objects.filter(
        tipo_pedido='restaurante'
    ).select_related('mesa', 'mesero')

    # -------- FILTROS --------
    if request.GET.get('inicio'):
        pedidos = pedidos.filter(fecha_hora__date__gte=request.GET['inicio'])
    if request.GET.get('fin'):
        pedidos = pedidos.filter(fecha_hora__date__lte=request.GET['fin'])
    if request.GET.get('estado') and request.GET['estado'] != 'todos':
        pedidos = pedidos.filter(estado=request.GET['estado'])
    if request.GET.get('mesero') and request.GET['mesero'] != 'todos':
        pedidos = pedidos.filter(mesero_id=request.GET['mesero'])

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Pedidos Restaurante"

    header_fill, header_font, center, border = estilos_tabla()

    # -------- LOGO --------
    logo_path = os.path.join(settings.MEDIA_ROOT, 'logo', 'logo.jpeg')
    if os.path.exists(logo_path):
        logo = ExcelImage(logo_path)
        logo.width = 120
        logo.height = 60
        ws.add_image(logo, "A1")

    # -------- TITULOS --------
    ws.merge_cells("A3:F3")
    ws["A3"] = "CAFÉ RESTAURANTE PRODUCTOS CARLOS GERARDO"
    ws["A3"].font = Font(bold=True, size=14)
    ws["A3"].alignment = center

    ws.merge_cells("A4:F4")
    ws["A4"] = f"Reporte generado: {timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M')}"
    ws["A4"].alignment = center

    # -------- ENCABEZADOS --------
    headers = ["Código", "Fecha", "Mesa", "Mesero", "Estado", "Total"]
    ws.append([])
    ws.append(headers)

    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=6, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center
        cell.border = border

    # -------- DATOS --------
    for p in pedidos:
        ws.append([
            p.codigo_pedido,
            p.fecha_hora.strftime('%d/%m/%Y %H:%M'),
            p.mesa.numero if p.mesa else "",
            p.mesero.nombre if p.mesero else "",
            p.estado.capitalize(),
            float(p.total)
        ])

    # -------- FORMATO --------
    for row in ws.iter_rows(min_row=7, max_row=ws.max_row, max_col=6):
        for cell in row:
            cell.border = border
            cell.alignment = center

    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 20

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="pedidos_restaurante.xlsx"'
    wb.save(response)
    return response

@login_required
@rol_requerido('admin')
def exportar_pedidos_domicilio_excel(request):

    pedidos = Pedido.objects.filter(
        tipo_pedido='domicilio'
    ).select_related('cajero')

    # -------- FILTROS --------
    if request.GET.get('inicio'):
        pedidos = pedidos.filter(fecha_hora__date__gte=request.GET['inicio'])
    if request.GET.get('fin'):
        pedidos = pedidos.filter(fecha_hora__date__lte=request.GET['fin'])
    if request.GET.get('estado') and request.GET['estado'] != 'todos':
        pedidos = pedidos.filter(estado=request.GET['estado'])
    if request.GET.get('cajero') and request.GET['cajero'] != 'todos':
        pedidos = pedidos.filter(cajero_id=request.GET['cajero'])

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Pedidos Domicilio"

    header_fill, header_font, center, border = estilos_tabla()

    # -------- LOGO --------
    logo_path = os.path.join(settings.MEDIA_ROOT, 'logo', 'logo.jpeg')
    if os.path.exists(logo_path):
        logo = ExcelImage(logo_path)
        logo.width = 120
        logo.height = 60
        ws.add_image(logo, "A1")

    # -------- TITULOS --------
    ws.merge_cells("A3:G3")
    ws["A3"] = "CAFÉ RESTAURANTE PRODUCTOS CARLOS GERARDO"
    ws["A3"].font = Font(bold=True, size=14)
    ws["A3"].alignment = center

    ws.merge_cells("A4:G4")
    ws["A4"] = f"Reporte generado: {timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M')}"
    ws["A4"].alignment = center

    # -------- ENCABEZADOS --------
    headers = ["Código", "Fecha", "Cliente", "Dirección", "Cajero", "Estado", "Total"]
    ws.append([])
    ws.append(headers)

    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=6, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center
        cell.border = border

    # -------- DATOS --------
    for p in pedidos:
        ws.append([
            p.codigo_pedido,
            p.fecha_hora.strftime('%d/%m/%Y %H:%M'),
            p.nombre_cliente,
            p.direccion_entrega,
            p.cajero.nombre if p.cajero else "",
            p.estado.capitalize(),
            float(p.total)
        ])

    # -------- FORMATO --------
    for row in ws.iter_rows(min_row=7, max_row=ws.max_row, max_col=7):
        for cell in row:
            cell.border = border
            cell.alignment = center

    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 22

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="pedidos_domicilio.xlsx"'
    wb.save(response)
    return response

@login_required
@rol_requerido('admin')
def exportar_cobros_restaurante_excel(request):

    pagos = Pago.objects.filter(
        pedido__tipo_pedido='restaurante',
        estado_pago='confirmado'
    ).select_related('pedido', 'pedido__mesero', 'pedido__mesa')

    # -------- FILTROS --------
    if request.GET.get('inicio'):
        pagos = pagos.filter(fecha_hora__date__gte=request.GET['inicio'])

    if request.GET.get('fin'):
        pagos = pagos.filter(fecha_hora__date__lte=request.GET['fin'])

    if request.GET.get('metodo') and request.GET['metodo'] != 'todos':
        pagos = pagos.filter(metodo_pago=request.GET['metodo'])

    if request.GET.get('cajero') and request.GET['cajero'] != 'todos':
        pagos = pagos.filter(pedido__mesero_id=request.GET['cajero'])

    total_recaudado = pagos.aggregate(total=Sum('total'))['total'] or 0

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Cobros Restaurante"

    header_fill, header_font, center, border = estilos_tabla()

    # -------- LOGO --------
    logo_path = os.path.join(settings.MEDIA_ROOT, 'logo', 'logo.jpeg')
    if os.path.exists(logo_path):
        logo = ExcelImage(logo_path)
        logo.width = 110
        logo.height = 100
        ws.add_image(logo, "A1")

    # -------- TITULOS --------
    ws.merge_cells("A3:F3")
    ws["A3"] = "CAFÉ RESTAURANTE PRODUCTOS CARLOS GERARDO"
    ws["A3"].font = Font(bold=True, size=14)
    ws["A3"].alignment = center

    ws.merge_cells("A4:F4")
    ws["A4"] = f"Reporte generado: {timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M')}"
    ws["A4"].alignment = center

    # -------- ENCABEZADOS TABLA --------
    headers = ["Pedido", "Mesa", "Mesero", "Método", "Total", "Fecha"]
    ws.append([])
    ws.append(headers)

    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=6, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center
        cell.border = border

    # -------- DATOS --------
    for p in pagos:
        ws.append([
            p.pedido.codigo_pedido,
            p.pedido.mesa.numero if p.pedido.mesa else "",
            p.pedido.mesero.nombre if p.pedido.mesero else "",
            p.metodo_pago.capitalize(),
            float(p.total),
            p.fecha_hora.strftime('%d/%m/%Y %H:%M')
        ])

    # -------- FORMATO FILAS --------
    for row in ws.iter_rows(min_row=7, max_row=ws.max_row, max_col=6):
        for cell in row:
            cell.border = border
            cell.alignment = center

    # -------- TOTAL --------
    ws.append([])
    total_row = ws.max_row + 1
    ws.merge_cells(start_row=total_row, start_column=1, end_row=total_row, end_column=4)
    ws.cell(row=total_row, column=1, value="TOTAL RECAUDADO").font = Font(bold=True)
    ws.cell(row=total_row, column=1).alignment = Alignment(horizontal="right")
    ws.cell(row=total_row, column=5, value=float(total_recaudado)).font = Font(bold=True)

    # -------- AUTO ANCHO --------
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 22

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="cobros_restaurante.xlsx"'
    wb.save(response)
    return response

@login_required
@rol_requerido('admin')
def exportar_cobros_domicilio_excel(request):

    pagos = Pago.objects.filter(
        pedido__tipo_pedido='domicilio',
        estado_pago='confirmado'
    ).select_related('pedido', 'pedido__cajero')

    # -------- FILTROS --------
    if request.GET.get('inicio'):
        pagos = pagos.filter(fecha_hora__date__gte=request.GET['inicio'])
    if request.GET.get('fin'):
        pagos = pagos.filter(fecha_hora__date__lte=request.GET['fin'])
    if request.GET.get('metodo') and request.GET['metodo'] != 'todos':
        pagos = pagos.filter(metodo_pago=request.GET['metodo'])
    if request.GET.get('cajero') and request.GET['cajero'] != 'todos':
        pagos = pagos.filter(pedido__cajero_id=request.GET['cajero'])

    total_recaudado = pagos.aggregate(total=Sum('total'))['total'] or 0

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Cobros Domicilio"

    header_fill, header_font, center, border = estilos_tabla()

    # -------- LOGO --------
    logo_path = os.path.join(settings.MEDIA_ROOT, 'logo', 'logo.jpeg')
    if os.path.exists(logo_path):
        img = ExcelImage(logo_path)
        img.width = 110
        img.height = 100
        ws.add_image(img, "A1")

    # -------- TITULOS --------
    ws.merge_cells("A3:F3")
    ws["A3"] = "CAFÉ RESTAURANTE PRODUCTOS CARLOS GERARDO"
    ws["A3"].font = Font(bold=True, size=14)
    ws["A3"].alignment = center

    ws.merge_cells("A4:F4")
    ws["A4"] = f"Reporte generado: {timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M')}"
    ws["A4"].alignment = center

    # -------- ENCABEZADOS --------
    headers = ["Pedido", "Cliente", "Cajero", "Método", "Total", "Fecha"]
    ws.append([])
    ws.append(headers)

    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=6, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center
        cell.border = border

    # -------- DATOS --------
    for p in pagos:
        ws.append([
            p.pedido.codigo_pedido,
            p.pedido.nombre_cliente,
            p.pedido.cajero.nombre if p.pedido.cajero else "",
            p.metodo_pago.capitalize(),
            float(p.total),
            p.fecha_hora.strftime('%d/%m/%Y %H:%M')
        ])

    # -------- FORMATO --------
    for row in ws.iter_rows(min_row=7, max_row=ws.max_row, max_col=6):
        for cell in row:
            cell.border = border
            cell.alignment = center

    # -------- TOTAL --------
    ws.append([])
    ws.append(["", "", "", "TOTAL RECAUDADO", float(total_recaudado), ""])
    ws[f"E{ws.max_row}"].font = Font(bold=True)

    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 22

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="cobros_domicilio.xlsx"'
    wb.save(response)
    return response

@login_required
@rol_requerido('admin', 'cajero')
def reporte_unificado(request):

    pagos = Pago.objects.filter(
        estado_pago='confirmado'
    ).select_related(
        'pedido',
        'pedido__mesa',
        'pedido__mesero',
        'pedido__cajero'
    )

    # -------- FILTROS --------
    if request.GET.get('inicio'):
        pagos = pagos.filter(fecha_hora__date__gte=request.GET['inicio'])

    if request.GET.get('fin'):
        pagos = pagos.filter(fecha_hora__date__lte=request.GET['fin'])

    if request.GET.get('tipo') and request.GET['tipo'] != 'todos':
        pagos = pagos.filter(pedido__tipo_pedido=request.GET['tipo'])

    if request.GET.get('metodo') and request.GET['metodo'] != 'todos':
        pagos = pagos.filter(metodo_pago=request.GET['metodo'])

    total_recaudado = pagos.aggregate(total=Sum('total'))['total'] or 0

    return render(
        request,
        'administrador/reportes/reporte_unificado.html',
        {
            'pagos': pagos,
            'total_recaudado': total_recaudado
        }
    )

@login_required
@rol_requerido('admin', 'cajero')
def exportar_unificado_pdf(request):

    pagos = Pago.objects.filter(
        estado_pago='confirmado'
    ).select_related(
        'pedido',
        'pedido__mesa',
        'pedido__mesero',
        'pedido__cajero'
    )

    # ================= FILTROS =================
    inicio = request.GET.get("inicio")
    fin = request.GET.get("fin")
    tipo = request.GET.get("tipo")
    metodo = request.GET.get("metodo")

    if inicio:
        pagos = pagos.filter(fecha_hora__date__gte=inicio)

    if fin:
        pagos = pagos.filter(fecha_hora__date__lte=fin)

    if tipo and tipo != "todos":
        pagos = pagos.filter(pedido__tipo_pedido=tipo)

    if metodo and metodo != "todos":
        pagos = pagos.filter(metodo_pago=metodo)

    # ================= TOTALES =================
    total_recaudado = pagos.aggregate(total=Sum('total'))['total'] or 0
    fecha_reporte = timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")

    # ================= PDF =================
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="reporte_unificado.pdf"'
    doc = SimpleDocTemplate(response, pagesize=A4)

    elementos = []

    # ================= LOGO =================
    logo_path = os.path.join(settings.MEDIA_ROOT, 'logo', 'logo.jpeg')
    if os.path.exists(logo_path):
        elementos.append(Image(logo_path, width=110, height=70))

    elementos.append(Spacer(1, 10))

    # ================= NOMBRE LOCAL =================
    elementos.append(Table(
        [["CAFÉ RESTAURANTE PRODUCTOS CARLOS GERARDO"]],
        colWidths=[480],
        style=[
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONT', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 13),
        ]
    ))

    elementos.append(Spacer(1, 6))

    elementos.append(Table(
        [[f"Fecha de reporte: {fecha_reporte}"]],
        colWidths=[480],
        style=[('ALIGN', (0,0), (-1,-1), 'CENTER')]
    ))

    elementos.append(Spacer(1, 10))

    # ================= TITULO =================
    elementos.append(Table(
        [["REPORTE UNIFICADO - PEDIDOS Y COBROS"]],
        colWidths=[480],
        style=[
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#cd966c")),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONT', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 14),
        ]
    ))

    elementos.append(Spacer(1, 10))

    # ================= TABLA =================
    data = [[
        "Pedido", "Tipo", "Cliente / Mesa",
        "Responsable", "Total", "Método", "Fecha"
    ]]

    for p in pagos:
        pedido = p.pedido
        if not pedido:
            continue  # por si acaso

        # --- Cliente / Mesa ---
        if pedido.tipo_pedido == 'domicilio':
            cliente_mesa = pedido.nombre_cliente or "Domicilio"
        else:
            if pedido.mesa:
                cliente_mesa = f"Mesa {pedido.mesa.numero}"
            else:
                cliente_mesa = "Sin mesa"

        # --- Responsable ---
        if pedido.tipo_pedido == 'domicilio':
            responsable = pedido.cajero.nombre if pedido.cajero else "Cajero no asignado"
        else:
            responsable = pedido.mesero.nombre if pedido.mesero else "Mesero no asignado"

        data.append([
            pedido.codigo_pedido,
            pedido.tipo_pedido.capitalize(),
            cliente_mesa,
            responsable,
            f"$ {p.total:.2f}",
            p.metodo_pago.capitalize(),
            p.fecha_hora.strftime("%d/%m/%Y %H:%M")
        ])

    tabla = Table(data, colWidths=[55, 65, 90, 90, 60, 65, 80])
    tabla.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#b4764f")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONT', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,1), (-1,-1), 'CENTER'),
    ]))

    elementos.append(tabla)
    elementos.append(Spacer(1, 12))

    # ================= TOTAL =================
    elementos.append(Table(
        [["TOTAL RECAUDADO", f"$ {total_recaudado:.2f}"]],
        colWidths=[350, 130],
        style=[
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#3E7A3F")),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.white),
            ('FONT', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ]
    ))

    doc.build(elementos)
    return response

@login_required
@rol_requerido('admin', 'cajero')
def exportar_unificado_excel(request):

    pagos = Pago.objects.filter(
        estado_pago='confirmado'
    ).select_related(
        'pedido',
        'pedido__mesa',
        'pedido__mesero',
        'pedido__cajero'
    )

    # -------- FILTROS --------
    if request.GET.get('inicio'):
        pagos = pagos.filter(fecha_hora__date__gte=request.GET['inicio'])

    if request.GET.get('fin'):
        pagos = pagos.filter(fecha_hora__date__lte=request.GET['fin'])

    if request.GET.get('tipo') and request.GET['tipo'] != 'todos':
        pagos = pagos.filter(pedido__tipo_pedido=request.GET['tipo'])

    if request.GET.get('metodo') and request.GET['metodo'] != 'todos':
        pagos = pagos.filter(metodo_pago=request.GET['metodo'])

    total_recaudado = pagos.aggregate(total=Sum('total'))['total'] or 0

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reporte Unificado"

    # ===== ESTILOS (IGUAL QUE OTROS REPORTES) =====
    header_fill, header_font, center, border = estilos_tabla()

    # -------- LOGO --------
    logo_path = os.path.join(settings.MEDIA_ROOT, 'logo', 'logo.jpeg')
    if os.path.exists(logo_path):
        img = ExcelImage(logo_path)
        img.width = 110
        img.height = 100
        ws.add_image(img, "A1")

    # -------- TÍTULOS --------
    ws.merge_cells("A3:G3")
    ws["A3"] = "CAFÉ RESTAURANTE PRODUCTOS CARLOS GERARDO"
    ws["A3"].font = Font(bold=True, size=14)
    ws["A3"].alignment = center

    ws.merge_cells("A4:G4")
    ws["A4"] = f"Reporte generado: {timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M')}"
    ws["A4"].alignment = center

    # -------- ENCABEZADOS --------
    headers = [
        "Pedido", "Tipo", "Cliente / Mesa",
        "Responsable", "Total", "Método", "Fecha"
    ]
    ws.append([])              # fila vacía
    ws.append(headers)         # encabezados
    header_row = ws.max_row    # normalmente será 6

    # Aplicar estilo de encabezado (como en cobros domicilio)
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=header_row, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center
        cell.border = border

    # -------- DATOS --------
    data_start_row = header_row + 1

    for p in pagos:
        pedido = p.pedido
        if not pedido:
            continue  # por seguridad

        # ------ Cliente / Mesa ------
        if pedido.tipo_pedido == 'domicilio':
            cliente_mesa = pedido.nombre_cliente or "Domicilio"
        else:
            if pedido.mesa:
                cliente_mesa = f"Mesa {pedido.mesa.numero}"
            else:
                cliente_mesa = "Sin mesa"

        # ------ Responsable ------
        if pedido.tipo_pedido == 'domicilio':
            responsable = pedido.cajero.nombre if pedido.cajero else "Cajero no asignado"
        else:
            responsable = pedido.mesero.nombre if pedido.mesero else "Mesero no asignado"

        # Fecha sin tz para Excel
        fecha_excel = timezone.localtime(p.fecha_hora).replace(tzinfo=None)

        ws.append([
            pedido.codigo_pedido,
            pedido.tipo_pedido.capitalize(),
            cliente_mesa,
            responsable,
            float(p.total),
            p.metodo_pago.capitalize(),
            fecha_excel
        ])

    # Aplicar bordes y centrado a TODA la tabla de datos
    for row in ws.iter_rows(min_row=data_start_row, max_row=ws.max_row, max_col=7):
        for cell in row:
            cell.border = border
            cell.alignment = center

    # -------- TOTAL --------
    ws.append([])
    ws.append(["", "", "", "TOTAL RECAUDADO", float(total_recaudado), "", ""])
    ws[f"E{ws.max_row}"].font = Font(bold=True)

    # -------- FORMATO FECHA --------
    for cell in ws["G"]:
        cell.number_format = "DD/MM/YYYY HH:MM"

    # -------- ANCHO COLUMNAS --------
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 22

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename=\"reporte_unificado.xlsx\"'
    wb.save(response)
    return response

# ======================= REPORTE UNIFICADO CAJERO (WEB) =======================
@login_required(login_url='login')
@rol_requerido('cajero')
def cajero_reporte_unificado(request):

    pagos = Pago.objects.filter(
        estado_pago='confirmado'
    ).select_related(
        'pedido',
        'pedido__mesa',
        'pedido__mesero',
        'pedido__cajero'
    )

    # -------- FILTROS --------
    if request.GET.get('inicio'):
        pagos = pagos.filter(fecha_hora__date__gte=request.GET['inicio'])

    if request.GET.get('fin'):
        pagos = pagos.filter(fecha_hora__date__lte=request.GET['fin'])

    if request.GET.get('tipo') and request.GET['tipo'] != 'todos':
        pagos = pagos.filter(pedido__tipo_pedido=request.GET['tipo'])

    if request.GET.get('metodo') and request.GET['metodo'] != 'todos':
        pagos = pagos.filter(metodo_pago=request.GET['metodo'])

    total_recaudado = pagos.aggregate(total=Sum('total'))['total'] or 0

    return render(
        request,
        'cajero/reporte/reporte_general.html',
        {
            'pagos': pagos,
            'total_recaudado': total_recaudado
        }
    )

# ======================= REPORTE UNIFICADO CAJERO (PDF) =======================
@login_required(login_url='login')
@rol_requerido('cajero')
def cajero_exportar_unificado_pdf(request):

    pagos = Pago.objects.filter(
        estado_pago='confirmado'
    ).select_related(
        'pedido',
        'pedido__mesa',
        'pedido__mesero',
        'pedido__cajero'
    )

    # ================= FILTROS =================
    inicio = request.GET.get("inicio")
    fin = request.GET.get("fin")
    tipo = request.GET.get("tipo")
    metodo = request.GET.get("metodo")

    if inicio:
        pagos = pagos.filter(fecha_hora__date__gte=inicio)

    if fin:
        pagos = pagos.filter(fecha_hora__date__lte=fin)

    if tipo and tipo != "todos":
        pagos = pagos.filter(pedido__tipo_pedido=tipo)

    if metodo and metodo != "todos":
        pagos = pagos.filter(metodo_pago=metodo)

    # ================= TOTALES =================
    total_recaudado = pagos.aggregate(total=Sum('total'))['total'] or 0
    fecha_reporte = timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")

    # ================= PDF =================
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="reporte_unificado_cajero.pdf"'
    doc = SimpleDocTemplate(response, pagesize=A4)

    elementos = []

    # ================= LOGO =================
    logo_path = os.path.join(settings.MEDIA_ROOT, 'logo', 'logo.jpeg')
    if os.path.exists(logo_path):
        elementos.append(Image(logo_path, width=110, height=70))

    elementos.append(Spacer(1, 10))

    # ================= NOMBRE LOCAL =================
    elementos.append(Table(
        [["CAFÉ RESTAURANTE PRODUCTOS CARLOS GERARDO"]],
        colWidths=[480],
        style=[
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONT', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 13),
        ]
    ))

    elementos.append(Spacer(1, 6))

    elementos.append(Table(
        [[f"Fecha de reporte: {fecha_reporte}"]],
        colWidths=[480],
        style=[('ALIGN', (0,0), (-1,-1), 'CENTER')]
    ))

    elementos.append(Spacer(1, 10))

    # ================= TITULO =================
    elementos.append(Table(
        [["REPORTE UNIFICADO - PEDIDOS Y COBROS"]],
        colWidths=[480],
        style=[
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#cd966c")),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONT', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 14),
        ]
    ))

    elementos.append(Spacer(1, 10))

    # ================= TABLA =================
    data = [[
        "Pedido", "Tipo", "Cliente / Mesa",
        "Responsable", "Total", "Método", "Fecha"
    ]]

    for p in pagos:
        pedido = p.pedido
        if not pedido:
            continue  # por si acaso

        # --- Cliente / Mesa ---
        if pedido.tipo_pedido == 'domicilio':
            cliente_mesa = pedido.nombre_cliente or "Domicilio"
        else:
            if pedido.mesa:
                cliente_mesa = f"Mesa {pedido.mesa.numero}"
            else:
                cliente_mesa = "Sin mesa"

        # --- Responsable ---
        if pedido.tipo_pedido == 'domicilio':
            responsable = pedido.cajero.nombre if pedido.cajero else "Cajero no asignado"
        else:
            responsable = pedido.mesero.nombre if pedido.mesero else "Mesero no asignado"

        data.append([
            pedido.codigo_pedido,
            pedido.tipo_pedido.capitalize(),
            cliente_mesa,
            responsable,
            f"$ {p.total:.2f}",
            p.metodo_pago.capitalize(),
            timezone.localtime(p.fecha_hora).strftime("%d/%m/%Y %H:%M")
        ])

    tabla = Table(data, colWidths=[55, 65, 90, 90, 60, 65, 80])
    tabla.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#b4764f")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONT', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,1), (-1,-1), 'CENTER'),
    ]))

    elementos.append(tabla)
    elementos.append(Spacer(1, 12))

    # ================= TOTAL =================
    elementos.append(Table(
        [["TOTAL RECAUDADO", f"$ {total_recaudado:.2f}"]],
        colWidths=[350, 130],
        style=[
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#3E7A3F")),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.white),
            ('FONT', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ]
    ))

    doc.build(elementos)
    return response

# ======================= REPORTE UNIFICADO CAJERO (EXCEL) =======================
@login_required(login_url='login')
@rol_requerido('cajero')
def cajero_exportar_unificado_excel(request):

    pagos = Pago.objects.filter(
        estado_pago='confirmado'
    ).select_related(
        'pedido',
        'pedido__mesa',
        'pedido__mesero',
        'pedido__cajero'
    )

    # -------- FILTROS --------
    if request.GET.get('inicio'):
        pagos = pagos.filter(fecha_hora__date__gte=request.GET['inicio'])

    if request.GET.get('fin'):
        pagos = pagos.filter(fecha_hora__date__lte=request.GET['fin'])

    if request.GET.get('tipo') and request.GET['tipo'] != 'todos':
        pagos = pagos.filter(pedido__tipo_pedido=request.GET['tipo'])

    if request.GET.get('metodo') and request.GET['metodo'] != 'todos':
        pagos = pagos.filter(metodo_pago=request.GET['metodo'])

    total_recaudado = pagos.aggregate(total=Sum('total'))['total'] or 0

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reporte Unificado"

    # ===== ESTILOS (IGUAL QUE OTROS REPORTES) =====
    header_fill, header_font, center, border = estilos_tabla()

    # -------- LOGO --------
    logo_path = os.path.join(settings.MEDIA_ROOT, 'logo', 'logo.jpeg')
    if os.path.exists(logo_path):
        img = ExcelImage(logo_path)
        img.width = 110
        img.height = 100
        ws.add_image(img, "A1")

    # -------- TÍTULOS --------
    ws.merge_cells("A3:G3")
    ws["A3"] = "CAFÉ RESTAURANTE PRODUCTOS CARLOS GERARDO"
    ws["A3"].font = Font(bold=True, size=14)
    ws["A3"].alignment = center

    ws.merge_cells("A4:G4")
    ws["A4"] = f"Reporte generado: {timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M')}"
    ws["A4"].alignment = center

    # -------- ENCABEZADOS --------
    headers = [
        "Pedido", "Tipo", "Cliente / Mesa",
        "Responsable", "Total", "Método", "Fecha"
    ]
    ws.append([])              # fila vacía
    ws.append(headers)         # encabezados
    header_row = ws.max_row    # normalmente será 6

    # Aplicar estilo de encabezado (como en cobros domicilio)
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=header_row, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center
        cell.border = border

    # -------- DATOS --------
    data_start_row = header_row + 1

    for p in pagos:
        pedido = p.pedido
        if not pedido:
            continue  # por seguridad

        # ------ Cliente / Mesa ------
        if pedido.tipo_pedido == 'domicilio':
            cliente_mesa = pedido.nombre_cliente or "Domicilio"
        else:
            if pedido.mesa:
                cliente_mesa = f"Mesa {pedido.mesa.numero}"
            else:
                cliente_mesa = "Sin mesa"

        # ------ Responsable ------
        if pedido.tipo_pedido == 'domicilio':
            responsable = pedido.cajero.nombre if pedido.cajero else "Cajero no asignado"
        else:
            responsable = pedido.mesero.nombre if pedido.mesero else "Mesero no asignado"

        # Fecha sin tz para Excel
        fecha_excel = timezone.localtime(p.fecha_hora).replace(tzinfo=None)

        ws.append([
            pedido.codigo_pedido,
            pedido.tipo_pedido.capitalize(),
            cliente_mesa,
            responsable,
            float(p.total),
            p.metodo_pago.capitalize(),
            fecha_excel
        ])

    # Aplicar bordes y centrado a TODA la tabla de datos
    for row in ws.iter_rows(min_row=data_start_row, max_row=ws.max_row, max_col=7):
        for cell in row:
            cell.border = border
            cell.alignment = center

    # -------- TOTAL --------
    ws.append([])
    ws.append(["", "", "", "TOTAL RECAUDADO", float(total_recaudado), "", ""])
    ws[f"E{ws.max_row}"].font = Font(bold=True)

    # -------- FORMATO FECHA --------
    for cell in ws["G"]:
        cell.number_format = "DD/MM/YYYY HH:MM"

    # -------- ANCHO COLUMNAS --------
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 22

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename=\"reporte_unificado_cajero.xlsx\"'
    wb.save(response)
    return response

@login_required(login_url='login')
@rol_requerido('cajero')
def tabla_pedidos_pagados_domicilio(request):

    hoy = timezone.localdate()

    pedidos_pagados = (
        Pedido.objects
        .filter(
            tipo_pedido='domicilio',
            cajero=request.user,
            pagos__estado_pago='confirmado',
            pagos__fecha_hora__date=hoy 
        )
        .prefetch_related('pagos__comprobante_set')
        .distinct()
        .order_by('-id')
    )

    # añadimos el último pago confirmado manualmente
    for p in pedidos_pagados:
        p.pago_confirmado = (
            p.pagos
            .filter(estado_pago='confirmado')
            .order_by('-id')
            .first()
        )

    html = render_to_string(
        "cajero/pago/tabla_pedidos_pagados_domicilio.html",
        {"pedidos_pagados": pedidos_pagados},
        request=request
    )

    return JsonResponse({"html": html})

# ----------------------------
# Cajero - Perfil
# ----------------------------
@login_required(login_url='login')
@rol_requerido('cajero')
def perfil_cajero(request):
    usuario = request.user   # cajero logueado
    return render(request, "cajero/perfil.html", {"usuario": usuario})

@login_required(login_url='login')
@rol_requerido('cajero')
def editar_perfil_cajero(request):
    usuario = request.user  # cajero logueado

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        apellido = request.POST.get("apellido", "").strip()
        correo = request.POST.get("correo", "").strip()
        telefono = request.POST.get("telefono", "").strip()
        direccion = request.POST.get("direccion", "").strip()
        password = request.POST.get("password", "")
        password2 = request.POST.get("password2", "")

        # -----------------------------
        # VALIDACIONES BACKEND
        # -----------------------------

        # Nombre y apellido: solo letras
        if not re.match(r'^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$', nombre):
            messages.error(request, "El nombre solo debe contener letras.")
            return render(request, "cajero/editar_perfil.html", {"usuario": usuario})

        if not re.match(r'^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$', apellido):
            messages.error(request, "El apellido solo debe contener letras.")
            return render(request, "cajero/editar_perfil.html", {"usuario": usuario})

        # Correo obligatorio + válido
        if not correo:
            messages.error(request, "El correo es obligatorio.")
            return render(request, "cajero/editar_perfil.html", {"usuario": usuario})

        if not re.match(r"^[^@]+@[^@]+\.[^@]+$", correo):
            messages.error(request, "El formato del correo no es válido.")
            return render(request, "cajero/editar_perfil.html", {"usuario": usuario})

        # Validar correo no repetido (excepto el mismo usuario)
        if Usuario.objects.exclude(id=usuario.id).filter(correo=correo).exists():
            messages.error(request, "Ya existe un usuario con ese correo.")
            return render(request, "cajero/editar_perfil.html", {"usuario": usuario})

        # Teléfono obligatorio
        if not telefono:
            messages.error(request, "El teléfono es obligatorio.")
            return render(request, "cajero/editar_perfil.html", {"usuario": usuario})

        # Teléfono válido
        if not telefono.isdigit():
            messages.error(request, "El teléfono solo debe contener números.")
            return render(request, "cajero/editar_perfil.html", {"usuario": usuario})

        if len(telefono) != 10:
            messages.error(request, "El teléfono debe tener 10 dígitos.")
            return render(request, "cajero/editar_perfil.html", {"usuario": usuario})

        # Dirección obligatoria
        if not direccion:
            messages.error(request, "La dirección es obligatoria.")
            return render(request, "cajero/editar_perfil.html", {"usuario": usuario})
        
        # Contraseñas
        if password or password2:
            # Mínimo 6 caracteres
            if len(password) < 6:
                messages.error(request, "La contraseña debe tener mínimo 6 caracteres.")
                return render(request, "cajero/editar_perfil.html", {"usuario": usuario})

            if password != password2:
                messages.error(request, "Las contraseñas no coinciden.")
                return render(request, "cajero/editar_perfil.html", {"usuario": usuario})

            usuario.password = make_password(password)

        # Guardar datos generales
        usuario.nombre = nombre
        usuario.apellido = apellido
        usuario.correo = correo
        usuario.username = correo
        usuario.telefono = telefono
        usuario.direccion = direccion
        usuario.save()

        # Actualizar nombre en la sesión (opcional pero recomendable)
        request.session['usuario_nombre'] = f"{usuario.nombre} {usuario.apellido}"

        messages.success(request, "Perfil actualizado correctamente.")
        return redirect("perfil_cajero")

    return render(request, "cajero/editar_perfil.html", {"usuario": usuario})

#-----------------------------
#PERFIL - MESERO
#-----------------------------
@login_required
@rol_requerido('mesero')
def perfil_mesero(request):
    usuario = request.user  # si tu auth usa tu modelo Usuario como user
    return render(request, "mesero/perfil_mesero.html", {"usuario": usuario})


@login_required
@rol_requerido('mesero')
def editar_perfil_mesero(request):
    usuario = request.user

    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        apellido = request.POST.get("apellido", "").strip()
        correo = request.POST.get("correo", "").strip()
        telefono = request.POST.get("telefono", "").strip()
        direccion = request.POST.get("direccion", "").strip()

        password = request.POST.get("password", "").strip()
        password2 = request.POST.get("password2", "").strip()

        # Actualizar datos
        usuario.nombre = nombre
        usuario.apellido = apellido
        usuario.correo = correo
        usuario.telefono = telefono
        usuario.direccion = direccion

        # Cambiar contraseña (solo si llenó)
        if password or password2:
            if password != password2:
                messages.error(request, "Las contraseñas no coinciden.")
                return redirect("editar_perfil_mesero")

            if len(password) < 6:
                messages.error(request, "La contraseña debe tener mínimo 6 caracteres.")
                return redirect("editar_perfil_mesero")

            usuario.password = make_password(password)

        usuario.save()
        messages.success(request, "Perfil actualizado correctamente.")
        return redirect("perfil_mesero")

    return render(request, "mesero/editar_perfil_mesero.html", {"usuario": usuario})

