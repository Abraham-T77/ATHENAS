# AthenasApp/utils.py
from django.utils import timezone

def _negocio_id_from_request(request):
    """
    Devuelve el id de negocio activo para la request.
    Prioriza la sesión; si no existe, intenta con el perfil del usuario.
    """
    nid = request.session.get("negocio_id")
    if nid:
        return nid

    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        perfil = getattr(user, "perfil", None)
        if perfil and getattr(perfil, "negocio_id", None):
            return perfil.negocio_id

    return None


def get_usuario_from_request(request):
    """
    Devuelve la fila espejo en AthenasApp.Usuarios del usuario autenticado.
    Si no existe espejo, retorna None (y las vistas deberán manejarlo).
    Importamos adentro para evitar ciclos de import.
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return None

    try:
        from .models import Usuarios  # import interno para evitar ciclos
        return Usuarios.objects.filter(usuario=user.username).first()
    except Exception:
        return None


def now_local():
    """Atajo para timestamp local (si en algún punto lo necesitás)."""
    return timezone.localtime(timezone.now())



# =========================================================
# UTILIDADES PR-4 (Reportes, Alertas, Respaldos)
# =========================================================
import os
from django.conf import settings
import csv

def exportar_respaldo_csv(modelo, nombre_archivo="respaldo.csv"):
    """
    Genera un respaldo CSV de cualquier queryset o modelo.
    Ejemplo de uso:
        exportar_respaldo_csv(Clientes, "clientes_backup.csv")
    """
    ruta = os.path.join(settings.BASE_DIR, "respaldos", nombre_archivo)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    campos = [f.name for f in modelo._meta.fields]
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(campos)
        for obj in modelo.objects.all():
            writer.writerow([getattr(obj, campo) for campo in campos])
    return ruta


def generar_reporte_datos(queryset, campos):
    """
    Convierte un queryset a una lista de diccionarios filtrando los campos deseados.
    Se usa como backend para matplotlib/pandas.
    """
    return [
        {campo: getattr(obj, campo) for campo in campos}
        for obj in queryset
    ]
