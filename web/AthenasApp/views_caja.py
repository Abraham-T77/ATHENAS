# =========================
# VIEWS - CAJA
# =========================
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.utils import timezone

from .models import Caja, CajaUsuario, MovimientoCaja, LogAuditoria
from .utils import _negocio_id_from_request, get_usuario_from_request
from .audit import registrar_auditoria
from .decorators import requiere_negocio


# =========================
# LISTA DE CAJAS
# =========================
@login_required
@requiere_negocio
@permission_required("AthenasApp.view_caja", raise_exception=True)
def caja_lista(request):
    neg_id = _negocio_id_from_request(request)
    cajas = Caja.objects.filter(negocio_id=neg_id).order_by("-fecha_apertura")
    return render(request, "athenas/caja/caja_lista.html", {"items": cajas})


# =========================
# APERTURA DE CAJA
# =========================
@login_required
@requiere_negocio
@permission_required("AthenasApp.can_open_caja", raise_exception=True)
def caja_apertura(request):
    usuario = get_usuario_from_request(request)
    neg_id = _negocio_id_from_request(request)

    if request.method == "POST":
        saldo_inicial_raw = request.POST.get("saldo_inicial") or "0"
        try:
            saldo_inicial = float(saldo_inicial_raw.replace(",", "."))
        except ValueError:
            messages.error(request, "Saldo inicial inválido.")
            return redirect("caja_apertura")

        with transaction.atomic():
            caja = Caja.objects.create(
                negocio_id=neg_id,
                estado="ABIERTA",
                fecha_apertura=timezone.now(),
                saldo_inicial=saldo_inicial,
                saldo_final=saldo_inicial,
            )

            CajaUsuario.objects.create(
                caja=caja,
                usuario=usuario,
                fecha_apertura=timezone.now(),
                estado="ABIERTA",
                saldo_inicial=saldo_inicial,
                saldo_final=saldo_inicial,
            )

            registrar_auditoria(
                request,
                accion="Apertura de caja",
                entidad="Caja",
                id_registro=caja.pk
            )


            messages.success(request, "Caja abierta correctamente.")
            return redirect("caja_lista")

    return render(request, "athenas/caja/abrir.html")


# =========================
# CIERRE DE CAJA
# =========================
@login_required
@requiere_negocio
@permission_required("AthenasApp.can_close_caja", raise_exception=True)
def caja_cierre(request, pk):
    usuario = get_usuario_from_request(request)
    neg_id = _negocio_id_from_request(request)
    caja = get_object_or_404(Caja, pk=pk, negocio_id=neg_id)

    # Si ya está cerrada, avisamos y volvemos al detalle
    if caja.estado != "ABIERTA" and request.method == "GET":
        messages.info(request, f"La caja #{caja.pk} no está ABIERTA (estado actual: {caja.estado}).")
        return redirect("caja_detalle", pk=caja.pk)

    if request.method == "POST":
        with transaction.atomic():
            caja.estado = "CERRADA"
            caja.fecha_cierre = timezone.now()
            caja.saldo_final = caja.calcular_saldo()
            caja.save()

            caja_usuario = (
                CajaUsuario.objects
                .filter(caja=caja, usuario=usuario)
                .order_by("-fecha_apertura")
                .first()
            )
            if caja_usuario:
                caja_usuario.estado = "CERRADA"
                caja_usuario.fecha_cierre = timezone.now()
                caja_usuario.saldo_final = caja.saldo_final
                caja_usuario.save()

            registrar_auditoria(
                request,
                accion="Cierre de caja",
                entidad="Caja",
                id_registro=caja.pk
            )


            messages.success(request, "Caja cerrada correctamente.")
            return redirect("caja_lista")

    return render(request, "athenas/caja/cerrar.html", {"caja": caja})


# =========================
# DETALLE DE CAJA
# =========================
@login_required
@requiere_negocio
@permission_required("AthenasApp.view_caja", raise_exception=True)
def caja_detalle(request, pk):
    neg_id = _negocio_id_from_request(request)
    caja = get_object_or_404(Caja, pk=pk, negocio_id=neg_id)

    movimientos = (
        MovimientoCaja.objects
        .filter(caja_usuario__caja=caja)
        .order_by("-fecha")
    )

    ctx = {
        "caja": caja,
        "movimientos": movimientos,
        "saldo_calculado": caja.calcular_saldo(),
    }
    return render(request, "athenas/caja/caja_detalle.html", ctx)


# =========================
# ESTADO DE CAJA (por usuario)
# =========================
@login_required
@requiere_negocio
@permission_required("AthenasApp.view_caja", raise_exception=True)
def caja_estado(request):
    usuario = get_usuario_from_request(request)
    neg_id = _negocio_id_from_request(request)

    caja_usuario = (
        CajaUsuario.objects
        .filter(usuario=usuario, caja__negocio_id=neg_id)
        .select_related("caja")
        .order_by("-fecha_apertura")
        .first()
    )

    if not caja_usuario:
        messages.warning(request, "No tenés cajas asociadas.")
        return redirect("caja_lista")

    movimientos = (
        MovimientoCaja.objects
        .filter(caja_usuario=caja_usuario)
        .order_by("-fecha")
    )

    ctx = {
        "caja_usuario": caja_usuario,
        "caja_activa": caja_usuario,   # 👈 alias para que el template no rompa
        "movimientos": movimientos,
        "saldo_calculado": caja_usuario.caja.calcular_saldo(),
    }
    return render(request, "athenas/caja/estado.html", ctx)



# =========================
# ARQUEO DE CAJA
# =========================
@login_required
@requiere_negocio
@permission_required("AthenasApp.view_caja", raise_exception=True)
def caja_arqueo(request):
    usuario = get_usuario_from_request(request)
    neg_id = _negocio_id_from_request(request)

    caja_activa = (
        CajaUsuario.objects
        .filter(usuario=usuario, estado="ABIERTA", caja__negocio_id=neg_id)
        .select_related("caja")
        .first()
    )

    # Denominaciones (solo billetes, ARS – Argentina)
    denominaciones = [20000, 10000, 2000, 1000, 500, 200, 100, 50, 20, 10]

    if not caja_activa:
        # Mostramos la pantalla pero indicando que no hay caja abierta
        return render(
            request,
            "athenas/caja/arqueo.html",
            {"caja_activa": None, "denominaciones": denominaciones},
        )

    if request.method == "POST":
        total = 0
        for den in denominaciones:
            raw = request.POST.get(f"den_{den}", "0")
            try:
                cant = int(raw)
            except ValueError:
                cant = 0
            total += den * cant

        MovimientoCaja.objects.create(
            caja_usuario=caja_activa,
            tipo="ARQUEO",
            monto=total,
            motivo="Arqueo de caja",
            fecha=timezone.now(),
        )

        # Auditoría
        registrar_auditoria(
            request,
            accion="Arqueo de caja",
            entidad="Caja",
            id_registro=caja_activa.caja.pk
        )


        messages.success(request, f"Arqueo registrado por ${total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        return redirect("caja_estado")

    return render(
        request,
        "athenas/caja/arqueo.html",
        {"caja_activa": caja_activa, "denominaciones": denominaciones},
    )
