import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from .decorators import rol_requerido
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password
from .models import Usuario, Mesa, Pedido, DetallePedido, Producto, Notificacion, Mensaje
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
                return redirect('dashboard_cocinero')
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

        # Teléfono opcional, pero si existe debe tener 10 dígitos
        if telefono:
            if not telefono.isdigit():
                messages.error(request, "El teléfono solo debe contener números.")
                return render(request, "administrador/editar_perfil_admin.html", {"usuario": usuario})

            if len(telefono) != 10:
                messages.error(request, "El teléfono debe tener 10 dígitos.")
                return render(request, "administrador/editar_perfil_admin.html", {"usuario": usuario})

        # Contraseñas
        if password or password2:
            # Mínimo 6 caracteres
            if len(password) < 6:
                messages.error(request, "La contraseña debe tener mínimo 6 caracteres.")
                return render(request, "administrador/editar_perfil_admin.html", {"usuario": usuario})

            if password != password2:
                messages.error(request, "Las contraseñas no coinciden.")
                return render(request, "administrador/editar_perfil_admin.html", {"usuario": usuario})

            usuario.password = make_password(password)
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
    "Elimina un trabajador por su ID"
    if request.method == 'POST':
        trabajador = get_object_or_404(Usuario, id=trabajador_id)
        nombre_trabajador = f"{trabajador.nombre} {trabajador.apellido}"
        
        # Solo eliminar si no es administrador ni cliente
        if trabajador.rol in ['mesero', 'cocinero', 'cajero']:
            trabajador.delete()
            messages.success(request, f"Trabajador {nombre_trabajador} eliminado correctamente.")
        else:
            messages.error(request, "No se puede eliminar este usuario.")

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

        # Validación backend: nombre solo letras
        if not re.match(r'^[A-Za-zÁÉÍÓÚáéíóúÑñ ]+$', nombre):
            messages.error(request, "El nombre solo debe contener letras.")
            return render(request, 'administrador/menu/registrar_menu.html', {
                'nombre': nombre,
                'descripcion': descripcion,
                'precio': precio,
                'tipo': tipo,
            })

        # Validar que no esté vacío
        if not nombre or not precio or not tipo:
            messages.error(request, "Todos los campos obligatorios deben completarse.")
            return render(request, 'administrador/menu/registrar_menu.html', {
                'nombre': nombre,
                'descripcion': descripcion,
                'precio': precio,
                'tipo': tipo,
            })

        # Validar precio
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

        # Validar nombre repetido
        if Producto.objects.filter(nombre__iexact=nombre).exists():
            messages.error(request, "Ya existe un producto con ese nombre.")
            return render(request, 'administrador/menu/registrar_menu.html', {
                'descripcion': descripcion,
                'precio': precio,
                'tipo': tipo,
            })

        # Crear el producto
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

    if request.method == 'POST':
        nombre = producto.nombre
        producto.delete()
        messages.success(request, f"Producto {nombre} eliminado correctamente.")
        return redirect('listar_menu')

    return render(request, 'administrador/menu/confirmar_eliminar.html', {'producto': producto})

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
    pedidos = Pedido.objects.filter(tipo_pedido='restaurante', mesero=request.user).order_by('-id')
    return render(request, 'mesero/pedidos/listar_pedidos.html', {'pedidos': pedidos})

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
    pedido = get_object_or_404(Pedido, id=pedido_id)

    # Validación: no permitir ver pedido sin productos
    if not pedido.detalles.exists():
        messages.error(request, "Debe agregar al menos un producto antes de finalizar.")
        return redirect('agregar_detalles', pedido_id=pedido.id)

    # Enviar pedido a cocina si está en creación
    if pedido.estado == 'en_creacion':
        pedido.estado = 'en preparacion'
        pedido.save()

        # Notificar a cocineros
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "pedidos_activos",
            {
                "type": "nuevo_pedido",
                "pedido": {
                    "id": pedido.id,
                    "mesa": pedido.mesa.numero if pedido.mesa else None,
                    "mesero": pedido.mesero.nombre,
                    "productos": [
                        {
                            "nombre": d.producto.nombre,
                            "cantidad": d.cantidad,
                            "observacion": d.observacion
                        }
                        for d in pedido.detalles.all()
                    ]
                }
            }
        )

    return render(request, 'mesero/pedidos/ver_pedido.html', {'pedido': pedido})

