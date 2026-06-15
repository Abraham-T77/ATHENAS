from django.utils.deprecation import MiddlewareMixin

class EnforceNegocioMiddleware(MiddlewareMixin):
    """
    Fuerza la sesión al negocio asignado al usuario (PerfilUsuario),
    excepto si el usuario posee el permiso 'AthenasApp.can_switch_negocio'.
    """
    def process_request(self, request):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return

        # Admin (o quien posea el permiso) puede cambiar manualmente el negocio
        if user.has_perm('AthenasApp.can_switch_negocio'):
            return

        perfil = getattr(user, 'perfil', None)
        if perfil and perfil.negocio_id:
            if request.session.get('negocio_id') != perfil.negocio_id:
                request.session['negocio_id'] = perfil.negocio_id
