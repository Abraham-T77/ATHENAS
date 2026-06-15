# AthenasApp/views_compras.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction, models
from django.utils import timezone
from django.core.paginator import Paginator

from .models import (
    TipoNegocio, Usuarios, Proveedores, Productos,
    Compras, DetalleCompras, ComprobantesCompra,
    MovimientoStock, LogAuditoria
)
from .audit import registrar_auditoria
from .decorators import requiere_negocio
from .forms import CompraForm, DetalleComprasFormSet, ComprobanteCompraForm

ESTADO_BORRADOR = "BORRADOR"
ESTADO_CONFIRMADA = "CONFIRMADA"

def _negocio_id_from_request(request):
    negocio = getattr(request, "NEGOCIO_ACTUAL", None)
    if negocio and getattr(negocio, "id_negocio", None):
        return negocio.id_negocio
    return request.session.get("negocio_id")


# =========================
# LISTA (con paginación)
# =========================
@login_required
@requiere_negocio
@permission_required('AthenasApp.view_compras', raise_exception=True)
def compras_lista(request):
    neg_id = _negocio_id_from_request(request)

    qs = (Compras.objects
          .filter(negocio_id=neg_id)
          .select_related('proveedor')
          .order_by('-fecha', '-id_compra'))

    # Filtros
    q = (request.GET.get('q') or '').strip()
    estado = (request.GET.get('estado') or '').strip()
    if q:
        qs = qs.filter(
            models.Q(proveedor__razon_social__icontains=q) |
            models.Q(numero_comprobante__icontains=q)
        )
    if estado:
        qs = qs.filter(estado=estado)

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    ctx = {
        "items": page_obj.object_list,   # <-- el template usa "items"
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "request": request,              # para mantener q/estado en la paginación
    }
    return render(request, 'athenas/compras/lista.html', ctx)


# =========================
# CREAR (form + formset)
# =========================
@login_required
@requiere_negocio
@permission_required('AthenasApp.add_compras', raise_exception=True)
def compra_crear(request):
    neg_id = _negocio_id_from_request(request)

    if request.method == "POST":
        form = CompraForm(request.POST, negocio_id=neg_id)
        prov_id = None
        if form.is_valid():
            prov_id = form.cleaned_data.get("proveedor").id_proveedor if form.cleaned_data.get("proveedor") else None
        formset = DetalleComprasFormSet(
            request.POST, instance=Compras(),
            form_kwargs={"negocio_id": neg_id, "proveedor_id": prov_id}
        )
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                espejo_user = Usuarios.objects.filter(usuario=request.user.username).first()

                compra = form.save(commit=False)
                compra.negocio_id = neg_id
                compra.usuario = espejo_user
                compra.fecha = compra.fecha or timezone.now()
                compra.estado = ESTADO_BORRADOR
                compra.total = 0
                compra.save()

                formset.instance = compra
                formset.save()

                total = (DetalleCompras.objects
                         .filter(compra=compra)
                         .aggregate(s=models.Sum('subtotal'))['s'] or 0)
                compra.total = total
                compra.save(update_fields=['total'])

                messages.success(request, "Compra registrada en borrador.")
                return redirect('compras_detalle', pk=compra.id_compra)
        else:
            messages.error(request, "Revisá los errores del formulario.")
    else:
        form = CompraForm(negocio_id=neg_id)
        compra = Compras()
        prov_id = None
        formset = DetalleComprasFormSet(
            instance=compra,
            form_kwargs={"negocio_id": neg_id, "proveedor_id": prov_id}
        )

    return render(request, 'athenas/compras/crear.html', {
        "form": form,
        "formset": formset,
    })


# =========================
# DETALLE
# =========================
@login_required
@requiere_negocio
@permission_required('AthenasApp.view_compras', raise_exception=True)
def compras_detalle(request, pk):
    neg_id = _negocio_id_from_request(request)
    compra = get_object_or_404(Compras, pk=pk, negocio_id=neg_id)
    detalle = DetalleCompras.objects.filter(compra=compra).select_related('producto')
    comprobantes = ComprobantesCompra.objects.filter(compra=compra).order_by('-cargado_en')

    ctx = {"obj": compra, "detalle": detalle, "comprobantes": comprobantes}
    return render(request, 'athenas/compras/detalle.html', ctx)


