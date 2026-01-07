from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def rol_requerido(*roles):   # 👈 ahora acepta 1, 2, 3... roles
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # No autenticado
            if not request.user.is_authenticated:
                return redirect('login')

            # Rol no permitido
            if request.user.rol not in roles:
                messages.error(request, "No tienes permisos para acceder a esta página.")
                return redirect('login')

            # Todo bien
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
