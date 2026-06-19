# =========================================================
# AthenasApp/views_reportes.py
# ÉPIC 12 – Reportes, Gráficos y Exportaciones (PDF/Excel)
# =========================================================

import io
import base64
import matplotlib.pyplot as plt
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required, permission_required
from django.utils import timezone
from django.db.models import Sum, F, ExpressionWrapper, FloatField
from .utils import _negocio_id_from_request
from openpyxl import Workbook
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from AthenasApp.models import Venta, Compras, Productos, Clientes
from AthenasApp.decorators import requiere_negocio


# =========================================================
# FUNCIÓN AUXILIAR – GRÁFICOS BASE64
# =========================================================
def generar_grafico_barras(titulos, valores, titulo, color='steelblue'):
    plt.switch_backend('AGG')
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(titulos, valores, color=color)
    ax.set_title(titulo)
    ax.set_ylabel('Monto ($)')
    plt.xticks(rotation=45, ha='right')

    buffer = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    imagen_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    buffer.close()
    return imagen_base64


# =========================================================
# PANEL GENERAL DE REPORTES
# =========================================================
@login_required
@requiere_negocio
@permission_required('AthenasApp.view_venta', raise_exception=True)
def reportes_panel(request):
    hoy = timezone.now()
    mes_actual = hoy.month
    anio_actual = hoy.year
    neg_id = _negocio_id_from_request(request)

    ventas_mes = Venta.objects.filter(
        negocio_id=neg_id,
        fecha__month=mes_actual,
        fecha__year=anio_actual,
        estado=Venta.ESTADO_CONFIRMADA
    ).aggregate(total=Sum('total_neto'))['total'] or 0

    compras_mes = Compras.objects.filter(
        negocio_id=neg_id,
        fecha__month=mes_actual,
        fecha__year=anio_actual,
        estado=Compras.ESTADO_CONFIRMADA
    ).aggregate(total=Sum('total'))['total'] or 0

    productos_activos = Productos.objects.filter(activo=True, negocio_id=neg_id).count()
    clientes_activos = Clientes.objects.filter(activo=True, negocio_id=neg_id).count()

    resumen_ventas = {
        "total": Venta.objects.filter(negocio_id=neg_id).count(),
        "monto_total": ventas_mes
    }
    resumen_compras = {
        "total": Compras.objects.filter(negocio_id=neg_id).count(),
        "monto_total": compras_mes
    }
    resumen_stock = {
        "productos": productos_activos,
        "valor_total": Productos.objects.filter(negocio_id=neg_id).aggregate(
            total=Sum(ExpressionWrapper(F('stock_actual') * F('precio_venta'), output_field=FloatField()))
        )['total'] or 0
    }

    context = {
        "resumen_ventas": resumen_ventas,
        "resumen_compras": resumen_compras,
        "resumen_stock": resumen_stock,
        "titulo": "Panel General de Reportes",
    }
    return render(request, "athenas/reportes/panel_reportes.html", context)


# =========================================================
# REPORTE DE VENTAS
# =========================================================
@login_required
@requiere_negocio
@permission_required('AthenasApp.view_venta', raise_exception=True)
def reportes_ventas(request):
    desde = request.GET.get("desde")
    hasta = request.GET.get("hasta")

    neg_id = _negocio_id_from_request(request)
    ventas = Venta.objects.filter(negocio_id=neg_id).order_by("-fecha")

    if desde:
        ventas = ventas.filter(fecha__gte=desde)
    if hasta:
        ventas = ventas.filter(fecha__lte=hasta)

    # === Gráfico ===
    if ventas.exists():
        dias = [v.fecha.strftime("%d/%m") for v in ventas]
        montos = [float(v.total_neto) for v in ventas]
        grafico_ventas = generar_grafico_barras(dias, montos, "Ventas por Día", color='mediumseagreen')
    else:
        grafico_ventas = None

    return render(request, "athenas/reportes/ventas.html", {
        "ventas": ventas,
        "titulo": "Reporte de Ventas",
        "grafico": grafico_ventas,
    })


# =========================================================
# EXPORTAR PDF / EXCEL – VENTAS
# =========================================================

