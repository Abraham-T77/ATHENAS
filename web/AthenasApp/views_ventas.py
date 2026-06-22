# AthenasApp/views_ventas.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction, models
from django.utils import timezone
from django.urls import reverse
from decimal import Decimal, InvalidOperation

from AthenasApp.audit import registrar_auditoria


from .models import (
    TipoNegocio, Usuarios, Productos, Clientes,
    Venta, VentaDetalle, VentaPago, MovimientoCaja, MovimientoStock, CajaUsuario,
    LogAuditoria
)
from .decorators import requiere_negocio

FORMA_PAGO_EFECTIVO = Venta.FP_EFECTIVO
FORMA_PAGO_TARJETA = Venta.FP_TARJETA
FORMA_PAGO_TRANSFERENCIA = Venta.FP_TRANSFERENCIA
FORMA_PAGO_MIXTO = Venta.FP_MIXTO

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
          .select_related("cliente")
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
        "estados": Venta.ESTADOS,
        "formas_pago": Venta.FORMAS_PAGO,
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
        if forma_pago not in [FORMA_PAGO_EFECTIVO, FORMA_PAGO_TARJETA, FORMA_PAGO_TRANSFERENCIA, FORMA_PAGO_MIXTO]:
            forma_pago = FORMA_PAGO_EFECTIVO
        cliente_id = request.POST.get('cliente_id') or None
        desc_global_pct = request.POST.get('descuento_global_pct') or ""

        # Normalizar descuento global
        try:
            descuento_global_pct = (
                Decimal(desc_global_pct.replace(',', '.')) if desc_global_pct else None
            )
        except (InvalidOperation, AttributeError):
            messages.error(request, "El descuento global no es válido.")
            return redirect('venta_nueva')
        if descuento_global_pct is not None and not (Decimal("0") <= descuento_global_pct <= Decimal("100")):
            messages.error(request, "El descuento global debe estar entre 0 y 100.")
            return redirect('venta_nueva')

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
                pu = Decimal((precios[i] or '0').replace(',', '.'))
                di = Decimal((descs[i] or '').replace(',', '.')) if (i < len(descs) and descs[i]) else None
            except (ValueError, InvalidOperation, AttributeError, IndexError):
                messages.error(request, "El carrito contiene datos inválidos.")
                return redirect('venta_nueva')
            if pid <= 0 or cant <= 0 or pu < 0:
                messages.error(request, "El carrito contiene productos, cantidades o precios inválidos.")
                return redirect('venta_nueva')
            if di is not None and not (Decimal("0") <= di <= Decimal("100")):
                messages.error(request, "El descuento por ítem debe estar entre 0 y 100.")
                return redirect('venta_nueva')
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
            cantidades_por_producto = {}
            for pid, cant, _pu, _di in items:
                cantidades_por_producto[pid] = cantidades_por_producto.get(pid, 0) + cant

            for pid, cantidad_total in cantidades_por_producto.items():
                prod = prods_map.get(pid)
                if not prod:
                    transaction.set_rollback(True)
                    messages.error(
                        request,
                        f"Producto ID {pid} no existe en el negocio actual."
                    )
                    return redirect('venta_nueva')
                if prod.stock_actual < cantidad_total:
                    transaction.set_rollback(True)
                    messages.error(
                        request,
                        f"Sin stock suficiente para '{prod.descripcion}'. Stock disponible: {prod.stock_actual}."
                    )
                    return redirect('venta_nueva')

            total_bruto = 0
            lineas_ok = []
            for pid, cant, pu, di in items:
                prod = prods_map.get(pid)

                precio_aplicado = pu
                if di is not None:
                    precio_aplicado = (pu * (Decimal("1") - di / Decimal("100"))).quantize(Decimal("0.01"))

                subtotal = (Decimal(cant) * precio_aplicado).quantize(Decimal("0.01"))
                total_bruto += subtotal
                lineas_ok.append((prod, cant, pu, di, subtotal))

            total_neto = total_bruto
            if descuento_global_pct is not None:
                total_neto = (total_bruto * (Decimal("1") - descuento_global_pct / Decimal("100"))).quantize(Decimal("0.01"))

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
                        monto = Decimal(raw.replace(',', '.')) if raw else Decimal("0")
                    except (InvalidOperation, AttributeError):
                        monto = Decimal("0")
                    if monto > 0:
                        metodo = key.replace('pago_', '').upper()
                        partes.append((metodo, monto))

                if not partes:
                    transaction.set_rollback(True)
                    messages.error(
                        request,
                        "Forma de pago Mixto requiere al menos un monto válido."
                    )
                    return redirect('venta_nueva')

                suma = sum((m for _, m in partes), Decimal("0")).quantize(Decimal("0.01"))
                if suma != total_neto:
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
    venta = get_object_or_404(
        Venta.objects.select_related("negocio", "cliente"),
        pk=pk,
        negocio_id=neg_id,
    )
    detalles = VentaDetalle.objects.filter(venta=venta)
    pagos = VentaPago.objects.filter(venta=venta)
    ctx = {"venta": venta, "detalles": detalles, "pagos": pagos}
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