# Editar pedido
@login_required(login_url='login')
@rol_requerido('mesero')
def editar_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)

    if request.method == 'POST':
        pedido.mesero_id = request.POST.get('mesero')
        pedido.mesa_id = request.POST.get('mesa')

        # Solo cocinero puede modificar estado
        if request.user.rol == 'cocinero':
            pedido.estado = request.POST.get('estado')

        pedido.save()

        return JsonResponse({
            "success": True,
            "mensaje": f"Pedido #{pedido.id} actualizado correctamente."
        })

    meseros = Usuario.objects.filter(rol='mesero')
    mesas = Mesa.objects.all()
    productos = Producto.objects.all()

    return render(request, 'mesero/pedidos/editar_pedido.html', {
        'pedido': pedido,
        'meseros': meseros,
        'mesas': mesas,
        'productos': productos
    })

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
    productos = Producto.objects.all()
    return render(request, 'mesero/pedidos/agregar_detalles.html', {'pedido': pedido, 'productos': productos})

@login_required(login_url='login')
@rol_requerido('mesero')
def agregar_detalle_ajax(request, pedido_id):
    if request.method == 'POST':
        import json
        data = json.loads(request.body)

        producto_id = data.get('producto_id')
        cantidad = int(data.get('cantidad', 1))
        observacion = data.get("observacion", '')

        # Crear o actualizar detalle (SIN RECARGOS)
        detalle, creado = DetallePedido.objects.get_or_create(
            pedido_id=pedido_id,
            producto_id=producto_id,
            defaults={'cantidad': cantidad, 'observacion': observacion}
        )

        if not creado:
            detalle.cantidad += cantidad
            detalle.observacion = observacion
            detalle.save()

        # Actualizar totales
        pedido = get_object_or_404(Pedido, id=pedido_id)
        pedido.calcular_totales()

        tabla_html = render_to_string('mesero/pedidos/tabla_detalles.html', {'pedido': pedido})

        return JsonResponse({'success': True, 'mensaje': 'Producto agregado.', 'tabla': tabla_html})

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

        # SIN RECARGO, NO VALIDACIÓN DE TIPO
        detalle.save()

        tabla_html = render_to_string('mesero/pedidos/tabla_detalles.html', {'pedido': pedido})

        return JsonResponse({'success': True, 'mensaje': 'Detalle actualizado correctamente.', 'tabla': tabla_html})

    return JsonResponse({'success': False, 'mensaje': 'Error al actualizar detalle.'})

@login_required(login_url='login')
@rol_requerido('mesero')
def eliminar_detalle_ajax(request, detalle_id):
    detalle = get_object_or_404(DetallePedido, id=detalle_id)
    pedido = detalle.pedido

    if request.method == 'POST':
        detalle.delete()

        tabla_html = render_to_string('mesero/pedidos/tabla_detalles.html', {'pedido': pedido})

        return JsonResponse({'success': True, 'mensaje': 'Producto eliminado correctamente.', 'tabla': tabla_html})

    return JsonResponse({'success': False, 'mensaje': 'Error al eliminar producto.'})


# ----------------------------
# Cocinero marca pedido como listo
# ----------------------------

def vista_cocina(request):
    pedidos = Pedido.objects.filter(
        estado='en preparacion',
        tipo_pedido='restaurante'
    ).order_by('id')

    meseros = Usuario.objects.filter(rol='mesero')

    return render(request, 'cocinero/pedido.html', {
        'pedidos': pedidos,
        'meseros': meseros
    })



@csrf_protect
def marcar_pedido_listo(request, pedido_id):
    if request.method == "POST":
        pedido = get_object_or_404(Pedido, id=pedido_id)
        pedido.estado = "listo"
        pedido.save()

        # Guardar notificación en BD
        Notificacion.objects.create(
            usuario_destino=pedido.mesero,
            tipo="pedido_listo",
            mensaje=f"El pedido #{pedido.id} está listo.",
            pedido=pedido
        )

        # Emitir WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"notificaciones_{pedido.mesero.id}",
            {
                "type": "enviar_notificacion",
                "tipo": "pedido_listo",
                "mensaje": f"El pedido #{pedido.id} está listo.",
                "mesa": pedido.mesa.numero,
                "pedido": pedido.id
            }
        )

        return JsonResponse({"success": True})
    return JsonResponse({"success": False}, status=400)

