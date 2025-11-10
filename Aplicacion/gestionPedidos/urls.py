from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('iniciar_sesion/', views.iniciar_sesion, name='iniciar_sesion'),
    path('logout/', views.cerrar_sesion, name='logout'),
    path('registro/', views.registro, name='registro'),

    # Dashboards por rol
    path('administrador/dashboard/', views.dashboard_admin, name='dashboard_admin'),
    path('mesero/dashboard/', views.dashboard_mesero, name='dashboard_mesero'),
    path('cocinero/dashboard/', views.dashboard_cocinero, name='dashboard_cocinero'),
    path('cajero/dashboard/', views.dashboard_cajero, name='dashboard_cajero'),
    path('cliente/dashboard/', views.dashboard_cliente, name='dashboard_cliente'),

    # Admin-gestion de trabajadores
    path('trabajadores/', views.listar_trabajadores, name='listar_trabajadores'),
    path('trabajadores/crear/', views.crear_trabajador, name='crear_trabajador'),
    path('trabajadores/editar/<int:trabajador_id>/', views.editar_trabajador, name='editar_trabajador'),
    path('trabajadores/eliminar/<int:trabajador_id>/', views.eliminar_trabajador, name='eliminar_trabajador'),

    # Admin-gestion de mesas
    path('mesas/', views.listar_mesas, name='listar_mesas'),
    path('mesas/registrar/', views.registrar_mesa, name='registrar_mesa'),
    path('mesas/editar/<int:mesa_id>/', views.editar_mesa, name='editar_mesa'),
    path('mesas/eliminar/<int:mesa_id>/', views.eliminar_mesa, name='eliminar_mesa'),

    # Admin - Gestión de Menú
    path('menu/', views.listar_menu, name='listar_menu'),
    path('menu/registrar/', views.registrar_menu, name='registrar_menu'),
    path('menu/editar/<int:producto_id>/', views.editar_menu, name='editar_menu'),
    path('menu/eliminar/<int:producto_id>/', views.eliminar_menu, name='eliminar_menu'),

    # Pedidos
    path('pedidos/', views.listar_pedidos, name='listar_pedidos'),
    path('pedidos/crear/', views.crear_pedido, name='crear_pedido'),
    path('pedidos/agregar-detalles/<int:pedido_id>/', views.agregar_detalles, name='agregar_detalles'),
    path('pedidos/ver/<int:pedido_id>/', views.ver_pedido, name='ver_pedido'),
    path('pedidos/editar/<int:pedido_id>/', views.editar_pedido, name='editar_pedido'),
    path('pedidos/eliminar/<int:pedido_id>/', views.eliminar_pedido, name='eliminar_pedido'),

    # DetallePedido AJAX
    path('pedidos/detalle/agregar/ajax/<int:pedido_id>/', views.agregar_detalle_ajax, name='agregar_detalle_ajax'),
    path('pedidos/detalle/editar/ajax/<int:detalle_id>/', views.editar_detalle_ajax, name='editar_detalle_ajax'),
    path('pedidos/detalle/eliminar/ajax/<int:detalle_id>/', views.eliminar_detalle_ajax, name='eliminar_detalle_ajax'),

]
