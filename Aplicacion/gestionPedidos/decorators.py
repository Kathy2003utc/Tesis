from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def rol_requerido(rol):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            if request.user.rol != rol:
                messages.error(request, "No tienes permisos para acceder a esta página.")
                return redirect('login')
                
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