@login_required
@requiere_negocio
@permission_required('AthenasApp.view_venta', raise_exception=True)
def exportar_reporte_ventas_pdf(request):
    desde = request.GET.get("desde")
    hasta = request.GET.get("hasta")
    neg_id = _negocio_id_from_request(request)

    ventas = Venta.objects.filter(negocio_id=neg_id).order_by("-fecha")
    if desde: ventas = ventas.filter(fecha__gte=desde)
    if hasta: ventas = ventas.filter(fecha__lte=hasta)

    response = HttpResponse(content_type="application/pdf")
    response['Content-Disposition'] = 'attachment; filename=\"reporte_ventas.pdf\"'

    p = canvas.Canvas(response, pagesize=letter)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, 750, "Reporte de Ventas")

    p.setFont("Helvetica", 10)
    y = 720

    for v in ventas:
        p.drawString(50, y, f"{v.fecha.strftime('%d/%m/%Y')} — {v.numero_ticket} — ${v.total_neto}")
        y -= 18
        if y < 50:
            p.showPage()
            p.setFont("Helvetica", 10)
            y = 750

    p.showPage()
    p.save()
    return response


@login_required
@requiere_negocio
@permission_required('AthenasApp.view_venta', raise_exception=True)
def exportar_reporte_ventas_excel(request):
    desde = request.GET.get("desde")
    hasta = request.GET.get("hasta")
    neg_id = _negocio_id_from_request(request)

    ventas = Venta.objects.filter(negocio_id=neg_id).order_by("-fecha")
    if desde: ventas = ventas.filter(fecha__gte=desde)
    if hasta: ventas = ventas.filter(fecha__lte=hasta)

    wb = Workbook()
    ws = wb.active
    ws.title = "Ventas"

    ws.append(["Fecha", "Número", "Cliente", "Forma de Pago", "Total", "Estado"])

    for v in ventas:
        ws.append([
            v.fecha.strftime("%d/%m/%Y"),
            v.numero_ticket,
            v.cliente.nombre if v.cliente else "—",
            v.forma_pago,
            float(v.total_neto),
            v.estado,
        ])

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response['Content-Disposition'] = 'attachment; filename=\"reporte_ventas.xlsx\"'
    wb.save(response)
    return response


# =========================================================
# REPORTE DE COMPRAS
# =========================================================
@login_required
@requiere_negocio
@permission_required('AthenasApp.view_compras', raise_exception=True)
def reportes_compras(request):
    desde = request.GET.get("desde")
    hasta = request.GET.get("hasta")
    neg_id = _negocio_id_from_request(request)

    compras = Compras.objects.filter(negocio_id=neg_id).order_by("-fecha")
    if desde: compras = compras.filter(fecha__gte=desde)
    if hasta: compras = compras.filter(fecha__lte=hasta)

    if compras.exists():
        dias = [c.fecha.strftime("%d/%m") for c in compras]
        montos = [float(c.total) for c in compras]
        grafico_compras = generar_grafico_barras(dias, montos, "Compras por Día", color='cornflowerblue')
    else:
        grafico_compras = None

    return render(request, "athenas/reportes/compras.html", {
        "compras": compras,
        "titulo": "Reporte de Compras",
        "grafico": grafico_compras,
    })


# =========================================================
# EXPORTAR PDF / EXCEL – COMPRAS
# =========================================================

@login_required
@requiere_negocio
@permission_required('AthenasApp.view_compras', raise_exception=True)
def exportar_reporte_compras_pdf(request):
    desde = request.GET.get("desde")
    hasta = request.GET.get("hasta")
    neg_id = _negocio_id_from_request(request)

    compras = Compras.objects.filter(negocio_id=neg_id).order_by("-fecha")
    if desde: compras = compras.filter(fecha__gte=desde)
    if hasta: compras = compras.filter(fecha__lte=hasta)

    response = HttpResponse(content_type="application/pdf")
    response['Content-Disposition'] = 'attachment; filename=\"reporte_compras.pdf\"'

    p = canvas.Canvas(response, pagesize=letter)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, 750, "Reporte de Compras")

    y = 720
    p.setFont("Helvetica", 10)

    for c in compras:
        p.drawString(50, y, f"{c.fecha.strftime('%d/%m/%Y')} — {c.proveedor.razon_social} — ${c.total}")
        y -= 18
        if y < 50:
            p.showPage()
            y = 750

    p.showPage()
    p.save()
    return response


