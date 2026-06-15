from .models import TipoNegocio

def negocio_actual(request):
    nid = request.session.get('negocio_id')
    negocio = None
    if nid:
        negocio = TipoNegocio.objects.filter(pk=nid).first()
    return {'NEGOCIO_ACTUAL': negocio}
