from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.signals import user_logged_in, user_logged_out

from .models import (
    TipoNegocio, Roles, Usuarios, PerfilUsuario, Caja, CajaUsuario,
    Clientes, Proveedores, Productos, Venta, VentaDetalle, VentaPago,
    Compras, DetalleCompras, PagoClientes, MovimientoCaja, MovimientoStock, LogAuditoria
)

from .audit import registrar_auditoria

def _perms_for(model_cls, acciones=('add','change','delete','view')):
    ct = ContentType.objects.get_for_model(model_cls)
    codenames = [f"{a}_{model_cls._meta.model_name}" for a in acciones]
    return Permission.objects.filter(content_type=ct, codename__in=codenames)

@receiver(post_migrate)
def crear_grupos_roles_permisos(sender, **kwargs):
    # Grupos
    g_admin, _ = Group.objects.get_or_create(name='administrador')
    g_enc, _   = Group.objects.get_or_create(name='encargado')
    g_caja, _  = Group.objects.get_or_create(name='caja')
    g_rep, _   = Group.objects.get_or_create(name='repositor')

    # Roles (tabla dominio)
    for desc in ['administrador', 'encargado', 'caja', 'repositor']:
        Roles.objects.get_or_create(descripcion=desc)

    # Permisos por grupo
    MODELOS_TODOS = [
        TipoNegocio, Roles, Usuarios, Caja, CajaUsuario, Clientes, Proveedores,
        Productos, Venta, VentaDetalle, VentaPago,
        Compras, DetalleCompras, PagoClientes, MovimientoCaja, MovimientoStock, LogAuditoria
    ]
    for m in MODELOS_TODOS:
        g_admin.permissions.add(*_perms_for(m, ('add','change','delete','view')))

    ENC_FULL = [
        Productos, Clientes, Proveedores, Compras, DetalleCompras,
        Venta, VentaDetalle, VentaPago, Caja, CajaUsuario, MovimientoCaja,
        MovimientoStock, PagoClientes
    ]
    for m in ENC_FULL:
        g_enc.permissions.add(*_perms_for(m, ('add','change','delete','view')))
        g_enc.permissions.add(*_perms_for(TipoNegocio, ('view',)))
        g_enc.permissions.add(*_perms_for(LogAuditoria, ('view',)))

    CAJA_ACV = [Venta, VentaDetalle, VentaPago, Caja, CajaUsuario, PagoClientes, Clientes]
    for m in CAJA_ACV:
        g_caja.permissions.add(*_perms_for(m, ('add','change','view')))
    for m in [Productos, Proveedores, Compras, DetalleCompras, MovimientoStock, TipoNegocio]:
        g_caja.permissions.add(*_perms_for(m, ('view',)))
        g_rep.permissions.add(*_perms_for(Productos, ('view',)))
        g_rep.permissions.add(*_perms_for(MovimientoStock, ('add','view')))
    for m in [Compras, DetalleCompras, Clientes, Proveedores, TipoNegocio]:
        g_rep.permissions.add(*_perms_for(m, ('view',)))

    # Permiso: sólo admin puede cambiar negocio
    ct = ContentType.objects.get_for_model(PerfilUsuario)
    perm, _ = Permission.objects.get_or_create(
        content_type=ct,
        codename='can_switch_negocio',
        defaults={'name': 'Puede cambiar/seleccionar el negocio actual'}
    )
    g_admin.permissions.add(perm)

    # Semillas de negocios
    for det in ["Despensa Athenas", "Vinería Athenas"]:
        TipoNegocio.objects.get_or_create(detalle=det)

@receiver(post_save, sender=User)
def crear_perfil_usuario_y_espejo(sender, instance: User, created, **kwargs):
    # Crear perfil si no existe (negocio por defecto; luego el admin lo define al crear usuarios)
    perfil, _ = PerfilUsuario.objects.get_or_create(
        user=instance,
        defaults={'negocio': TipoNegocio.objects.first()}
    )

    # Resolver SIEMPRE un rol no nulo
    if instance.is_superuser:
        rol, _ = Roles.objects.get_or_create(descripcion='administrador')
    else:
        grupo = instance.groups.first()
        if grupo:
            rol, _ = Roles.objects.get_or_create(descripcion=grupo.name.lower())
        else:
            rol, _ = Roles.objects.get_or_create(descripcion='encargado')

    nombre = (f"{instance.first_name} {instance.last_name}").strip() or instance.username

    # Sincronizar espejo (rol NUNCA NULL)
    Usuarios.objects.update_or_create(
        usuario=instance.username,
        defaults={
            "nombre": nombre,
            "contrasenia": instance.password,  # hash Django
            "rol": rol,
            "negocio": perfil.negocio,
        }
    )


@receiver(post_save, sender=PerfilUsuario)
def sincronizar_espejo_usuarios(sender, instance: PerfilUsuario, **kwargs):
    Usuarios.objects.filter(usuario=instance.user.username).update(negocio=instance.negocio)

@receiver(user_logged_in)
def setear_negocio_en_login(sender, user: User, request, **kwargs):
    # Setear negocio en sesión (ya lo tenías)
    if hasattr(user, 'perfil') and user.perfil.negocio_id:
        request.session['negocio_id'] = user.perfil.negocio_id

    # Registrar auditoría de INICIO DE SESIÓN
    try:
        # Buscamos el espejo en Usuarios (por si lo querés usar como id_registro)
        usuario_espejo = Usuarios.objects.filter(usuario=user.username).first()
        if usuario_espejo:
            registrar_auditoria(
                request,
                accion="Login",
                entidad="Usuario",
                id_registro=usuario_espejo.pk,
            )
    except Exception as e:
        print(f"[AUDIT] Error registrando login: {e}")


@receiver(user_logged_out)
def auditar_logout(sender, request, user: User, **kwargs):
    """
    Registra en LogAuditoria el cierre de sesión del usuario.
    """
    try:
        usuario_espejo = Usuarios.objects.filter(usuario=user.username).first()
        if usuario_espejo:
            registrar_auditoria(
                request,
                accion="Logout",
                entidad="Usuario",
                id_registro=usuario_espejo.pk,
            )
    except Exception as e:
        print(f"[AUDIT] Error registrando logout: {e}")