@login_required
@requiere_negocio
@permission_required('AthenasApp.view_compras', raise_exception=True)
def exportar_reporte_compras_excel(request):
    desde = request.GET.get("desde")
    hasta = request.GET.get("hasta")
    neg_id = _negocio_id_from_request(request)

    compras = Compras.objects.filter(negocio_id=neg_id).order_by("-fecha")
    if desde: compras = compras.filter(fecha__gte=desde)
    if hasta: compras = compras.filter(fecha__lte=hasta)

    wb = Workbook()
    ws = wb.active
    ws.title = "Compras"

    ws.append(["Fecha", "Proveedor", "Forma de Pago", "Total", "Estado"])

    for c in compras:
        ws.append([
            c.fecha.strftime("%d/%m/%Y"),
            c.proveedor.razon_social if c.proveedor else "—",
            c.forma_pago,
            float(c.total),
            c.estado,
        ])

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response['Content-Disposition'] = 'attachment; filename=\"reporte_compras.xlsx\"'
    wb.save(response)
    return response


# =========================================================
# REPORTE DE STOCK
# =========================================================
@login_required
@requiere_negocio
@permission_required('AthenasApp.view_productos', raise_exception=True)
def reportes_stock(request):
    buscar = request.GET.get("buscar")
    neg_id = _negocio_id_from_request(request)
    productos = Productos.objects.filter(activo=True, negocio_id=neg_id)

    if buscar:
        productos = productos.filter(descripcion__icontains=buscar)

    # Valor total de cada producto
    productos = productos.annotate(
        valor_total=ExpressionWrapper(
            F('stock_actual') * F('precio_venta'),
            output_field=FloatField()
        )
    )

    if productos.exists():
        nombres = [p.descripcion for p in productos]
        stocks = [p.stock_actual for p in productos]
        grafico_stock = generar_grafico_barras(nombres, stocks, "Stock por Producto", color='orange')
    else:
        grafico_stock = None

    return render(request, "athenas/reportes/stock.html", {
        "productos": productos,
        "titulo": "Reporte de Stock",
        "grafico": grafico_stock,
    })


# =========================================================
# EXPORTAR PDF / EXCEL – STOCK
# =========================================================

@login_required
@requiere_negocio
@permission_required('AthenasApp.view_productos', raise_exception=True)
def exportar_reporte_stock_pdf(request):
    buscar = request.GET.get("buscar")
    neg_id = _negocio_id_from_request(request)
    productos = Productos.objects.filter(activo=True, negocio_id=neg_id)

    if buscar:
        productos = productos.filter(descripcion__icontains=buscar)

    productos = productos.annotate(
        valor_total=ExpressionWrapper(
            F('stock_actual') * F('precio_venta'),
            output_field=FloatField()
        )
    )

    response = HttpResponse(content_type="application/pdf")
    response['Content-Disposition'] = 'attachment; filename=\"reporte_stock.pdf\"'

    p = canvas.Canvas(response, pagesize=letter)
    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, 750, "Reporte de Stock")

    y = 720
    p.setFont("Helvetica", 10)

    for prod in productos:
        p.drawString(
            50, y,
            f"{prod.descripcion} — {prod.stock_actual} unidades — ${prod.precio_venta} — Total: ${prod.valor_total}"
        )
        y -= 18
        if y < 50:
            p.showPage()
            y = 750

    p.showPage()
    p.save()
    return response


@login_required
@requiere_negocio
@permission_required('AthenasApp.view_productos', raise_exception=True)
def exportar_reporte_stock_excel(request):
    buscar = request.GET.get("buscar")
    neg_id = _negocio_id_from_request(request)
    productos = Productos.objects.filter(activo=True, negocio_id=neg_id)

    if buscar:
        productos = productos.filter(descripcion__icontains=buscar)

    productos = productos.annotate(
        valor_total=ExpressionWrapper(
            F('stock_actual') * F('precio_venta'),
            output_field=FloatField()
        )
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Stock"

    ws.append(["Producto", "Categoría", "Stock Actual", "Stock Mínimo", "Precio Venta", "Valor Total"])

    for p in productos:
        ws.append([
            p.descripcion,
            p.categoria.nombre if p.categoria else "—",
            p.stock_actual,
            p.stock_minimo,
            float(p.precio_venta),
            float(p.valor_total),
        ])

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response['Content-Disposition'] = 'attachment; filename=\"reporte_stock.xlsx\"'
    wb.save(response)
    return response
