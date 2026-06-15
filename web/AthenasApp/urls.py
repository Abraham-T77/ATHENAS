# AthenasApp/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

# CBVs/funciones para Clientes, Proveedores y Usuarios
from .views import (
    # Usuarios
    UsuarioListView, UsuarioUpdateView, usuario_toggle_activo,
    # Clientes
    ClienteListView, ClienteCreateView, ClienteUpdateView, cliente_toggle_activo,
    # Proveedores
    ProveedorListView, ProveedorCreateView, ProveedorUpdateView, proveedor_toggle_activo,
    # Productos (funciones)
    productos_lista, productos_crear, productos_editar, productos_toggle_activo,
)

# =========================
# COMPRAS (ÉPIC 6)
# =========================
from .views_compras import (
    compras_lista,            # listado con paginación
    compra_crear,             # crear con form + formset
    compras_detalle,          # detalle (contexto: obj, detalle, comprobantes)
    compra_editar,            # editar con form + formset
    compra_confirmar,         # confirma y mueve stock
    compra_anular,            # anula borradores
    compra_adjuntar_comprobante,  # upload de comprobante
)

from . import views_ventas
from AthenasApp import views_caja
from AthenasApp import views_movimientos

# =========================
# NUEVOS MÓDULOS (PR-4)
# =========================
from AthenasApp import views_cuentas
from AthenasApp import views_alertas
from AthenasApp import views_reportes
from AthenasApp import views_bitacora


