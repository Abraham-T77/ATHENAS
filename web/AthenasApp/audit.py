# AthenasApp/audit.py
# ---------------------------------------------------
# Helper centralizado para registrar Auditoría en BitacoraSistema
# (para que se vea en el módulo de Bitácora)
# ---------------------------------------------------

from .models import BitacoraSistema, Usuarios

def registrar_auditoria(
    request,
    accion: str,
    entidad: str,
    id_registro: int,
    exito: bool = True,
    detalle_extra: str | None = None,
):
    """
    Registra un evento en BitacoraSistema de forma segura.

    - request: request de la view
    - accion: texto corto ("Venta confirmada", "Compra anulada", etc.)
    - entidad: nombre de la entidad ("Venta", "Compra", "Caja", etc.)
    - id_registro: id del registro afectado
    - exito: True/False por si en el futuro queremos registrar errores también
    - detalle_extra: texto opcional para agregar más info al detalle
    """

    try:
        usuario_espejo = None

        # Tus usuarios reales están en Usuarios, no en auth_user
        if getattr(request, "user", None) and hasattr(request.user, "username"):
            usuario_espejo = Usuarios.objects.filter(
                usuario=request.user.username
            ).first()

        # Texto que verá el usuario en la columna "Detalle"
        detalle = f"{entidad} #{id_registro}"
        if detalle_extra:
            detalle = f"{detalle} - {detalle_extra}"

        BitacoraSistema.objects.create(
            usuario=usuario_espejo,
            accion=accion,
            detalle=detalle,
            exito=exito,
        )

    except Exception as e:
        # Nunca debe romper el flujo del sistema
        print(f"[ERROR] No se pudo registrar auditoría en bitácora: {e}")