def enviar_pedido_cocina(pedido):
    """Enviar el pedido al grupo de cocineros solo cuando esté finalizado."""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "pedidos_activos",
        {
            "type": "nuevo_pedido",
            "pedido": {
                "id": pedido.id,
                "mesa": pedido.mesa.numero if pedido.mesa else None,
                "mesero": pedido.mesero.nombre,
                "productos": [
                    {
                        "nombre": d.producto.nombre,
                        "cantidad": d.cantidad,
                        "observacion": d.observacion
                    }
                    for d in pedido.detalles.all()
                ]
            }
        }
    )

@csrf_exempt
def enviar_mensaje_mesero(request):
    if request.method == "POST":
        import json
        data = json.loads(request.body)

        mesero_id = data.get("mesero_id")
        mensaje = data.get("mensaje")

        mesero = get_object_or_404(Usuario, id=mesero_id)

        Mensaje.objects.create(
            remitente=request.user,
            destinatario=mesero,
            contenido=mensaje
        )

        Notificacion.objects.create(
            usuario_destino=mesero,
            tipo="mensaje",
            mensaje=mensaje
        )

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"notificaciones_{mesero_id}",
            {
                "type": "enviar_notificacion",
                "tipo": "mensaje",
                "mensaje": mensaje,
            }
        )

        return JsonResponse({"success": True})

    return JsonResponse({"success": False}, status=400)


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
            "fecha": n.fecha_hora.strftime("%d/%m/%Y %H:%M")
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


