# AthenasApp/views_ventas.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction, models
from django.utils import timezone
from django.urls import reverse

from AthenasApp.audit import registrar_auditoria


from .models import (
    TipoNegocio, Usuarios, Productos, Clientes,
    Venta, VentaDetalle, VentaPago, MovimientoCaja, MovimientoStock, CajaUsuario,
    LogAuditoria
)
from .decorators import requiere_negocio

FORMA_PAGO_EFECTIVO = "Efectivo"
FORMA_PAGO_TARJETA = "Tarjeta"
FORMA_PAGO_TRANSFERENCIA = "Transferencia"
FORMA_PAGO_MIXTO = "Mixto"

ESTADO_BORRADOR = "BORRADOR"
ESTADO_CONFIRMADA = "CONFIRMADA"


def _negocio_id_from_request(request):
    negocio = getattr(request, "NEGOCIO_ACTUAL", None)
    if negocio and getattr(negocio, "id_negocio", None):
        return negocio.id_negocio
    return request.session.get("negocio_id")


@login_required
@requiere_negocio
@permission_required('AthenasApp.view_venta', raise_exception=True)
def ventas_lista(request):
    neg_id = _negocio_id_from_request(request)
    qs = (Venta.objects
          .filter(negocio_id=neg_id)
          .order_by('-fecha', '-id_venta'))

    # Filtros simples
    estado = request.GET.get('estado') or ''
    forma = request.GET.get('forma') or ''
    if estado:
        qs = qs.filter(estado=estado)
    if forma:
        qs = qs.filter(forma_pago=forma)

    ctx = {
        "ventas": qs[:200],
        "f_estado": estado,
        "f_forma": forma,
    }
    return render(request, 'athenas/ventas/lista.html', ctx)


