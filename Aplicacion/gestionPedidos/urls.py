from django.urls import path
from . import views
from django.views.generic import TemplateView

urlpatterns = [
    # Login
    path('login/', views.login_view, name='login'),
    path('iniciar_sesion/', views.iniciar_sesion, name='iniciar_sesion'),
    path('logout/', views.cerrar_sesion, name='logout'),
    path('cambiar_password/', views.cambiar_password_primera_vez, name='cambiar_password_primera_vez'),

    # Dashboards por rol
    path('administrador/dashboard/', views.dashboard_admin, name='dashboard_admin'),
    path('mesero/dashboard/', views.dashboard_mesero, name='dashboard_mesero'),
    path('cocinero/dashboard/', views.dashboard_cocinero, name='dashboard_cocinero'),
    path('cajero/dashboard/', views.dashboard_cajero, name='dashboard_cajero'),
    
    #Admin-perfil
    path('perfil/', views.perfil_admin, name='perfil_admin'),
    path('perfil/administrador/editar/', views.editar_perfil_admin, name='editar_perfil_admin'),

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

    # Admin - Resportes
    path('reportes/', views.reportes_general, name='reportes_general'),
    path('reportes/restaurante/',views.reporte_pagos_restaurante,name='reporte_pagos_restaurante'),
    path('reportes/domicilio/', views.reporte_pagos_domicilio, name='reporte_pagos_domicilio'),
    path('reportes/pedidos-restaurante/', views.reporte_pedidos_restaurante, name='reporte_pedidos_restaurante'),
    path('reportes/pedidos-domicilio/', views.reporte_pedidos_domicilio, name='reporte_pedidos_domicilio'),

    path('reportes/pedidos/restaurante/pdf/', views.exportar_pedidos_restaurante_pdf, name='exportar_pedidos_restaurante_pdf'),
    path('reportes/pagos/restaurante/pdf/', views.exportar_cobros_restaurante_pdf,name='exportar_cobros_restaurante_pdf'),
    path('reportes/pagos/domicilio/pdf/', views.exportar_cobros_domicilio_pdf, name='exportar_cobros_domicilio_pdf'),
    path('reportes/pedidos/domicilio/pdf/', views.exportar_pedidos_domicilio_pdf, name='exportar_pedidos_domicilio_pdf'),
    
    path('reportes/pedidos/domicilio/excel/', views.exportar_pedidos_domicilio_excel, name='exportar_pedidos_domicilio_excel'),
    path('reportes/pedidos/restaurante/excel/', views.exportar_pedidos_restaurante_excel, name='exportar_pedidos_restaurante_excel'),
    path('reportes/pagos/restaurante/excel/',views.exportar_cobros_restaurante_excel,name='exportar_cobros_restaurante_excel'),
    path('reportes/pagos/domicilio/excel/',views.exportar_cobros_domicilio_excel,name='exportar_cobros_domicilio_excel'),

    # Reporte Unificado
    path('reportes/unificado/', views.reporte_unificado, name='reporte_unificado'),
    path('reportes/unificado/pdf/',views.exportar_unificado_pdf,name='exportar_unificado_pdf'),
    path( 'reportes/unificado/excel/', views.exportar_unificado_excel, name='exportar_unificado_excel'),

    # Mesero - Pedidos
    path('mesero/api/pedidos/estados/', views.api_estados_pedidos, name='api_estados_pedidos'),
    path('pedidos/', views.listar_pedidos, name='listar_pedidos'),
    path('pedidos/crear/', views.crear_pedido, name='crear_pedido'),
    path('pedidos/agregar-detalles/<int:pedido_id>/', views.agregar_detalles, name='agregar_detalles'),
    path('pedidos/ver/<int:pedido_id>/', views.ver_pedido, name='ver_pedido'),
    path('pedidos/editar/<int:pedido_id>/', views.editar_pedido, name='editar_pedido'),
    path('pedidos/eliminar/<int:pedido_id>/', views.eliminar_pedido, name='eliminar_pedido'),
    path('pedidos/finalizar/<int:pedido_id>/', views.finalizar_pedido, name='finalizar_pedido'),

    # DetallePedido AJAX
    path('pedidos/detalle/agregar/ajax/<int:pedido_id>/', views.agregar_detalle_ajax, name='agregar_detalle_ajax'),
    path('pedidos/detalle/editar/ajax/<int:detalle_id>/', views.editar_detalle_ajax, name='editar_detalle_ajax'),
    path('pedidos/detalle/eliminar/ajax/<int:detalle_id>/', views.eliminar_detalle_ajax, name='eliminar_detalle_ajax'),

    #Cocinero pedido
    path('cocinero/pedidos/', views.vista_cocina, name='vista_cocina'),
    path('pedido/<int:pedido_id>/listo/', views.marcar_pedido_listo, name='marcar_pedido_listo'),
    path("cocina/enviar-mensaje/", views.enviar_mensaje_mesero, name="enviar_mensaje_mesero"),

    #notificaion al mesero de listo
    path("notificaciones/", views.notificaciones_mesero, name="notificaciones_mesero"),
    path("notificaciones/obtener/", views.obtener_notificaciones, name="obtener_notificaciones"),
    path("notificaciones/eliminar/<int:notif_id>/", views.eliminar_notificacion, name="eliminar_notificacion"),

    # PERFIL - MESERO
    path("mesero/perfil/", views.perfil_mesero, name="perfil_mesero"),
    path("mesero/perfil/editar/", views.editar_perfil_mesero, name="editar_perfil_mesero"),

    # CAJERO - PEDIDOS A DOMICILIO
    path('cajero/api/pedidos/estados/', views.cajero_api_estados_pedidos, name='cajero_api_estados_pedidos'),
    path('cajero/pedidos/', views.cajero_listar_pedidos, name='cajero_listar_pedidos'),
    path('cajero/pedidos/crear/', views.cajero_crear_pedido, name='cajero_crear_pedido'),
    path('cajero/pedidos/<int:pedido_id>/agregar/', views.cajero_agregar_detalles, name='cajero_agregar_detalles'),
    path('cajero/pedidos/<int:pedido_id>/ver/', views.cajero_ver_pedido, name='cajero_ver_pedido'),
    path('cajero/pedidos/<int:pedido_id>/eliminar/', views.cajero_eliminar_pedido, name='cajero_eliminar_pedido'),
    path('cajero/pedidos/<int:pedido_id>/editar/', views.cajero_editar_pedido, name='cajero_editar_pedido'),
    path('cajero/pedidos/<int:pedido_id>/finalizar/', views.cajero_finalizar_pedido, name='cajero_finalizar_pedido'),
    path('cajero/pedidos/<int:pedido_id>/cancelar/', views.cajero_cancelar_pedido, name='cajero_cancelar_pedido'),

    # AJAX
    path('cajero/pedidos/<int:pedido_id>/detalle/agregar/', views.cajero_agregar_detalle_ajax, name='cajero_agregar_detalle_ajax'),
    path('cajero/detalle/<int:detalle_id>/editar/', views.cajero_editar_detalle_ajax, name='cajero_editar_detalle_ajax'),
    path('cajero/detalle/<int:detalle_id>/eliminar/', views.cajero_eliminar_detalle_ajax, name='cajero_eliminar_detalle_ajax'),

    #notificaciones al cajero
    path("cajero/notificaciones/", views.cajero_notificaciones, name="cajero_notificaciones"),

    # Cajero - cobros restaurante
    path('cajero/restaurante/cobros/', views.cajero_restaurante_cobros, name='cajero_restaurante_cobros'),
    path('cajero/restaurante/<int:pedido_id>/pagar/', views.cajero_restaurante_pagar, name='cajero_restaurante_pagar'),
    # Cajero - cobros domicilio
    path('cajero/domicilio/cobros/',views.cajero_domicilio_cobros,name='cajero_domicilio_cobros'),
    path('cajero/domicilio/<int:pedido_id>/pagar/',views.cajero_domicilio_pagar,name='cajero_domicilio_pagar'),
    path("cajero/tabla-pedidos-pagados-domicilio/", views.tabla_pedidos_pagados_domicilio, name="tabla_pedidos_pagados_domicilio"),

    #Cajero - comprobante
    path("comprobante/<int:comp_id>/", views.ver_comprobante, name="ver_comprobante"),

    #Cajero - reporte
    path('cajero/reporte/unificado/',views.cajero_reporte_unificado,name='cajero_reporte_unificado'),
    path('cajero/reporte/unificado/pdf/',views.cajero_exportar_unificado_pdf,name='cajero_exportar_unificado_pdf'),
    path('cajero/reporte/unificado/excel/',views.cajero_exportar_unificado_excel,name='cajero_exportar_unificado_excel'),

    #Cajero - Perfil
    path('cajero/perfil/', views.perfil_cajero, name='perfil_cajero'),
    path('cajero/perfil/editar/', views.editar_perfil_cajero, name='editar_perfil_cajero'),

    #offline
    path("offline/", TemplateView.as_view(template_name="offline.html"), name="offline"),

]
