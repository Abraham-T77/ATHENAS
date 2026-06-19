# =========================
# VIEWS - MOVIMIENTOS DE STOCK
# =========================
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q

from .models import MovimientoStock, Productos, LogAuditoria
from .utils import _negocio_id_from_request, get_usuario_from_request
from .audit import registrar_auditoria
from .decorators import requiere_negocio


# ============================================================
# LISTA GENERAL DE MOVIMIENTOS (Entrada / Salida / Ajuste / Anulación)
# ============================================================
@login_required
@requiere_negocio
@permission_required("AthenasApp.view_movimientostock", raise_exception=True)
def movimientos_lista(request):
    neg_id = _negocio_id_from_request(request)

    q = request.GET.get("q", "")
    tipo = request.GET.get("tipo", "")
    desde = request.GET.get("desde", "")
    hasta = request.GET.get("hasta", "")

    movimientos = MovimientoStock.objects.filter(negocio_id=neg_id)

    # --- BÚSQUEDA GENERAL (producto o usuario espejo) ---
    if q:
        movimientos = movimientos.filter(
            Q(producto__descripcion__icontains=q) |
            Q(usuario__usuario__icontains=q)   # usuario = modelo Usuarios
        )

    # --- FILTRO POR TIPO ---
    if tipo:
        movimientos = movimientos.filter(tipo=tipo)

    # --- FILTRO POR RANGO DE FECHAS ---
    if desde:
        movimientos = movimientos.filter(fecha__date__gte=desde)

    if hasta:
        movimientos = movimientos.filter(fecha__date__lte=hasta)

    movimientos = movimientos.order_by("-fecha")

    # --- PAGINACIÓN ---
    paginator = Paginator(movimientos, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "athenas/movimientos/listado_movimientos.html", {
        "items": page_obj,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
    })


# ============================================================
# LISTA EXCLUSIVA DE AJUSTES
# ============================================================
@login_required
@requiere_negocio
@permission_required("AthenasApp.view_movimientostock", raise_exception=True)
def ajustes_list(request):
    neg_id = _negocio_id_from_request(request)

    q = request.GET.get("q", "")
    tipo = request.GET.get("tipo", "")

    movimientos = MovimientoStock.objects.filter(
        negocio_id=neg_id,
        tipo__in=["ENTRADA", "SALIDA"]
    )

    # --- BÚSQUEDA GENERAL ---
    if q:
        movimientos = movimientos.filter(
            Q(producto__descripcion__icontains=q) |
            Q(usuario__usuario__icontains=q)
        )

    # --- FILTRO POR TIPO ---
    if tipo:
        movimientos = movimientos.filter(tipo=tipo)

    movimientos = movimientos.order_by("-fecha")

    # Paginación
    paginator = Paginator(movimientos, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "athenas/movimientos/ajustes_list.html", {
        "items": page_obj,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
    })


@login_required
@requiere_negocio
@permission_required("AthenasApp.can_adjust_stock", raise_exception=True)
def ajuste_stock(request):
    usuario = get_usuario_from_request(request)
    neg_id = _negocio_id_from_request(request)  # ← usar siempre el helper

    productos = Productos.objects.filter(
        negocio_id=neg_id,
        activo=True
    ).order_by("descripcion")

    if request.method == "POST":
        producto_id = request.POST.get("producto_id")
        tipo = request.POST.get("tipo")
        cantidad_raw = request.POST.get("cantidad")
        motivo = request.POST.get("motivo") or "Ajuste manual"

        # Validar datos
        errores = []
        if not producto_id:
            errores.append("Debe seleccionar un producto.")

        # intentar obtener el producto (valida que exista y sea del negocio)
        producto = None
        if producto_id:
            try:
                producto = Productos.objects.get(pk=producto_id, negocio_id=neg_id)
            except Productos.DoesNotExist:
                errores.append("Debe seleccionar un producto válido.")

        try:
            cantidad = int(cantidad_raw)
            if cantidad <= 0:
                errores.append("La cantidad debe ser mayor a cero.")
        except Exception:
            errores.append("Cantidad inválida.")

        if tipo not in ["ENTRADA", "SALIDA"]:
            errores.append("Tipo de movimiento inválido.")

        if errores:
            return render(request, "athenas/movimientos/ajustes_form.html", {
                "errores": errores,
                "productos": productos,
            })

        try:
            with transaction.atomic():
                # producto ya lo tenemos validado arriba
                if tipo == "ENTRADA":
                    producto.stock_actual += cantidad
                else:  # SALIDA
                    if producto.stock_actual < cantidad:
                        messages.error(
                            request,
                            "No hay suficiente stock para realizar la salida."
                        )
                        return redirect("ajuste_stock")
                    producto.stock_actual -= cantidad

                producto.save()

                MovimientoStock.objects.create(
                    producto=producto,
                    tipo=tipo,
                    cantidad=cantidad,
                    usuario=usuario,
                    motivo=motivo,
                    negocio=producto.negocio,
                    fecha=timezone.now(),
                )

                registrar_auditoria(
                    request,
                    accion=f"Ajuste de stock ({tipo})",
                    entidad="MovimientoStock",
                    id_registro=producto.pk,
                )

                messages.success(request, "Ajuste registrado correctamente.")
                # 🔴 IMPORTANTE: redirigimos a una URL que YA EXISTE
                return redirect("movimientos_lista")

        except Exception as e:
            messages.error(request, f"Error al ajustar stock: {e}")

    return render(request, "athenas/movimientos/ajustes_form.html", {
        "productos": productos,
    })


