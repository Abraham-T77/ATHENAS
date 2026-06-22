# =========================================================
# AthenasApp/views_cuentas.py
# Gestion de Cuentas Corrientes (Clientes y Proveedores)
# =========================================================

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from AthenasApp.decorators import requiere_negocio
from AthenasApp.models import (
    CajaUsuario,
    Clientes,
    Compras,
    MovimientoCaja,
    PagoClientes,
    Proveedores,
    Venta,
)
from AthenasApp.utils import _negocio_id_from_request, get_usuario_from_request


FORMA_PAGO_CUENTA_CORRIENTE = "CUENTA_CORRIENTE"
METODOS_PAGO_CLIENTE = [
    ("EFECTIVO", "Efectivo"),
    ("TARJETA", "Tarjeta"),
    ("TRANSFERENCIA", "Transferencia"),
]


def _cliente_del_negocio(pk, neg_id, for_update=False):
    qs = Clientes.objects
    if for_update:
        qs = qs.select_for_update()
    return get_object_or_404(qs, pk=pk, negocio_id=neg_id)


def _saldo_cliente(cliente):
    return cliente.saldo_cuenta_corriente or Decimal("0")


# =========================================================
# PANEL PRINCIPAL
# =========================================================
@login_required
@requiere_negocio
@permission_required("AthenasApp.can_view_cuentas_corrientes", raise_exception=True)
def panel_cuentas(request):
    neg_id = _negocio_id_from_request(request)

    total_clientes_deuda = (
        Clientes.objects
        .filter(negocio_id=neg_id)
        .aggregate(total=Sum("saldo_cuenta_corriente"))["total"] or Decimal("0")
    )

    total_proveedores_favor = Decimal("0")
    proveedores = Proveedores.objects.filter(negocio_id=neg_id)
    for proveedor in proveedores:
        total_compras = (
            Compras.objects
            .filter(proveedor=proveedor, estado=Compras.ESTADO_CONFIRMADA)
            .aggregate(total=Sum("total"))["total"] or Decimal("0")
        )
        total_proveedores_favor += total_compras

    return render(request, "athenas/cuentas/panel_cuentas.html", {
        "total_clientes_deuda": total_clientes_deuda,
        "total_proveedores_favor": total_proveedores_favor,
        "titulo": "Panel de Cuentas Corrientes",
    })


# =========================================================
# CLIENTES - LISTADO GENERAL
# =========================================================
@login_required
@requiere_negocio
@permission_required("AthenasApp.can_view_cuentas_corrientes", raise_exception=True)
def cuenta_corriente_clientes(request):
    neg_id = _negocio_id_from_request(request)
    buscar = request.GET.get("buscar", "").strip()

    clientes = Clientes.objects.filter(negocio_id=neg_id, activo=True).order_by("nombre")
    if buscar:
        clientes = clientes.filter(nombre__icontains=buscar)

    total_deuda = clientes.aggregate(total=Sum("saldo_cuenta_corriente"))["total"] or Decimal("0")

    return render(request, "athenas/cuentas/clientes.html", {
        "clientes": clientes,
        "total_deuda": total_deuda,
    })


# =========================================================
# CLIENTE - DETALLE
# =========================================================
@login_required
@requiere_negocio
@permission_required("AthenasApp.can_view_cuentas_corrientes", raise_exception=True)
def cuenta_detalle_cliente(request, pk):
    neg_id = _negocio_id_from_request(request)
    cliente = _cliente_del_negocio(pk, neg_id)

    ventas = (
        Venta.objects
        .filter(cliente=cliente, negocio_id=neg_id, forma_pago=FORMA_PAGO_CUENTA_CORRIENTE)
        .order_by("-fecha")
    )
    ventas_confirmadas = ventas.filter(estado=Venta.ESTADO_CONFIRMADA)
    pagos = PagoClientes.objects.filter(cliente=cliente).order_by("-fecha")

    movimientos = []
    for venta in ventas:
        movimientos.append({
            "fecha": venta.fecha,
            "concepto": f"Venta {venta.numero_ticket}",
            "tipo": "DEBE" if venta.estado == Venta.ESTADO_CONFIRMADA else "ANULADA",
            "monto": venta.total_neto,
            "estado": venta.estado,
            "venta": venta,
        })

    for pago in pagos:
        movimientos.append({
            "fecha": pago.fecha,
            "concepto": pago.descripcion or "Pago",
            "tipo": "PAGO",
            "monto": pago.monto,
            "pago": pago,
        })

    movimientos = sorted(movimientos, key=lambda x: x["fecha"], reverse=True)
    total_ventas = ventas_confirmadas.aggregate(total=Sum("total_neto"))["total"] or Decimal("0")
    total_pagos = pagos.aggregate(total=Sum("monto"))["total"] or Decimal("0")

    return render(request, "athenas/cuentas/detalle_cliente.html", {
        "cliente": cliente,
        "ventas": ventas,
        "pagos": pagos,
        "movimientos": movimientos,
        "saldo_actual": _saldo_cliente(cliente),
        "total_ventas": total_ventas,
        "total_pagos": total_pagos,
    })


