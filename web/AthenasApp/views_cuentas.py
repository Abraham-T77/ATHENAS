# =========================================================
# AthenasApp/views_cuentas.py
# Gestión de Cuentas Corrientes (Clientes y Proveedores)
# =========================================================

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from django.contrib.auth.decorators import login_required
from AthenasApp.decorators import requiere_negocio

# Modelos REALES que ya existen en tu sistema
from AthenasApp.models import (
    Clientes, Proveedores,
    PagoClientes,
    Venta, Compras
)


# =========================================================
# PANEL PRINCIPAL
# =========================================================
def panel_cuentas(request):
    """Panel principal de Cuentas Corrientes."""
    
    # 1) Total de deuda de CLIENTES
    total_clientes_deuda = (
        Clientes.objects.aggregate(total=Sum("saldo_cuenta_corriente"))
        ["total"] or 0
    )

    # 2) Total de "saldo a favor" de PROVEEDORES
    #    Como Proveedores NO tiene campo de saldo, lo calculamos desde las compras confirmadas.
    total_proveedores_favor = 0
    proveedores = Proveedores.objects.all()

    for p in proveedores:
        compras = Compras.objects.filter(
            proveedor=p,
            estado=Compras.ESTADO_CONFIRMADA
        )
        total_compras = compras.aggregate(total=Sum("total"))["total"] or 0
        total_proveedores_favor += total_compras

    return render(request, "athenas/cuentas/panel_cuentas.html", {
        "total_clientes_deuda": total_clientes_deuda,
        "total_proveedores_favor": total_proveedores_favor,
        "titulo": "Panel de Cuentas Corrientes",
    })


# =========================================================
# CLIENTES – LISTADO GENERAL
# =========================================================
@login_required
@requiere_negocio
def cuenta_corriente_clientes(request):

    buscar = request.GET.get("buscar", "")

    clientes = Clientes.objects.filter(activo=True)

    if buscar:
        clientes = clientes.filter(nombre__icontains=buscar)

    total_deuda = clientes.aggregate(total=Sum("saldo_cuenta_corriente"))["total"] or 0

    return render(request, "athenas/cuentas/clientes.html", {
        "clientes": clientes,
        "total_deuda": total_deuda,
    })


# =========================================================
# CLIENTE – DETALLE
# =========================================================
@login_required
@requiere_negocio
def cuenta_detalle_cliente(request, pk):

    cliente = get_object_or_404(Clientes, pk=pk)

    # ventas del cliente
    ventas = Venta.objects.filter(cliente=cliente, estado="CONFIRMADA")

    # pagos
    pagos = PagoClientes.objects.filter(cliente=cliente).order_by("-fecha")

    # unir movimientos para el template
    movimientos = []

    for v in ventas:
        movimientos.append({
            "fecha": v.fecha,
            "concepto": f"Venta {v.numero_ticket}",
            "tipo": "DEBE",
            "monto": v.total_neto
        })

    for p in pagos:
        movimientos.append({
            "fecha": p.fecha,
            "concepto": p.descripcion,
            "tipo": "PAGO",
            "monto": p.monto
        })

    movimientos = sorted(movimientos, key=lambda x: x["fecha"], reverse=True)

    return render(request, "athenas/cuentas/detalle_cliente.html", {
        "cliente": cliente,
        "movimientos": movimientos,
    })


# =========================================================
# CLIENTE – REGISTRAR PAGO
# =========================================================
@login_required
@requiere_negocio
@transaction.atomic
def registrar_pago_cliente(request, pk):

    cliente = get_object_or_404(Clientes, pk=pk)

    if request.method == "POST":
        monto_raw = request.POST.get("monto")
        descripcion = request.POST.get("descripcion") or "Pago registrado manualmente"

        try:
            monto = float(monto_raw)
            if monto <= 0:
                raise ValueError()

            PagoClientes.objects.create(
                cliente=cliente,
                fecha=timezone.now(),
                monto=monto,
                descripcion=descripcion,
            )

            cliente.saldo_cuenta_corriente = max(0, cliente.saldo_cuenta_corriente - monto)
            cliente.save()

            messages.success(request, "Pago registrado correctamente.")

        except Exception:
            messages.error(request, "Monto inválido.")

        return redirect("cuentas_clientes_detalle", pk=cliente.pk)

    return render(request, "athenas/cuentas/pago_cliente.html", {
        "cliente": cliente,
    })


# =========================================================
# PROVEEDORES – LISTADO GENERAL
# =========================================================
@login_required
@requiere_negocio
def cuenta_corriente_proveedores(request):

    buscar = request.GET.get("buscar", "")

    proveedores = Proveedores.objects.filter(activo=True)

    if buscar:
        proveedores = proveedores.filter(razon_social__icontains=buscar)

    return render(request, "athenas/cuentas/proveedores.html", {
        "proveedores": proveedores,
    })


# =========================================================
# PROVEEDOR – DETALLE
# =========================================================
@login_required
@requiere_negocio
def cuenta_detalle_proveedor(request, pk):

    proveedor = get_object_or_404(Proveedores, pk=pk)

    compras = Compras.objects.filter(proveedor=proveedor).order_by("-fecha")

    return render(request, "athenas/cuentas/detalle_proveedor.html", {
        "proveedor": proveedor,
        "compras": compras,
    })
