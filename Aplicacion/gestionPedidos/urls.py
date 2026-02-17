from django.urls import path
from . import views
from django.views.generic import TemplateView

urlpatterns = [
    # Login
    path('login/', views.login_view, name='login'),
    path('iniciar_sesion/', views.iniciar_sesion, name='iniciar_sesion'),
    path('logout/', views.cerrar_sesion, name='logout'),
    path('cambiar_password/', views.cambiar_password_primera_vez, name='cambiar_password_primera_vez'),
    
    #Login - cliente
    path('registro/cliente/', views.registro_cliente, name='registro_cliente'),
    path('cliente/activar/<uidb64>/<token>/',views.activar_cuenta_cliente,name='activar_cuenta_cliente'),
    path('ajax/verificar-correo/',views.verificar_correo_ajax,name='verificar_correo_ajax'),
    path('cliente/recuperar-password/',views.cliente_recuperar_password,name='cliente_recuperar_password'),
    path('cliente/restablecer-password/<uidb64>/<token>/',views.cliente_restablecer_password,name='cliente_restablecer_password'),


    # Dashboards por rol
    path('administrador/dashboard/', views.dashboard_admin, name='dashboard_admin'),
    path('mesero/dashboard/', views.dashboard_mesero, name='dashboard_mesero'),
    path('cocinero/dashboard/', views.dashboard_cocinero, name='dashboard_cocinero'),
    path('cajero/dashboard/', views.dashboard_cajero, name='dashboard_cajero'),
    path('dashboard/cliente/', views.dashboard_cliente, name='dashboard_cliente'),
    
    #Admin-perfil
    path('perfil/', views.perfil_admin, name='perfil_admin'),
    path('perfil/administrador/editar/', views.editar_perfil_admin, name='editar_perfil_admin'),

    # Admin-gestion de trabajadores
    path('trabajadores/', views.listar_trabajadores, name='listar_trabajadores'),
    path('trabajadores/crear/', views.crear_trabajador, name='crear_trabajador'),
    path('trabajadores/editar/<int:trabajador_id>/', views.editar_trabajador, name='editar_trabajador'),
    path('trabajadores/eliminar/<int:trabajador_id>/', views.eliminar_trabajador, name='eliminar_trabajador'),
    path('trabajadores/activar/<int:trabajador_id>/', views.activar_trabajador, name='activar_trabajador'),

    #Admin-gestion horario
    path('horarios/', views.lista_horarios, name='lista_horarios'),          
    path('horarios/crear/', views.crear_horario, name='crear_horario'),      
    path('horarios/editar/<int:id>/', views.editar_horario, name='editar_horario'),  
    path('horarios/eliminar/<int:id>/', views.eliminar_horario, name='eliminar_horario'),
    
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
    path('menu/activar/<int:producto_id>/', views.activar_menu, name='activar_menu'),

    # Admin - Clientes registrados
    path('administrador/clientes/',views.admin_listar_clientes,name='admin_listar_clientes'),

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
    path('mesero/pedidos/cancelar/<int:pedido_id>/', views.mesero_cancelar_pedido, name='mesero_cancelar_pedido'),
    path("mesero/pedidos/historial/",views.mesero_historial_pedidos,name="mesero_historial_pedidos"),

    # DetallePedido AJAX
    path('pedidos/detalle/agregar/ajax/<int:pedido_id>/', views.agregar_detalle_ajax, name='agregar_detalle_ajax'),
    path('pedidos/detalle/editar/ajax/<int:detalle_id>/', views.editar_detalle_ajax, name='editar_detalle_ajax'),
    path('pedidos/detalle/eliminar/ajax/<int:detalle_id>/', views.eliminar_detalle_ajax, name='eliminar_detalle_ajax'),

    #Cocinero pedido
    path('cocinero/pedidos/', views.vista_cocina, name='vista_cocina'),
    path('pedido/<int:pedido_id>/listo/', views.marcar_pedido_listo, name='marcar_pedido_listo'),
    path("pedido/<int:pedido_id>/preparacion/", views.marcar_pedido_preparacion, name="pedido_preparacion"),
    path("cocina/enviar-mensaje/", views.enviar_mensaje_mesero, name="enviar_mensaje_mesero"),

    path("cocina/no-hay-producto/", views.avisar_no_hay_producto, name="avisar_no_hay_producto"),

    path("cocinero/perfil/", views.perfil_cocinero, name="perfil_cocinero"),
    path("cocinero/perfil/editar/", views.editar_perfil_cocinero, name="editar_perfil_cocinero"),

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
    path('pedidos/historial/',views.cajero_historial_pedidos,name='cajero_historial_pedidos'),

    # AJAX
    path('cajero/pedidos/<int:pedido_id>/detalle/agregar/', views.cajero_agregar_detalle_ajax, name='cajero_agregar_detalle_ajax'),
    path('cajero/detalle/<int:detalle_id>/editar/', views.cajero_editar_detalle_ajax, name='cajero_editar_detalle_ajax'),
    path('cajero/detalle/<int:detalle_id>/eliminar/', views.cajero_eliminar_detalle_ajax, name='cajero_eliminar_detalle_ajax'),

    #Cajero - cliente pedidos
    path('pedidos-clientes-domicilio/',views.cajero_pedidos_clientes_domicilio,name='cajero_pedidos_clientes_domicilio'),
    path('cajero/pedido-cliente/<int:pedido_id>/aceptar/',views.cajero_aceptar_pedido_cliente,name='cajero_aceptar_pedido_cliente'),
    path('cajero/pedido-cliente/<int:pedido_id>/rechazar/',views.cajero_rechazar_pedido_cliente,name='cajero_rechazar_pedido_cliente'),
    path('cajero/pedidos/historial/',views.cajero_pedidos_historial_cliente,name='cajero_pedidos_historial_cliente'),

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

    # PEDIDOS - CLIENTE
    path('cliente/pedidos/',views.cliente_listar_pedidos,name='cliente_listar_pedidos'),
    path('cliente/pedido/crear/',views.cliente_crear_pedido,name='cliente_crear_pedido'),
    path('cliente/pedido/<int:pedido_id>/eliminar/',views.cliente_eliminar_pedido,name='cliente_eliminar_pedido'),
    path('cliente/pedidos/editar/<int:pedido_id>/',  views.cliente_editar_pedido, name='cliente_editar_pedido'),
    path('cliente/pedido/<int:pedido_id>/editar-pago/', views.cliente_editar_pago, name='cliente_editar_pago'),
    path('cliente/pedido/<int:pedido_id>/detalles/',views.cliente_agregar_detalles,name='cliente_agregar_detalles'),
    path('cliente/pedidos/ver/<int:pedido_id>/', views.cliente_ver_pedido, name='cliente_ver_pedido'),
    path('cliente/pedidos/historial/',views.cliente_historial_pedidos,name='cliente_historial_pedidos'),
    
    #AJAX
    path('cliente/pedido/<int:pedido_id>/detalle/agregar/', views.cliente_agregar_detalle_ajax, name='cliente_agregar_detalle_ajax'),
    path('cliente/detalle/<int:detalle_id>/editar/',views.cliente_editar_detalle_ajax,name='cliente_editar_detalle_ajax'),
    path('cliente/detalle/<int:detalle_id>/eliminar/',views.cliente_eliminar_detalle_ajax,name='cliente_eliminar_detalle_ajax'),

    # CLIENTE - PAGO PEDIDO
    path('cliente/pedido/<int:pedido_id>/pago/',views.cliente_pago_pedido,name='cliente_pago_pedido'),

    #CLIENTE - ENVIA PEDIDO AL CAJERO
    path('cliente/pedido/<int:pedido_id>/enviar/',views.cliente_enviar_pedido,name='cliente_enviar_pedido'),

    # CLIENTE - PERFIL
    path('cliente/perfil/',views.cliente_ver_perfil,name='cliente_ver_perfil'),
    path('cliente/perfil/editar/',views.cliente_editar_perfil,name='cliente_editar_perfil'),
    path('cliente/desactivar-cuenta/',views.cliente_desactivar_cuenta,name='cliente_desactivar_cuenta'),
    path('cliente/reactivar/',views.cliente_reactivar_cuenta,name='cliente_reactivar_cuenta'),
    path('cliente/reactivar/<uidb64>/<token>/',views.cliente_confirmar_reactivacion,name='cliente_confirmar_reactivacion'),




    

]