"""
# ----------------------------
# Cajero-Pedidos
# ----------------------------

# Listar pedidos
@login_required(login_url='login')
@rol_requerido('mesero')
def listar_pedidos(request):
    pedidos = Pedido.objects.filter(mesero=request.user).order_by('id')
    return render(request, 'mesero/pedidos/listar_pedidos.html', {'pedidos': pedidos})

# Crear pedido
@login_required(login_url='login')
def crear_pedido(request):
    if request.method == 'POST':
        tipo_pedido = request.POST.get('tipo_pedido')

        # Validaciones según el rol
        if tipo_pedido == 'restaurante' and request.user.rol != 'mesero':
            messages.error(request, "Solo los meseros pueden crear pedidos en restaurante.")
            return redirect('crear_pedido')

        if tipo_pedido == 'domicilio' and request.user.rol != 'cajero':
            messages.error(request, "Solo los cajeros pueden crear pedidos a domicilio.")
            return redirect('crear_pedido')

        # Si pasa las validaciones, se crea normalmente
        mesero_id = request.user.id
        mesa_id = request.POST.get('mesa')

        pedido = Pedido.objects.create(
            mesero_id=mesero_id,
            mesa_id=mesa_id if mesa_id else None,
            tipo_pedido=tipo_pedido,
            estado='en preparacion'
        )

        return redirect('agregar_detalles', pedido_id=pedido.id)

    mesas = Mesa.objects.all()
    return render(request, 'mesero/pedidos/crear_pedido.html', {'mesas': mesas})


# Ver pedido
@login_required(login_url='login')
@rol_requerido('mesero')
def ver_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)

    # Validación: no permitir ver pedido sin productos
    if not pedido.detalles.exists():
        messages.error(request, "Debe agregar al menos un producto antes de finalizar.")
        return redirect('agregar_detalles', pedido_id=pedido.id)

    # 🔹 Enviar pedido a cocina solo si está en creación
    if pedido.estado == 'en_creacion':
        pedido.estado = 'en preparacion'
        pedido.save()

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "pedidos_activos",  # grupo para los cocineros
            {
                "type": "nuevo_pedido",
                "pedido": {
                    "id": pedido.id,
                    "mesa": pedido.mesa.numero if pedido.mesa else None,
                    "mesero": pedido.mesero.nombre,
                    "productos": [
                        {
                            "nombre": d.producto.nombre,
                            "cantidad": d.cantidad,
                            "observacion": d.observacion
                        }
                        for d in pedido.detalles.all()
                    ]
                }
            }
        )

    return render(request, 'mesero/pedidos/ver_pedido.html', {'pedido': pedido})

# Editar pedido
@login_required(login_url='login')
@rol_requerido('mesero')
def editar_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)

    if request.method == 'POST':
        pedido.mesero_id = request.POST.get('mesero')
        pedido.mesa_id = request.POST.get('mesa') if request.POST.get('mesa') else None
        # Solo el cocinero puede cambiar el estado del pedido
        if request.user.rol == 'cocinero':
            pedido.estado = request.POST.get('estado')

        pedido.save()

        return JsonResponse({
            "success": True,
            "mensaje": f"Pedido #{pedido.id} actualizado correctamente."
        })

    meseros = Usuario.objects.filter(rol='mesero')
    mesas = Mesa.objects.all()
    productos = Producto.objects.all()

    return render(request, 'mesero/pedidos/editar_pedido.html', {
        'pedido': pedido,
        'meseros': meseros,
        'mesas': mesas,
        'productos': productos
    })

# Eliminar pedido
@login_required(login_url='login')
@rol_requerido('mesero')
def eliminar_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)

    if pedido.estado == 'listo':
        messages.error(request, f"El pedido #{pedido.id} ya está listo y no puede eliminarse.")
        return redirect('listar_pedidos')

    if request.method == 'POST':
        id_eliminado = pedido.id
        pedido.delete()
        messages.success(request, f"Pedido #{id_eliminado} eliminado.")
        return redirect('listar_pedidos')

    return redirect('listar_pedidos')

# ----------------------------
# Detalles con AJAX
# ----------------------------

# Agregar detalles con AJAX
@login_required(login_url='login')
@rol_requerido('mesero')
def agregar_detalles(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    productos = Producto.objects.all()
    return render(request, 'mesero/pedidos/agregar_detalles.html', {'pedido': pedido, 'productos': productos})

@login_required(login_url='login')
@rol_requerido('mesero')
def agregar_detalle_ajax(request, pedido_id):
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        producto_id = data.get('producto_id')
        cantidad = int(data.get('cantidad', 1))
        observacion = data.get("observacion", '')
        recargo = float(data.get("recargo", 0))

        # Crear o actualizar detalle
        detalle, creado = DetallePedido.objects.get_or_create(
            pedido_id=pedido_id,
            producto_id=producto_id,
            defaults={'cantidad': cantidad, 'observacion': observacion, 'recargo': recargo}
        )

        if not creado:
            detalle.cantidad += cantidad
            detalle.observacion = observacion  # actualizar observación
            detalle.recargo = recargo
            detalle.save()

        # Actualizar totales del pedido
        pedido = get_object_or_404(Pedido, id=pedido_id)
        pedido.calcular_totales()

        # Renderizar tabla actualizada
        tabla_html = render_to_string('mesero/pedidos/tabla_detalles.html', {'pedido': pedido})

        return JsonResponse({
            'success': True,
            'mensaje': f'Producto {detalle.producto.nombre} agregado.',
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
        
        # Datos del SweetAlert
        cantidad = int(data.get("cantidad", detalle.cantidad))
        observacion = data.get("observacion", detalle.observacion)
        
        # Solo actualizar recargo si el pedido es a domicilio
        recargo = detalle.recargo
        if pedido.tipo_pedido == 'domicilio':
            recargo = float(data.get("recargo", detalle.recargo))

        # Guardar cambios
        detalle.cantidad = cantidad
        detalle.observacion = observacion
        detalle.recargo = recargo
        detalle.save()  # ⚡ recalcula subtotal y totales del pedido

        # Renderizar tabla actualizada
        tabla_html = render_to_string('mesero/pedidos/tabla_detalles.html', {'pedido': pedido})

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
        tabla_html = render_to_string('mesero/pedidos/tabla_detalles.html', {'pedido': pedido})
        return JsonResponse({'success': True, 'mensaje': 'Producto eliminado correctamente.', 'tabla': tabla_html})

    return JsonResponse({'success': False, 'mensaje': 'Error al eliminar producto.'})
"""