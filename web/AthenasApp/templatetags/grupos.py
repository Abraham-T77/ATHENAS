from django import template

register = template.Library()

@register.filter(name='has_group')
def has_group(user, group_name):
    """
    Devuelve True si el usuario pertenece al grupo con nombre `group_name`.
    Uso en templates: {% if user|has_group:"administrador" %} ... {% endif %}
    """
    if not hasattr(user, "is_authenticated") or not user.is_authenticated:
        return False
    return user.groups.filter(name=group_name).exists()