# =========================
# EDITAR (form + formset)
# =========================
@login_required
@requiere_negocio
@permission_required('AthenasApp.change_compras', raise_exception=True)
def compra_editar(request, pk):
    neg_id = _negocio_id_from_request(request)
    compra = get_object_or_404(Compras, pk=pk, negocio_id=neg_id)

    if compra.estado == ESTADO_CONFIRMADA:
        messages.warning(request, "No podés editar una compra confirmada.")
        return redirect('compras_detalle', pk=pk)

    if request.method == "POST":
        form = CompraForm(request.POST, instance=compra, negocio_id=neg_id)
        formset = DetalleComprasFormSet(request.POST, instance=compra)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()

                total = (DetalleCompras.objects
                         .filter(compra=compra)
                         .aggregate(s=models.Sum('subtotal'))['s'] or 0)
                compra.total = total
                compra.save(update_fields=['total'])

                messages.success(request, "Compra modificada correctamente.")
                return redirect('compras_detalle', pk=pk)
        else:
            messages.error(request, "Revisá los errores del formulario.")
    else:
        form = CompraForm(instance=compra, negocio_id=neg_id)
        formset = DetalleComprasFormSet(instance=compra)

    return render(request, 'athenas/compras/editar.html', {
        "compra": compra,
        "form": form,
        "formset": formset,
    })


# =========================
# CONFIRMAR (mueve stock)
# =========================
@login_required
@requiere_negocio
@permission_required('AthenasApp.change_compras', raise_exception=True)
def compra_confirmar(request, pk):
    neg_id = _negocio_id_from_request(request)
    compra = get_object_or_404(Compras, pk=pk, negocio_id=neg_id)

    if compra.estado == ESTADO_CONFIRMADA:
        messages.warning(request, "La compra ya está confirmada.")
        return redirect('compras_detalle', pk=pk)

    detalles = DetalleCompras.objects.filter(compra=compra).select_related('producto')
    espejo_user = Usuarios.objects.filter(usuario=request.user.username).first()

    with transaction.atomic():
        for det in detalles:
            # Aumentar stock
            Productos.objects.filter(pk=det.producto.pk).update(
                stock_actual=models.F('stock_actual') + det.cantidad
            )
            MovimientoStock.objects.create(
                fecha=timezone.now(),
                tipo="ENTRADA",
                cantidad=det.cantidad,
                producto=det.producto,
                usuario=espejo_user
            )
        compra.estado = ESTADO_CONFIRMADA
        compra.save(update_fields=['estado'])

        # Auditoría
        registrar_auditoria(
            request,
            accion="Compra confirmada",
            entidad="Compra",
            id_registro=compra.pk
        )




    messages.success(request, "Compra confirmada correctamente.")
    return redirect('compras_detalle', pk=pk)


# =========================
# ANULAR (borradores o confirmadas)
# =========================
@login_required
@requiere_negocio
@permission_required('AthenasApp.delete_compras', raise_exception=True)
def compra_anular(request, pk):
    neg_id = _negocio_id_from_request(request)
    compra = get_object_or_404(Compras, pk=pk, negocio_id=neg_id)

    # Ya anulada: no hacer nada
    if compra.estado == Compras.ESTADO_ANULADA:
        messages.info(request, f"La compra #{pk} ya estaba anulada.")
        return redirect('compras_lista')

    # Borrador: eliminar
    if compra.estado == Compras.ESTADO_BORRADOR:
        compra.delete()
        messages.success(request, f"La compra #{pk} fue eliminada (borrador).")
        return redirect('compras_lista')

    # Confirmada: invocar método del modelo que revierte stock + log
    if compra.estado == Compras.ESTADO_CONFIRMADA:
        try:
            with transaction.atomic():
                compra.anular(request.user)  # usa el método del modelo
            messages.success(request, f"La compra #{pk} fue anulada correctamente.")

            registrar_auditoria(
                request,
                accion="Compra anulada",
                entidad="Compra",
                id_registro=compra.pk
            )


        except Exception as e:
            messages.error(request, f"No se pudo anular la compra: {e}")
        return redirect('compras_lista')

    messages.error(request, "Estado de compra no soportado para anulación.")
    return redirect('compras_lista')




# =========================
# ADJUNTAR COMPROBANTE
# =========================
@login_required
@requiere_negocio
@permission_required('AthenasApp.add_comprobantescompra', raise_exception=True)
def compra_adjuntar_comprobante(request, pk):
    neg_id = _negocio_id_from_request(request)
    compra = get_object_or_404(Compras, pk=pk, negocio_id=neg_id)

    if request.method == "POST":
        form = ComprobanteCompraForm(request.POST, request.FILES)
        if form.is_valid():
            comp = form.save(commit=False)
            comp.compra = compra
            comp.cargado_en = timezone.now()
            comp.save()
            messages.success(request, "Comprobante adjuntado.")
            return redirect('compras_detalle', pk=pk)
        else:
            messages.error(request, "Revisá los errores del comprobante.")
    else:
        form = ComprobanteCompraForm()

    return render(request, 'athenas/compras/adjuntar_comprobante.html', {
        "compra": compra,
        "form": form,
    })