urlpatterns = [
    # =========================
    # Autenticación
    # =========================
    path('accounts/login/', auth_views.LoginView.as_view(template_name='athenas/login.html'), name='login'),
    path('accounts/logout/', views.salir, name='logout'),

    # =========================
    # Negocio
    # =========================
    path('negocio/seleccionar/', views.seleccionar_negocio, name='seleccionar_negocio'),

    # =========================
    # Panel principal
    # =========================
    path('', views.dashboard, name='dashboard'),

    # =========================
    # Módulos base
    # =========================
    # Productos (Épic 3)
    path('productos/',                     productos_lista,         name='productos_lista'),
    path('productos/nuevo/',               productos_crear,         name='productos_crear'),
    path('productos/<int:pk>/editar/',     productos_editar,        name='productos_editar'),
    path('productos/<int:pk>/toggle/',     productos_toggle_activo, name='productos_toggle_activo'),

    # =========================
    # Catálogos (Categoría/Marca/Unidad)
    # =========================
    path('catalogos/categorias/nueva/', views.categoria_nueva, name='categoria_nueva'),
    path('catalogos/marcas/nueva/',     views.marca_nueva,     name='marca_nueva'),
    path('catalogos/unidades/nueva/',   views.unidad_nueva,    name='unidad_nueva'),


    # =========================
    # Seguridad (solo admin)
    # =========================
    path('seguridad/usuarios/nuevo/', views.crear_usuario, name='crear_usuario'),

    # --- Gestión de usuarios ---
    path('seguridad/usuarios/',                 UsuarioListView.as_view(),   name='usuarios_lista'),
    path('seguridad/usuarios/<int:pk>/editar/', UsuarioUpdateView.as_view(), name='usuarios_editar'),
    path('seguridad/usuarios/<int:pk>/toggle/', usuario_toggle_activo,       name='usuarios_toggle'),

    # =========================
    # CLIENTES
    # =========================
    path('clientes/',                 ClienteListView.as_view(),   name='clientes_lista'),
    path('clientes/nuevo/',           ClienteCreateView.as_view(), name='clientes_nuevo'),
    path('clientes/<int:pk>/editar/', ClienteUpdateView.as_view(), name='clientes_editar'),
    path('clientes/<int:pk>/toggle/', cliente_toggle_activo,       name='clientes_toggle'),

    # =========================
    # PROVEEDORES
    # =========================
    path('proveedores/',                 ProveedorListView.as_view(),   name='proveedores_lista'),
    path('proveedores/nuevo/',           ProveedorCreateView.as_view(), name='proveedores_nuevo'),
    path('proveedores/<int:pk>/editar/', ProveedorUpdateView.as_view(), name='proveedores_editar'),
    path('proveedores/<int:pk>/toggle/', proveedor_toggle_activo,       name='proveedores_toggle'),

    # =========================
    # COMPRAS (ÉPIC 6)
    # =========================
    path('compras/',                      compras_lista,                 name='compras_lista'),
    path('compras/nueva/',                compra_crear,                  name='compras_crear'),
    path('compras/<int:pk>/',             compras_detalle,               name='compras_detalle'),
    path('compras/<int:pk>/editar/',      compra_editar,                 name='compras_editar'),
    path('compras/<int:pk>/confirmar/',   compra_confirmar,              name='compras_confirmar'),
    path('compras/<int:pk>/anular/',      compra_anular,                 name='compras_anular'),
    path('compras/<int:pk>/comprobante/', compra_adjuntar_comprobante,   name='compras_adjuntar_comprobante'),

    # --- Ventas (Épic 7) ---
    path("ventas/", views_ventas.ventas_lista, name="ventas_lista"),
    path("ventas/nueva/", views_ventas.venta_nueva, name="venta_nueva"),
    path("ventas/<int:pk>/", views_ventas.venta_detalle, name="venta_detalle"),
    path("ventas/<int:pk>/ticket/", views_ventas.venta_ticket, name="venta_ticket"),
    path("ventas/<int:pk>/anular/", views_ventas.venta_anular, name="venta_anular"),

    # --- Caja (Épic 10) ---
    path("caja/", views_caja.caja_lista, name="caja_lista"),
    path("caja/abrir/", views_caja.caja_apertura, name="caja_apertura"),
    path("caja/<int:pk>/cerrar/", views_caja.caja_cierre, name="caja_cierre"),
    path("caja/<int:pk>/detalle/", views_caja.caja_detalle, name="caja_detalle"),
    path("caja/estado/", views_caja.caja_estado, name="caja_estado"),
    path("caja/arqueo/", views_caja.caja_arqueo, name="caja_arqueo"),



    # --- Movimientos de Stock (Épic 8) ---
    path("movimientos/", views_movimientos.movimientos_lista, name="movimientos_lista"),
    path("movimientos/ajuste/", views_movimientos.ajuste_stock, name="ajuste_stock"),
    


    # ============================
    # CUENTAS CORRIENTES (Épic 9)
    # ============================

    # PANEL PRINCIPAL
    path("cuentas/", views_cuentas.panel_cuentas, name="cuentas_panel"),
    # CLIENTES
    path("cuentas/clientes/", views_cuentas.cuenta_corriente_clientes, name="cuenta_corriente_clientes"),
    path("cuentas/clientes/<int:pk>/", views_cuentas.cuenta_detalle_cliente, name="cuentas_clientes_detalle"),
    path("cuentas/clientes/<int:pk>/pago/", views_cuentas.registrar_pago_cliente, name="cuentas_cliente_pago"),
    # PROVEEDORES
    path("cuentas/proveedores/", views_cuentas.cuenta_corriente_proveedores, name="cuentas_proveedores"),
    path("cuentas/proveedores/<int:pk>/", views_cuentas.cuenta_detalle_proveedor, name="cuentas_proveedores_detalle"),



    # ================================
    # ALERTAS (Épic 12)
    # ================================
    path("alertas/", views_alertas.alertas_panel, name="alertas_panel"),
    path("alertas/productos-vencimiento/", views_alertas.alertas_productos_vencidos, name="alertas_productos_vencimiento"),
    path("alertas/stock-minimo/", views_alertas.alertas_stock_minimo, name="alertas_stock_minimo"),
    path("alertas/clientes-morosos/", views_alertas.alertas_clientes_morosos, name="alertas_clientes_morosos"),
    path("alertas/generales/", views_alertas.alertas_generales, name="alertas_generales"),




    # ================================
    # REPORTES Y GRÁFICOS (Épic 12)
    # ================================
    path("reportes/", views_reportes.reportes_panel, name="reportes_panel"),

    # --- Reportes principales ---
    path("reportes/ventas/", views_reportes.reportes_ventas, name="reportes_ventas"),
    path("reportes/compras/", views_reportes.reportes_compras, name="reportes_compras"),
    path("reportes/stock/", views_reportes.reportes_stock, name="reportes_stock"),

    # --- Exportación PDF ---
    path("reportes/ventas/pdf/", views_reportes.exportar_reporte_ventas_pdf, name="exportar_reporte_ventas_pdf"),
    path("reportes/compras/pdf/", views_reportes.exportar_reporte_compras_pdf, name="exportar_reporte_compras_pdf"),
    path("reportes/stock/pdf/", views_reportes.exportar_reporte_stock_pdf, name="exportar_reporte_stock_pdf"),

    # --- Exportación Excel ---
    path("reportes/ventas/excel/", views_reportes.exportar_reporte_ventas_excel, name="exportar_reporte_ventas_excel"),
    path("reportes/compras/excel/", views_reportes.exportar_reporte_compras_excel, name="exportar_reporte_compras_excel"),
    path("reportes/stock/excel/", views_reportes.exportar_reporte_stock_excel, name="exportar_reporte_stock_excel"),




    # ================================
    # BITÁCORA DEL SISTEMA (Épic 13)
    # ================================
    path("bitacora/", views_bitacora.bitacora_panel, name="bitacora_panel"),
    path("bitacora/lista/", views_bitacora.bitacora_lista, name="bitacora_lista"),
    path("bitacora/<int:id_log>/", views_bitacora.bitacora_detalle, name="bitacora_detalle"),
    path("bitacora/exportar/csv/", views_bitacora.exportar_bitacora_csv, name="bitacora_exportar_csv"),
    path("bitacora/exportar/pdf/", views_bitacora.exportar_bitacora_pdf, name="bitacora_exportar_pdf"),
    path("bitacora/exportar/excel/", views_bitacora.exportar_bitacora_excel, name="bitacora_exportar_excel"),

]