@login_required
@requiere_negocio
@permission_required('AthenasApp.add_venta', raise_exception=True)
def venta_nueva(request):
    """
    GET: muestra formulario + "carrito".
    POST: valida, descuenta stock y crea Venta + Detalles + Pagos (transacción).
    """
    neg_id = _negocio_id_from_request(request)
    clientes = Clientes.objects.filter(negocio_id=neg_id, activo=True).order_by('nombre')
    productos = Productos.objects.filter(negocio_id=neg_id, activo=True).order_by('descripcion')

    if request.method == "POST":
        prod_ids = request.POST.getlist('producto_id[]')
        cants    = request.POST.getlist('cantidad[]')
        precios  = request.POST.getlist('precio_unitario[]')
        descs    = request.POST.getlist('desc_item_pct[]')  # opcional

        forma_pago = request.POST.get('forma_pago') or FORMA_PAGO_EFECTIVO
        cliente_id = request.POST.get('cliente_id') or None
        desc_global_pct = request.POST.get('descuento_global_pct') or ""

        # Normalizar descuento global
        try:
            descuento_global_pct = (
                float(desc_global_pct.replace(',', '.')) if desc_global_pct else None
            )
        except Exception:
            descuento_global_pct = None

        # Si no hay cliente, crear/usar "Consumidor Final"
        if not cliente_id:
            consumidor_final, _ = Clientes.objects.get_or_create(
                negocio_id=neg_id,
                nombre="Consumidor Final",
                defaults={"activo": True}
            )
            cliente_id = consumidor_final.id_cliente

        # Sanitizar items del carrito
        items = []
        for i in range(len(prod_ids)):
            try:
                pid = int(prod_ids[i])
                cant = int(cants[i])
                pu = float((precios[i] or '0').replace(',', '.'))
                di = float((descs[i] or '').replace(',', '.')) if (i < len(descs) and descs[i]) else None
            except Exception:
                continue
            if pid > 0 and cant > 0 and pu >= 0:
                items.append((pid, cant, pu, di))

        if not items:
            messages.error(request, "El carrito está vacío o contiene datos inválidos.")
            return redirect('venta_nueva')

        with transaction.atomic():
            # Usuario de negocio (modelo Usuarios, espejo del auth User)
            usuario_negocio = Usuarios.objects.filter(
                usuario=request.user.username
            ).first()
            if not usuario_negocio:
                messages.error(
                    request,
                    "No existe un usuario de negocio asociado al usuario logueado."
                )
                transaction.set_rollback(True)
                return redirect('ventas_lista')

            # Bloquear stock de productos seleccionados
            productos_qs = (
                Productos.objects
                .select_for_update()
                .filter(negocio_id=neg_id,
                        id_producto__in=[i[0] for i in items],
                        activo=True)
            )
            prods_map = {p.id_producto: p for p in productos_qs}

            total_bruto = 0
            lineas_ok = []
            for pid, cant, pu, di in items:
                prod = prods_map.get(pid)
                if not prod:
                    transaction.set_rollback(True)
                    messages.error(
                        request,
                        f"Producto ID {pid} no existe en el negocio actual."
                    )
                    return redirect('venta_nueva')

                if prod.stock_actual < cant:
                    transaction.set_rollback(True)
                    messages.error(
                        request,
                        f"Sin stock suficiente para '{prod.descripcion}'."
                    )
                    return redirect('venta_nueva')

                precio_aplicado = pu
                if di is not None and 0 <= di <= 100:
                    precio_aplicado = round(pu * (1 - di/100), 2)

                subtotal = round(cant * precio_aplicado, 2)
                total_bruto += subtotal
                lineas_ok.append((prod, cant, pu, di, subtotal))

            total_neto = total_bruto
            if descuento_global_pct is not None and 0 <= descuento_global_pct <= 100:
                total_neto = round(total_bruto * (1 - descuento_global_pct/100), 2)

            # anio + secuencial (por negocio, año)
            anio = timezone.now().year
            ultimo = (
                Venta.objects
                .filter(negocio_id=neg_id, anio=anio)
                .aggregate(maxn=models.Max('nro_secuencial'))['maxn'] or 0
            )
            nro_secuencial = int(ultimo) + 1
            numero_ticket = f"{anio}-{int(neg_id):02d}-{nro_secuencial:06d}"

            # Buscar la caja abierta del usuario de negocio
            caja_usuario = (
                CajaUsuario.objects
                .filter(usuario=usuario_negocio,
                        estado="ABIERTA",
                        caja__negocio_id=neg_id)
                .select_related("caja")
                .order_by("-fecha_apertura")
                .first()
            )
            if not caja_usuario:
                messages.error(request, "No existe una caja abierta para este usuario.")
                transaction.set_rollback(True)
                return redirect("ventas_lista")

            # Crear la venta
            venta = Venta.objects.create(
                fecha=timezone.now(),
                usuario=usuario_negocio,      # <- modelo Usuarios
                cliente_id=cliente_id,
                caja=caja_usuario.caja,
                negocio_id=neg_id,
                anio=anio,
                nro_secuencial=nro_secuencial,
                numero_ticket=numero_ticket,
                total_bruto=total_bruto,
                total_neto=total_neto,
                descuento_global_pct=descuento_global_pct,
                forma_pago=forma_pago,
                estado=ESTADO_CONFIRMADA,
            )

            # Detalles + movimiento de stock (salida)
            for prod, cant, pu, di, subtotal in lineas_ok:
                VentaDetalle.objects.create(
                    venta=venta,
                    producto=prod,
                    cantidad=cant,
                    precio_unitario=pu,
                    subtotal=subtotal,
                    nombre_producto=prod.descripcion,
                    descuento_item_pct=di
                )
                Productos.objects.filter(pk=prod.pk).update(
                    stock_actual=models.F('stock_actual') - cant
                )
                MovimientoStock.objects.create(
                    fecha=timezone.now(),
                    tipo="SALIDA",
                    cantidad=cant,
                    producto=prod,
                    usuario=usuario_negocio,   # <- también Usuarios
                )

            # === Registrar pagos + movimientos de caja ===
            if forma_pago == FORMA_PAGO_MIXTO:
                partes = []
                for key in ['pago_efectivo', 'pago_tarjeta', 'pago_transferencia']:
                    raw = request.POST.get(key) or ""
                    try:
                        monto = float(raw.replace(',', '.')) if raw else 0
                    except Exception:
                        monto = 0
                    if monto > 0:
                        metodo = key.replace('pago_', '').capitalize()
                        partes.append((metodo, monto))

                if not partes:
                    transaction.set_rollback(True)
                    messages.error(
                        request,
                        "Forma de pago Mixto requiere al menos un monto válido."
                    )
                    return redirect('venta_nueva')

                suma = round(sum(m for _, m in partes), 2)
                if suma != float(total_neto):
                    transaction.set_rollback(True)
                    messages.error(
                        request,
                        "La suma de los pagos no coincide con el total neto."
                    )
                    return redirect('venta_nueva')

                for metodo, monto in partes:
                    VentaPago.objects.create(
                        venta=venta,
                        metodo=metodo,
                        monto=monto
                    )
                    MovimientoCaja.registrar_automatico(
                        caja_usuario=caja_usuario,
                        tipo="INGRESO",
                        monto=monto,
                        motivo=f"Venta {venta.numero_ticket} - {metodo}",
                        referencia=str(venta.pk)
                    )
            else:
                VentaPago.objects.create(
                    venta=venta,
                    metodo=forma_pago,
                    monto=total_neto
                )
                MovimientoCaja.registrar_automatico(
                    caja_usuario=caja_usuario,
                    tipo="INGRESO",
                    monto=total_neto,
                    motivo=f"Venta {venta.numero_ticket} - {forma_pago}",
                    referencia=str(venta.pk)
                )

            # === Auditoría ===
            registrar_auditoria(
                request,
                accion="Venta confirmada",
                entidad="Venta",
                id_registro=venta.pk
            )


        messages.success(request, f"Venta confirmada. Ticket {venta.numero_ticket}.")
        return redirect('venta_ticket', pk=venta.id_venta)

    # GET
    ctx = {
        "clientes": clientes,
        "productos": productos,
        "formas_pago": [
            FORMA_PAGO_EFECTIVO,
            FORMA_PAGO_TARJETA,
            FORMA_PAGO_TRANSFERENCIA,
            FORMA_PAGO_MIXTO,
        ],
    }
    return render(request, 'athenas/ventas/crear.html', ctx)




