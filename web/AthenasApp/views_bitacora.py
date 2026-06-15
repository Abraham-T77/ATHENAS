# =========================================================
# AthenasApp/views_bitacora.py – FINAL DEFINITIVO
# =========================================================

import csv
from datetime import datetime

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from django.contrib.auth.decorators import login_required, permission_required

from openpyxl import Workbook
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

from AthenasApp.models import BitacoraSistema
from AthenasApp.decorators import requiere_negocio



# =========================================================
# PANEL PRINCIPAL
# =========================================================
@login_required
@requiere_negocio
@permission_required("AthenasApp.view_bitacorasistema", raise_exception=True)
def bitacora_panel(request):

    total_registros = BitacoraSistema.objects.count()
    ultimo_evento = BitacoraSistema.objects.order_by("-fecha").first()

    context = {
        "total_registros": total_registros,
        "ultimo_evento": ultimo_evento,
        "titulo": "Bitácora del Sistema",
    }
    return render(request, "athenas/bitacora/panel_bitacora.html", context)


# =========================================================
# LISTA + FILTROS
# =========================================================
@login_required
@requiere_negocio
@permission_required("AthenasApp.view_bitacorasistema", raise_exception=True)
def bitacora_lista(request):

    registros = BitacoraSistema.objects.all().order_by("-fecha")

    usuario = (request.GET.get("usuario") or "").strip()
    desde = (request.GET.get("desde") or "").strip()
    hasta = (request.GET.get("hasta") or "").strip()

    # --- FILTRO POR USUARIO (tu modelo usa usuario.usuario) ---
    if usuario:
        registros = registros.filter(usuario__usuario__icontains=usuario)

    # --- FILTRO POR FECHA ---
    if desde:
        try:
            desde_date = datetime.strptime(desde, "%Y-%m-%d").date()
            registros = registros.filter(fecha__date__gte=desde_date)
        except ValueError:
            pass

    if hasta:
        try:
            hasta_date = datetime.strptime(hasta, "%Y-%m-%d").date()
            registros = registros.filter(fecha__date__lte=hasta_date)
        except ValueError:
            pass

    context = {
        "registros": registros[:500],
        "titulo": "Registros de Bitácora",
    }
    return render(request, "athenas/bitacora/lista_bitacora.html", context)


# =========================================================
# DETALLE
# =========================================================
@login_required
@requiere_negocio
@permission_required("AthenasApp.view_bitacorasistema", raise_exception=True)
def bitacora_detalle(request, id_log):

    log = get_object_or_404(BitacoraSistema, pk=id_log)

    context = {
        "log": log,
        "titulo": "Detalle de Registro de Bitácora",
    }
    return render(request, "athenas/bitacora/detalle_bitacora.html", context)


# =========================================================
# EXPORTAR CSV
# =========================================================
@login_required
@requiere_negocio
@permission_required("AthenasApp.view_bitacorasistema", raise_exception=True)
def exportar_bitacora_csv(request):

    fecha_actual = timezone.now().strftime("%Y%m%d_%H%M%S")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="bitacora_{fecha_actual}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow(["Fecha y Hora", "Usuario", "Acción", "Detalle", "Resultado"])

    for log in BitacoraSistema.objects.all().order_by("-fecha"):
        writer.writerow([
            log.fecha.strftime("%d/%m/%Y %H:%M:%S"),
            getattr(log.usuario, "usuario", "—"),
            log.accion,
            log.detalle or "",
            "Éxito" if log.exito else "Error",
        ])

    return response


# =========================================================
# EXPORTAR PDF
# =========================================================
@login_required
@requiere_negocio
@permission_required("AthenasApp.view_bitacorasistema", raise_exception=True)
def exportar_bitacora_pdf(request):

    fecha_actual = timezone.now().strftime("%Y%m%d_%H%M%S")

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="bitacora_{fecha_actual}.pdf"'
    )

    p = canvas.Canvas(response, pagesize=letter)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, 750, "Reporte de Bitácora del Sistema")

    y = 720
    p.setFont("Helvetica", 10)

    for log in BitacoraSistema.objects.all().order_by("-fecha"):

        linea = (
            f"{log.fecha.strftime('%d/%m/%Y %H:%M')} — "
            f"{getattr(log.usuario, 'usuario', '—')} — "
            f"{log.accion}"
        )

        p.drawString(50, y, linea)
        y -= 16

        if y < 50:
            p.showPage()
            p.setFont("Helvetica", 10)
            y = 750

    p.showPage()
    p.save()
    return response


# =========================================================
# EXPORTAR EXCEL
# =========================================================
@login_required
@requiere_negocio
@permission_required("AthenasApp.view_bitacorasistema", raise_exception=True)
def exportar_bitacora_excel(request):

    fecha_actual = timezone.now().strftime("%Y%m%d_%H%M%S")

    wb = Workbook()
    ws = wb.active
    ws.title = "Bitácora"

    ws.append(["Fecha y Hora", "Usuario", "Acción", "Detalle", "Resultado"])

    for log in BitacoraSistema.objects.all().order_by("-fecha"):
        ws.append([
            log.fecha.strftime("%d/%m/%Y %H:%M:%S"),
            getattr(log.usuario, "usuario", "—"),
            log.accion,
            log.detalle or "",
            "Éxito" if log.exito else "Error",
        ])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="bitacora_{fecha_actual}.xlsx"'

    wb.save(response)
    return response
