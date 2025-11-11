from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password
from .models import Usuario, Mesa, Pedido, DetallePedido, Producto
from django.contrib.auth.hashers import make_password
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.db.models import Sum, F



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
        correo = request.POST.get('username')
        password = request.POST.get('password')

        # Autenticar usando el modelo personalizado
        usuario = authenticate(request, username=correo, password=password)

        if usuario is not None:
            # Iniciar sesión
            auth_login(request, usuario)

            # Guardar datos en sesión
            request.session['usuario_id'] = usuario.id
            request.session['usuario_rol'] = usuario.rol
            request.session['usuario_nombre'] = f"{usuario.nombre} {usuario.apellido}"

            # Redirección según rol
            if usuario.rol == 'admin':
                return redirect('dashboard_admin')
            elif usuario.rol == 'mesero':
                return redirect('dashboard_mesero')
            elif usuario.rol == 'cocinero':
                return redirect('dashboard_cocinero')
            elif usuario.rol == 'cajero':
                return redirect('dashboard_cajero')
            elif usuario.rol == 'cliente':
                return redirect('dashboard_cliente')
            else:
                messages.error(request, "Rol desconocido.")
                return render(request, 'login/login.html')

        else:
            messages.error(request, "Correo o contraseña incorrectos.")
            return render(request, 'login/login.html')

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
# Formulario de registro de cliente
# ----------------------------
def registro(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        apellido = request.POST.get('apellido')
        telefono = request.POST.get('telefono')
        direccion = request.POST.get('direccion')
        correo = request.POST.get('correo')
        password = request.POST.get('password')

        if Usuario.objects.filter(correo=correo).exists():
            messages.error(request, "El correo ya está registrado.")
            return render(request, 'registro.html')

        # Crear usuario con rol cliente
        usuario = Usuario.objects.create(
            nombre=nombre,
            apellido=apellido,
            telefono=telefono,
            direccion=direccion,
            correo=correo,
            rol='cliente',
            username=correo,  # username obligatorio en AbstractUser
            password=make_password(password)  # cifrar contraseña
        )

        messages.success(request, "Registro exitoso. Ahora puedes iniciar sesión.")
        return redirect('login')

    return render(request, 'login/registro.html')


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


@login_required(login_url='login')
def dashboard_cliente(request):
    if request.user.rol != 'cliente':
        messages.error(request, "No tienes permisos para acceder a esta página.")
        return redirect('login')
    return render(request, 'cliente/dashboard.html')

# ----------------------------
# Admin-Gestion de trabajadores
# ----------------------------

def listar_trabajadores(request):
    # Filtrar todos los usuarios que no sean clientes ni admin
    trabajadores = Usuario.objects.exclude(rol__in=['cliente', 'admin'])
    return render(request, 'administrador/trabajadores/trabajadores.html', {'trabajadores': trabajadores})

def crear_trabajador(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        apellido = request.POST.get('apellido')
        correo = request.POST.get('correo')
        telefono = request.POST.get('telefono')
        direccion = request.POST.get('direccion')
        rol = request.POST.get('rol')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')

        if password != password2:
            messages.error(request, "Las contraseñas no coinciden.")
            return render(request, 'administrador/trabajadores/crear_trabajador.html')

        if Usuario.objects.filter(correo=correo).exists():
            messages.error(request, "Ya existe un usuario con este correo.")
            return render(request, 'administrador/trabajadores/crear_trabajador.html')

        # Crear usuario
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

        messages.success(request, f"Trabajador {trabajador.nombre} {trabajador.apellido} creado con éxito.")
        return redirect('listar_trabajadores')

    return render(request, 'administrador/trabajadores/crear_trabajador.html')

def editar_trabajador(request, trabajador_id):
    trabajador = get_object_or_404(Usuario, id=trabajador_id)

    if request.method == 'POST':
        trabajador.nombre = request.POST.get('nombre')
        trabajador.apellido = request.POST.get('apellido')
        trabajador.correo = request.POST.get('correo')
        trabajador.telefono = request.POST.get('telefono')
        trabajador.direccion = request.POST.get('direccion')
        trabajador.rol = request.POST.get('rol')

        password = request.POST.get('password')
        password2 = request.POST.get('password2')

        if password or password2:
            if password != password2:
                messages.error(request, "Las contraseñas no coinciden.")
                return render(request, 'administrador/trabajadores/editar_trabajador.html', {'trabajador': trabajador})
            trabajador.set_password(password)


        # Verificar que el correo no exista en otro usuario
        if Usuario.objects.exclude(id=trabajador.id).filter(correo=trabajador.correo).exists():
            messages.error(request, "Ya existe un usuario con este correo.")
            return render(request, 'administrador/trabajadores/editar_trabajador.html', {'trabajador': trabajador})

        trabajador.save()
        messages.success(request, f"Trabajador {trabajador.nombre} actualizado con éxito.")
        return redirect('listar_trabajadores')

    return render(request, 'administrador/trabajadores/editar_trabajador.html', {'trabajador': trabajador})

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
from .models import Mesa
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404

# Listar mesas
def listar_mesas(request):
    mesas = Mesa.objects.all().order_by('numero')
    return render(request, 'administrador/mesas/listar_mesas.html', {'mesas': mesas})


# Registrar mesa
def registrar_mesa(request):
    if request.method == 'POST':
        numero = request.POST.get('numero')
        capacidad = request.POST.get('capacidad')
        estado = request.POST.get('estado')

        # Validar que el número sea único
        if Mesa.objects.filter(numero=numero).exists():
            messages.error(request, "Ya existe una mesa con ese número.")
            return render(request, 'administrador/mesas/registrar_mesa.html')

        # Crear mesa
        Mesa.objects.create(
            numero=numero,
            capacidad=capacidad,
            estado=estado
        )
        messages.success(request, f"Mesa {numero} registrada correctamente.")
        return redirect('listar_mesas')

    return render(request, 'administrador/mesas/registrar_mesa.html')


# Editar mesa
def editar_mesa(request, mesa_id):
    mesa = get_object_or_404(Mesa, id=mesa_id)

    if request.method == 'POST':
        numero = request.POST.get('numero')
        capacidad = request.POST.get('capacidad')
        estado = request.POST.get('estado')

        # Validar número de mesa repetido
        if Mesa.objects.exclude(id=mesa.id).filter(numero=numero).exists():
            messages.error(request, "Ya existe otra mesa con ese número.")
            return render(request, 'administrador/mesas/editar_mesa.html', {'mesa': mesa})

        # Actualizar datos
        mesa.numero = numero
        mesa.capacidad = capacidad
        mesa.estado = estado
        mesa.save()

        messages.success(request, f"Mesa {numero} actualizada correctamente.")
        return redirect('listar_mesas')

    return render(request, 'administrador/mesas/editar_mesa.html', {'mesa': mesa})


# Eliminar mesa
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
def listar_menu(request):
    productos = Producto.objects.all().order_by('nombre')
    return render(request, 'administrador/menu/listar_menu.html', {'productos': productos})


# Registrar producto
def registrar_menu(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        descripcion = request.POST.get('descripcion')
        precio = request.POST.get('precio')
        tipo = request.POST.get('tipo')
        imagen = request.FILES.get('imagen')

        # Validar que el nombre no esté repetido
        if Producto.objects.filter(nombre=nombre).exists():
            messages.error(request, "Ya existe un producto con ese nombre.")
            return render(request, 'administrador/menu/registrar_menu.html')

        # Crear el producto
        Producto.objects.create(
            nombre=nombre,
            descripcion=descripcion,
            precio=precio,
            tipo=tipo,
            imagen=imagen
        )

        messages.success(request, f"Producto '{nombre}' registrado correctamente.")
        return redirect('listar_menu')

    return render(request, 'administrador/menu/registrar_menu.html')


# Editar producto
def editar_menu(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        descripcion = request.POST.get('descripcion')
        precio = request.POST.get('precio')
        tipo = request.POST.get('tipo')

        # Validar nombre repetido
        if Producto.objects.exclude(id=producto.id).filter(nombre=nombre).exists():
            messages.error(request, "Ya existe otro producto con ese nombre.")
            return render(request, 'administrador/menu/editar_menu.html', {'producto': producto})

        # Actualizar info
        producto.nombre = nombre
        producto.descripcion = descripcion
        producto.precio = precio
        producto.tipo = tipo

        # Validar si se subió una nueva imagen
        if 'imagen' in request.FILES:
            producto.imagen = request.FILES['imagen']

        producto.save()

        messages.success(request, f"Producto '{nombre}' actualizado correctamente.")
        return redirect('listar_menu')

    return render(request, 'administrador/menu/editar_menu.html', {'producto': producto})


# Eliminar producto
def eliminar_menu(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)

    if request.method == 'POST':
        nombre = producto.nombre
        producto.delete()
        messages.success(request, f"Producto '{nombre}' eliminado correctamente.")
        return redirect('listar_menu')

    return render(request, 'administrador/menu/confirmar_eliminar.html', {'producto': producto})

# ----------------------------
# Pedidos
# ----------------------------

# Listar pedidos
def listar_pedidos(request):
    pedidos = Pedido.objects.all().order_by('id')
    return render(request, 'mesero/pedidos/listar_pedidos.html', {'pedidos': pedidos})

# Crear pedido
def crear_pedido(request):
    if request.method == 'POST':
        mesero_id = request.POST.get('mesero')
        mesa_id = request.POST.get('mesa')
        tipo_pedido = request.POST.get('tipo_pedido')

        pedido = Pedido.objects.create(
            mesero_id=mesero_id,
            mesa_id=mesa_id if mesa_id else None,
            tipo_pedido=tipo_pedido
        )
        return redirect('agregar_detalles', pedido_id=pedido.id)

    meseros = Usuario.objects.filter(rol='mesero')
    mesas = Mesa.objects.all()
    return render(request, 'mesero/pedidos/crear_pedido.html', {'meseros': meseros, 'mesas': mesas})

# Ver pedido
def ver_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)

    # Validación: no permitir ver pedido sin productos
    if not pedido.detalles.exists():
        messages.error(request, "Debe agregar al menos un producto antes de finalizar.")
        return redirect('agregar_detalles', pedido_id=pedido.id)

    return render(request, 'mesero/pedidos/ver_pedido.html', {'pedido': pedido})

# Editar pedido
def editar_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)

    if request.method == 'POST':
        pedido.mesero_id = request.POST.get('mesero')
        pedido.mesa_id = request.POST.get('mesa') if request.POST.get('mesa') else None
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
def eliminar_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)

    if request.method == 'POST':
        id_eliminado = pedido.id
        pedido.delete()
        messages.success(request, f"Pedido #{id_eliminado} eliminado.")
        return redirect('listar_pedidos')

    return redirect('listar_pedidos')  # No hace falta mostrar nada

# ----------------------------
# Detalles con AJAX
# ----------------------------

# Agregar detalles con AJAX
def agregar_detalles(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    productos = Producto.objects.all()
    return render(request, 'mesero/pedidos/agregar_detalles.html', {'pedido': pedido, 'productos': productos})

def agregar_detalle_ajax(request, pedido_id):
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        producto_id = data.get('producto_id')
        cantidad = int(data.get('cantidad', 1))
        observacion = data.get("observacion", '')
        recargo = float(data.get("recargo", 0))  # Recargo por unidad del producto

        # Crear o actualizar detalle
        detalle, creado = DetallePedido.objects.get_or_create(
            pedido_id=pedido_id,
            producto_id=producto_id,
            defaults={'cantidad': cantidad, 'observacion': observacion, 'recargo': recargo}
        )
        if not creado:
            detalle.cantidad += cantidad
            detalle.recargo = recargo  # ⚡ siempre actualizar recargo por unidad
            detalle.save()

        # Actualizar totales del pedido
        pedido = get_object_or_404(Pedido, id=pedido_id)
        pedido.calcular_totales()  # ⚡ suma subtotal + recargo_total + recargo_domicilio

        # Renderizar tabla
        tabla_html = render_to_string('mesero/pedidos/tabla_detalles.html', {'pedido': pedido})

        return JsonResponse({
            'success': True,
            'mensaje': f'Producto {detalle.producto.nombre} agregado.',
            'tabla': tabla_html
        })

    return JsonResponse({'success': False, 'mensaje': 'Error al agregar producto'})

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

def eliminar_detalle_ajax(request, detalle_id):
    detalle = get_object_or_404(DetallePedido, id=detalle_id)
    pedido = detalle.pedido

    if request.method == 'POST':
        detalle.delete()
        tabla_html = render_to_string('mesero/pedidos/tabla_detalles.html', {'pedido': pedido})
        return JsonResponse({'success': True, 'mensaje': 'Producto eliminado correctamente.', 'tabla': tabla_html})

    return JsonResponse({'success': False, 'mensaje': 'Error al eliminar producto.'})