from functools import wraps
from django.shortcuts import redirect

def requiere_negocio(view_func):
    """
    Exige que exista request.session['negocio_id'].
    Si no hay negocio seleccionado, redirige a 'seleccionar_negocio'.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.session.get('negocio_id'):
            return redirect('seleccionar_negocio')
        return view_func(request, *args, **kwargs)
    return _wrapped
