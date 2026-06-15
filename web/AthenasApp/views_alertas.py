# =========================================================
# AthenasApp/views_alertas.py
# ÉPIC 12 – Alertas del Sistema y Productos Vencidos
# =========================================================

from django.shortcuts import render
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import F
from django.utils import timezone

from AthenasApp.models import Productos, Clientes, BitacoraSistema
from AthenasApp.decorators import requiere_negocio


# =========================================================
# PANEL PRINCIPAL DE ALERTAS
# =========================================================

@login_required
@requiere_negocio
@permission_required("AthenasApp.view_productos", raise_exception=True)
def alertas_panel(request):
    """
    Vista principal del módulo de alertas.
    Muestra un resumen por tipo:
    - productos vencidos
    - productos por vencer (15 días)
    - stock mínimo
    - clientes morosos
    - eventos del sistema
    """
    hoy = timezone.now().date()
    neg_id = request.session.get("NEGOCIO_ID")

    # Base de productos del negocio
    productos_qs = Productos.objects.filter(activo=True)
    if neg_id:
        productos_qs = productos_qs.filter(negocio_id=neg_id)

    productos_vencidos = productos_qs.filter(fecha_vencimiento__lt=hoy)
    productos_vencimiento = productos_qs.filter(
        fecha_vencimiento__gte=hoy,
        fecha_vencimiento__lte=hoy + timezone.timedelta(days=15),
    )
    productos_stock_bajo = productos_qs.filter(
        stock_actual__lte=F("stock_minimo")
    )

    # Clientes del negocio con deuda
    clientes_qs = Clientes.objects.filter(activo=True)
    if neg_id:
        clientes_qs = clientes_qs.filter(negocio_id=neg_id)

    clientes_morosos = clientes_qs.filter(
        saldo_cuenta_corriente__gt=0
    )

    # Eventos del sistema (bitácora)
    eventos_sistema = BitacoraSistema.objects.order_by("-fecha")[:50]

    context = {
        "productos_vencidos": productos_vencidos,
        "productos_vencimiento": productos_vencimiento,
        "productos_stock_bajo": productos_stock_bajo,
        "clientes_morosos": clientes_morosos,
        "eventos_sistema": eventos_sistema,
        "titulo": "Panel de Alertas del Sistema",
    }
    return render(request, "athenas/alertas/panel_alertas.html", context)


# =========================================================
# ALERTAS DETALLADAS – PRODUCTOS VENCIDOS / POR VENCER
# =========================================================

@login_required
@requiere_negocio
@permission_required("AthenasApp.view_productos", raise_exception=True)
def alertas_productos_vencidos(request):
    """
    Lista detallada de productos:
    - vencidos
    - próximos a vencer en 15 días
    """
    hoy = timezone.now().date()
    neg_id = request.session.get("NEGOCIO_ID")

    productos_qs = Productos.objects.filter(activo=True)
    if neg_id:
        productos_qs = productos_qs.filter(negocio_id=neg_id)

    vencidos = productos_qs.filter(
        fecha_vencimiento__lt=hoy
    ).order_by("fecha_vencimiento", "descripcion")

    proximos = productos_qs.filter(
        fecha_vencimiento__gte=hoy,
        fecha_vencimiento__lte=hoy + timezone.timedelta(days=15),
    ).order_by("fecha_vencimiento", "descripcion")

    # Calculamos días restantes para que el template no haga cuentas raras
    for p in proximos:
        if p.fecha_vencimiento:
            p.dias_restantes = (p.fecha_vencimiento - hoy).days
        else:
            p.dias_restantes = None

    context = {
        "vencidos": vencidos,
        "proximos": proximos,
        "titulo": "Productos Vencidos o Próximos a Vencer",
    }
    return render(request, "athenas/alertas/productos_vencimiento.html", context)


# =========================================================
# ALERTAS DETALLADAS – STOCK MÍNIMO
# =========================================================

@login_required
@requiere_negocio
@permission_required("AthenasApp.view_productos", raise_exception=True)
def alertas_stock_minimo(request):
    """
    Lista de productos con stock bajo o sin stock.
    """
    neg_id = request.session.get("NEGOCIO_ID")

    productos = Productos.objects.filter(
        activo=True,
        stock_actual__lte=F("stock_minimo"),
    )
    if neg_id:
        productos = productos.filter(negocio_id=neg_id)

    productos = productos.order_by("descripcion")

    context = {
        "productos": productos,
        "titulo": "Productos con Stock Bajo o Agotado",
    }
    return render(request, "athenas/alertas/stock_minimo.html", context)


# =========================================================
# ALERTAS DETALLADAS – CLIENTES MOROSOS
# =========================================================

@login_required
@requiere_negocio
@permission_required("AthenasApp.view_clientes", raise_exception=True)
def alertas_clientes_morosos(request):
    """
    Lista de clientes con saldo deudor en cuenta corriente.
    """
    neg_id = request.session.get("NEGOCIO_ID")

    clientes = Clientes.objects.filter(
        activo=True,
        saldo_cuenta_corriente__gt=0,
    )
    if neg_id:
        clientes = clientes.filter(negocio_id=neg_id)

    clientes = clientes.order_by("-saldo_cuenta_corriente", "nombre")

    context = {
        "clientes": clientes,
        "titulo": "Clientes con Deudas Pendientes",
    }
    return render(request, "athenas/alertas/clientes_morosos.html", context)


# =========================================================
# ALERTAS GENERALES – BITÁCORA
# =========================================================

@login_required
@requiere_negocio
@permission_required("AthenasApp.view_bitacorasistema", raise_exception=True)
def alertas_generales(request):
    """
    Muestra los últimos eventos registrados en la bitácora del sistema.
    Tomamos sólo los más recientes para que la lista sea manejable.
    """
    alertas = BitacoraSistema.objects.order_by("-fecha")[:100]

    context = {
        "alertas": alertas,
        "titulo": "Alertas Generales del Sistema",
    }
    return render(request, "athenas/alertas/generales.html", context)