# =========================================================
# CLIENTE - REGISTRAR PAGO
# =========================================================
@login_required
@requiere_negocio
@permission_required("AthenasApp.add_pagoclientes", raise_exception=True)
@transaction.atomic
def registrar_pago_cliente(request, pk):
    neg_id = _negocio_id_from_request(request)
    cliente = _cliente_del_negocio(pk, neg_id, for_update=request.method == "POST")
    saldo_actual = _saldo_cliente(cliente)

    if request.method == "POST":
        monto_raw = request.POST.get("monto") or ""
        metodo_pago = request.POST.get("metodo_pago") or "EFECTIVO"
        descripcion = request.POST.get("descripcion") or "Pago registrado manualmente"
        if metodo_pago not in dict(METODOS_PAGO_CLIENTE):
            metodo_pago = "EFECTIVO"

        try:
            monto = Decimal(monto_raw.replace(",", ".")).quantize(Decimal("0.01"))
        except (InvalidOperation, AttributeError):
            messages.error(request, "Monto invalido.")
            return redirect("cuentas_clientes_detalle", pk=cliente.pk)

        if monto <= 0:
            messages.error(request, "El monto del pago debe ser mayor a cero.")
            return redirect("cuentas_clientes_detalle", pk=cliente.pk)
        if saldo_actual <= 0:
            messages.error(request, "El cliente no registra deuda pendiente.")
            return redirect("cuentas_clientes_detalle", pk=cliente.pk)
        if monto > saldo_actual:
            messages.error(request, "El pago no puede superar la deuda actual del cliente.")
            return redirect("cuentas_clientes_detalle", pk=cliente.pk)

        usuario = get_usuario_from_request(request)
        if not usuario:
            messages.error(request, "No existe un usuario de negocio asociado al usuario logueado.")
            return redirect("cuentas_clientes_detalle", pk=cliente.pk)

        caja_usuario = (
            CajaUsuario.objects
            .filter(usuario=usuario, estado="ABIERTA", caja__negocio_id=neg_id)
            .select_related("caja")
            .order_by("-fecha_apertura")
            .first()
        )
        if not caja_usuario:
            messages.error(request, "No existe una caja abierta para registrar el pago del cliente.")
            return redirect("cuentas_clientes_detalle", pk=cliente.pk)

        pago = PagoClientes.objects.create(
            cliente=cliente,
            fecha=timezone.now(),
            monto=monto,
            descripcion=f"{descripcion} - {metodo_pago}",
        )

        cliente.saldo_cuenta_corriente = saldo_actual - monto
        cliente.save(update_fields=["saldo_cuenta_corriente"])

        MovimientoCaja.registrar_automatico(
            caja_usuario=caja_usuario,
            tipo="INGRESO",
            monto=monto,
            motivo=f"Pago cuenta corriente {cliente.nombre} - {metodo_pago}",
            referencia=f"pago_cliente:{pago.pk}",
        )

        messages.success(request, "Pago registrado correctamente.")
        return redirect("cuentas_clientes_detalle", pk=cliente.pk)

    return render(request, "athenas/cuentas/pago_cliente.html", {
        "cliente": cliente,
        "saldo_actual": saldo_actual,
        "metodos_pago": METODOS_PAGO_CLIENTE,
    })


# =========================================================
# PROVEEDORES - LISTADO GENERAL
# =========================================================
@login_required
@requiere_negocio
@permission_required("AthenasApp.can_view_cuentas_corrientes", raise_exception=True)
def cuenta_corriente_proveedores(request):
    neg_id = _negocio_id_from_request(request)
    buscar = request.GET.get("buscar", "").strip()

    proveedores = Proveedores.objects.filter(negocio_id=neg_id, activo=True)
    if buscar:
        proveedores = proveedores.filter(razon_social__icontains=buscar)

    return render(request, "athenas/cuentas/proveedores.html", {
        "proveedores": proveedores,
    })


# =========================================================
# PROVEEDOR - DETALLE
# =========================================================
@login_required
@requiere_negocio
@permission_required("AthenasApp.can_view_cuentas_corrientes", raise_exception=True)
def cuenta_detalle_proveedor(request, pk):
    neg_id = _negocio_id_from_request(request)
    proveedor = get_object_or_404(Proveedores, pk=pk, negocio_id=neg_id)
    compras = Compras.objects.filter(proveedor=proveedor).order_by("-fecha")
    total_compras = (
        compras
        .filter(estado=Compras.ESTADO_CONFIRMADA)
        .aggregate(total=Sum("total"))["total"] or Decimal("0")
    )

    return render(request, "athenas/cuentas/detalle_proveedor.html", {
        "proveedor": proveedor,
        "compras": compras,
        "total_compras": total_compras,
    })