@login_required
@requiere_negocio
@permission_required('AthenasApp.view_venta', raise_exception=True)
def venta_detalle(request, pk):
    neg_id = _negocio_id_from_request(request)
    venta = get_object_or_404(Venta, pk=pk, negocio_id=neg_id)
    detalles = VentaDetalle.objects.filter(venta=venta).select_related('producto')
    pagos = VentaPago.objects.filter(venta=venta)
    caja_usuario = (
        CajaUsuario.objects
        .filter(caja=venta.caja)
        .select_related("caja")
        .first()
    )
    ctx = {
        "venta": venta,
        "detalles": detalles,
        "pagos": pagos,
        "caja_usuario": caja_usuario,
    }
    return render(request, 'athenas/ventas/detalle.html', ctx)


@login_required
@requiere_negocio
@permission_required('AthenasApp.view_venta', raise_exception=True)
def venta_ticket(request, pk):
    neg_id = _negocio_id_from_request(request)
    venta = get_object_or_404(Venta, pk=pk, negocio_id=neg_id)
    detalles = VentaDetalle.objects.filter(venta=venta)
    ctx = {"venta": venta, "detalles": detalles}
    return render(request, 'athenas/ventas/ticket.html', ctx)


@login_required
@requiere_negocio
@permission_required('AthenasApp.change_venta', raise_exception=True)
def venta_anular(request, pk):
    neg_id = _negocio_id_from_request(request)
    venta = get_object_or_404(Venta, pk=pk, negocio_id=neg_id)

    if venta.estado == venta.ESTADO_ANULADA:
        messages.info(request, "La venta ya estaba anulada.")
        return redirect("venta_detalle", pk=pk)

    if venta.estado != venta.ESTADO_CONFIRMADA:
        messages.error(request, "Solo se pueden anular ventas confirmadas.")
        return redirect("venta_detalle", pk=pk)

    try:
        with transaction.atomic():
            venta.anular(request.user)  # usa el método del modelo
        messages.success(request, f"Venta {venta.numero_ticket} anulada correctamente.")

        # === Auditoría ===
        registrar_auditoria(
            request,
            accion="Venta anulada",
            entidad="Venta",
            id_registro=venta.pk
        )


    except Exception as e:
        messages.error(request, f"No se pudo anular la venta: {e}")

    return redirect("venta_detalle", pk=pk)

