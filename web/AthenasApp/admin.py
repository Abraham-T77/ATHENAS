from django.contrib import admin
from .models import (
    TipoNegocio, Roles, Usuarios,
    Caja, CajaUsuario,
    Clientes, Proveedores,
    Productos, Categoria, Marca, UnidadMedida,
    Venta, VentaDetalle, VentaPago,
    Compras, DetalleCompras, ComprobantesCompra,
    PagoClientes, MovimientoCaja, MovimientoStock, LogAuditoria,
    CuentaCorrienteCliente, AlertaSistema, ReporteSistema, BitacoraSistema
)

# =========================================================
# MODELOS BASE (necesarios para autocomplete)
# =========================================================

@admin.register(TipoNegocio)
class TipoNegocioAdmin(admin.ModelAdmin):
    list_display = ("detalle",)
    search_fields = ("detalle",)
    list_per_page = 25


@admin.register(Caja)
class CajaAdmin(admin.ModelAdmin):
    list_display = ("id_caja", "descripcion", "negocio", "estado", "saldo_inicial", "fecha_apertura", "fecha_cierre")
    list_filter = ("negocio", "estado")
    search_fields = ("descripcion",)
    date_hierarchy = "fecha_apertura"
    list_per_page = 25



@admin.register(Clientes)
class ClientesAdmin(admin.ModelAdmin):
    list_display = ("id_cliente", "nombre", "telefono", "saldo_cuenta_corriente", "activo")
    search_fields = ("nombre", "telefono")
    list_filter = ("activo",)
    list_per_page = 25


@admin.register(Productos)
class ProductosAdmin(admin.ModelAdmin):
    list_display = ("id_producto", "descripcion", "negocio", "categoria", "marca", "unidad", "precio_venta", "stock_actual")
    search_fields = ("descripcion", "codigo_barra", "sku")
    list_filter = ("negocio", "categoria", "marca", "unidad")
    autocomplete_fields = ("negocio", "categoria", "marca", "unidad")
    list_per_page = 25


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "negocio")
    search_fields = ("nombre",)
    list_filter = ("negocio",)
    autocomplete_fields = ("negocio",)
    list_per_page = 25


@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "negocio")
    search_fields = ("nombre",)
    list_filter = ("negocio",)
    autocomplete_fields = ("negocio",)
    list_per_page = 25


@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ("nombre",)
    search_fields = ("nombre",)
    list_per_page = 25


# =========================================================
# ROLES Y USUARIOS
# =========================================================

@admin.register(Roles)
class RolesAdmin(admin.ModelAdmin):
    list_display = ("id_rol", "descripcion")
    search_fields = ("descripcion",)
    list_per_page = 25


@admin.register(Usuarios)
class UsuariosAdmin(admin.ModelAdmin):
    list_display = ("id_usuario", "nombre", "usuario", "rol", "negocio")
    search_fields = ("nombre", "usuario")
    list_filter = ("rol", "negocio")
    autocomplete_fields = ("rol", "negocio")
    list_per_page = 25


# =========================================================
# CAJAS Y MOVIMIENTOS
# =========================================================

@admin.register(CajaUsuario)
class CajaUsuarioAdmin(admin.ModelAdmin):
    list_display = ("id", "caja", "usuario", "fecha_apertura", "fecha_cierre", "saldo_inicial", "saldo_final", "estado")
    list_filter = ("estado", "caja__negocio")
    search_fields = ("caja__descripcion", "usuario__usuario")
    date_hierarchy = "fecha_apertura"
    autocomplete_fields = ("caja", "usuario")
    list_per_page = 25


@admin.register(MovimientoCaja)
class MovimientoCajaAdmin(admin.ModelAdmin):
    list_display = ("id", "caja_usuario", "tipo", "monto", "motivo", "referencia", "fecha")
    list_filter = ("tipo", "caja_usuario")
    search_fields = ("motivo", "referencia")
    autocomplete_fields = ("caja_usuario",)
    date_hierarchy = "fecha"
    list_per_page = 25


@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = ("id", "fecha", "tipo", "producto", "cantidad", "usuario")
    list_filter = ("tipo", "producto__negocio")
    search_fields = ("producto__descripcion", "usuario__usuario")
    autocomplete_fields = ("producto", "usuario")
    date_hierarchy = "fecha"
    list_per_page = 25


# =========================================================
# PAGOS Y CUENTAS
# =========================================================

@admin.register(PagoClientes)
class PagoClientesAdmin(admin.ModelAdmin):
    list_display = ("id_pago", "fecha", "cliente", "monto", "descripcion")
    list_filter = ("cliente__negocio",)
    search_fields = ("cliente__nombre", "descripcion")
    autocomplete_fields = ("cliente",)
    date_hierarchy = "fecha"
    list_per_page = 25



@admin.register(CuentaCorrienteCliente)
class CuentaCorrienteClienteAdmin(admin.ModelAdmin):
    list_display = ("cliente", "saldo_actual")
    search_fields = ("cliente__nombre",)
    list_filter = ("cliente__negocio",)
    autocomplete_fields = ("cliente",)
    list_per_page = 25


# =========================================================
# ALERTAS, REPORTES Y BITÁCORA
# =========================================================

@admin.register(AlertaSistema)
class AlertaSistemaAdmin(admin.ModelAdmin):
    list_display = ("id_alerta", "tipo", "nivel", "mensaje", "descripcion", "negocio", "usuario_asignado", "estado", "creado_en", "resuelto_en")
    list_filter = ("tipo", "nivel", "estado", "negocio")
    search_fields = ("mensaje", "descripcion")
    autocomplete_fields = ("negocio", "usuario_asignado")
    date_hierarchy = "creado_en"
    list_per_page = 25


@admin.register(ReporteSistema)
class ReporteSistemaAdmin(admin.ModelAdmin):
    list_display = ("id_reporte", "tipo", "titulo", "negocio", "usuario", "generado_en")
    list_filter = ("tipo", "negocio")
    search_fields = ("titulo", "descripcion")
    autocomplete_fields = ("negocio", "usuario")
    date_hierarchy = "generado_en"
    list_per_page = 25


@admin.register(BitacoraSistema)
class BitacoraSistemaAdmin(admin.ModelAdmin):
    list_display = ("id_bitacora", "fecha", "usuario", "accion", "detalle", "exito")
    search_fields = ("accion", "detalle", "usuario__usuario")
    autocomplete_fields = ("usuario",)
    date_hierarchy = "fecha"
    list_per_page = 25
