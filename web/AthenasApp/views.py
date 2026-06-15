# AthenasApp/views.py

from django.contrib.auth.decorators import login_required, user_passes_test, permission_required
from django.contrib.auth import logout
from django.views.decorators.http import require_http_methods
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse

# CBVs y permisos
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy

# Extras para usuarios y búsquedas
from django.contrib.auth.models import User
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden

from .models import (
    TipoNegocio, Productos, Clientes, Proveedores,
    Categoria, Marca, UnidadMedida
)
from .audit import registrar_auditoria

from .forms import CrearUsuarioForm, ClienteForm, ProveedorForm, UsuarioEditForm, ProductoForm, CategoriaForm, MarcaForm, UnidadMedidaForm
from .decorators import requiere_negocio
from django.utils.decorators import method_decorator



# ===== Helpers de grupo (roles) =====
def es_admin(u): return u.is_superuser or u.groups.filter(name='administrador').exists()
def es_encargado(u): return u.groups.filter(name='encargado').exists()
def es_caja(u): return u.groups.filter(name='caja').exists()
def es_repositor(u): return u.groups.filter(name='repositor').exists()


# ===== Logout =====
@require_http_methods(["POST", "GET"])
def salir(request):
    """
    Cierra la sesión y redirige al login.
    Acepta POST (recomendado) y GET (por si navegas con enlace).
    """
    logout(request)
    messages.info(request, "Sesión cerrada correctamente.")
    return redirect('login')


# ===== Selección de negocio =====
@login_required
@permission_required('AthenasApp.can_switch_negocio', raise_exception=True)
def seleccionar_negocio(request):
    if request.method == 'POST':
        nid = request.POST.get('negocio_id')
        if TipoNegocio.objects.filter(pk=nid).exists():
            request.session['negocio_id'] = int(nid)
            messages.success(request, 'Negocio seleccionado correctamente.')
            return redirect('dashboard')
        messages.error(request, 'Negocio inválido.')
    negocios = TipoNegocio.objects.all()
    return render(request, 'athenas/seleccionar_negocio.html', {'negocios': negocios})


# ===== Dashboard según rol =====
@login_required
def dashboard(request):
    if not request.session.get('negocio_id'):
        return redirect('seleccionar_negocio')

    u = request.user
    if es_admin(u): tpl = 'athenas/dashboard_admin.html'
    elif es_encargado(u): tpl = 'athenas/dashboard_encargado.html'
    elif es_caja(u): tpl = 'athenas/dashboard_caja.html'
    elif es_repositor(u): tpl = 'athenas/dashboard_repositor.html'
    else:
        messages.error(request, 'Tu usuario no posee un rol asignado.')
        return redirect('logout')
    return render(request, tpl)


# ======================================================================
# ======================= PRODUCTOS (ÉPIC 3) ============================
# ======================================================================

# app_label/model_name para permisos dinámicos
APP_PROD = Productos._meta.app_label
MN_PROD = Productos._meta.model_name  # "productos"

# Permisos dinámicos para Catálogo
APP_CAT, MN_CAT = Categoria._meta.app_label, Categoria._meta.model_name      # add_categoria
APP_MAR, MN_MAR = Marca._meta.app_label, Marca._meta.model_name              # add_marca
APP_UNI, MN_UNI = UnidadMedida._meta.app_label, UnidadMedida._meta.model_name  # add_unidadmedida



def _negocio_id_actual(request):
    """Obtiene el id de negocio activo desde sesión."""
    return request.session.get('negocio_id')


@login_required
@requiere_negocio
@permission_required(f'{APP_PROD}.view_{MN_PROD}', raise_exception=True)
def productos_lista(request):
    """
    Listado con filtros, paginación y solo datos del negocio activo.
    """
    neg_id = _negocio_id_actual(request)
    if not neg_id:
        return HttpResponseForbidden("Debe seleccionar un negocio.")

    qs = Productos.objects.filter(negocio_id=neg_id).select_related("categoria", "marca", "unidad")

    # Filtros
    q = (request.GET.get("q") or "").strip()
    cat = request.GET.get("cat")
    mar = request.GET.get("mar")
    activo = request.GET.get("activo")  # 'S' | 'N' | None

    if q:
        qs = qs.filter(
            Q(descripcion__icontains=q) |
            Q(codigo_barra__icontains=q) |
            Q(sku__icontains=q)
        )
    if cat:
        qs = qs.filter(categoria_id=cat)
    if mar:
        qs = qs.filter(marca_id=mar)
    if activo in ("S", "N"):
        qs = qs.filter(activo=(activo == "S"))

    qs = qs.order_by("descripcion")

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    categorias = Categoria.objects.filter(negocio_id=neg_id).order_by("nombre")
    marcas = Marca.objects.filter(negocio_id=neg_id).order_by("nombre")

    return render(request, 'athenas/productos/lista.html', {
        "page_obj": page_obj,
        "q": q,
        "cat_sel": cat,
        "mar_sel": mar,
        "activo_sel": activo,
        "categorias": categorias,
        "marcas": marcas,
    })


@login_required
@requiere_negocio
@permission_required(f'{APP_PROD}.add_{MN_PROD}', raise_exception=True)
def productos_crear(request):
    """
    Alta de producto. El negocio se fuerza al negocio activo.
    """
    neg_id = _negocio_id_actual(request)
    if not neg_id:
        return HttpResponseForbidden("Debe seleccionar un negocio.")

    if request.method == "POST":
        form = ProductoForm(request.POST, request=request)
        if form.is_valid():
            prod = form.save(commit=False)
            prod.negocio_id = neg_id
            prod.save()
            messages.success(request, "Producto creado correctamente.")
            return redirect('productos_lista')
        messages.error(request, "Revisá los errores del formulario.")
    else:
        form = ProductoForm(request=request)

    return render(request, 'athenas/productos/crear.html', {"form": form})


@login_required
@requiere_negocio
@permission_required(f'{APP_PROD}.change_{MN_PROD}', raise_exception=True)
def productos_editar(request, pk):
    """
    Edición de producto del negocio activo.
    """
    neg_id = _negocio_id_actual(request)
    if not neg_id:
        return HttpResponseForbidden("Debe seleccionar un negocio.")

    prod = get_object_or_404(Productos, pk=pk, negocio_id=neg_id)

    if request.method == "POST":
        form = ProductoForm(request.POST, instance=prod, request=request)
        if form.is_valid():
            form.save()
            messages.success(request, "Producto actualizado correctamente.")
            return redirect('productos_lista')
        messages.error(request, "Revisá los errores del formulario.")
    else:
        form = ProductoForm(instance=prod, request=request)

    return render(request, 'athenas/productos/editar.html', {"form": form, "prod": prod})


@login_required
@requiere_negocio
@permission_required(f'{APP_PROD}.change_{MN_PROD}', raise_exception=True)
def productos_toggle_activo(request, pk):
    """
    Alta/Baja lógica (campo activo) dentro del negocio activo.
    """
    neg_id = _negocio_id_actual(request)
    if not neg_id:
        return HttpResponseForbidden("Debe seleccionar un negocio.")

    prod = get_object_or_404(Productos, pk=pk, negocio_id=neg_id)
    prod.activo = not prod.activo
    prod.save(update_fields=["activo"])
    messages.info(request, f"Producto {'activado' if prod.activo else 'desactivado'}.")
    return redirect('productos_lista')


# =========================================================
# Catálogo rápido: crear Categoría / Marca / Unidad
# - Usa ?next=/ruta/para/volver
# - Fuerza negocio actual en save() (lo hace el form)
# =========================================================

@login_required
@requiere_negocio
@permission_required(f'{APP_CAT}.add_{MN_CAT}', raise_exception=True)
def categoria_nueva(request):
    next_url = request.GET.get("next") or request.POST.get("next") or reverse('productos_crear')
    if request.method == "POST":
        form = CategoriaForm(request.POST, request=request)
        if form.is_valid():
            form.save()
            messages.success(request, "Categoría creada.")
            return redirect(next_url)
        messages.error(request, "Revisá los errores.")
    else:
        form = CategoriaForm(request=request)
    return render(request, "athenas/catalogos/categoria_form.html", {"form": form, "next": next_url})


@login_required
@requiere_negocio
@permission_required(f'{APP_MAR}.add_{MN_MAR}', raise_exception=True)
def marca_nueva(request):
    next_url = request.GET.get("next") or request.POST.get("next") or reverse('productos_crear')
    if request.method == "POST":
        form = MarcaForm(request.POST, request=request)
        if form.is_valid():
            form.save()
            messages.success(request, "Marca creada.")
            return redirect(next_url)
        messages.error(request, "Revisá los errores.")
    else:
        form = MarcaForm(request=request)
    return render(request, "athenas/catalogos/marca_form.html", {"form": form, "next": next_url})


@login_required
@requiere_negocio
@permission_required(f'{APP_UNI}.add_{MN_UNI}', raise_exception=True)
def unidad_nueva(request):
    next_url = request.GET.get("next") or request.POST.get("next") or reverse('productos_crear')
    if request.method == "POST":
        form = UnidadMedidaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Unidad de medida creada.")
            return redirect(next_url)
        messages.error(request, "Revisá los errores.")
    else:
        form = UnidadMedidaForm()
    return render(request, "athenas/catalogos/unidad_form.html", {"form": form, "next": next_url})



# ======================================================================
# ================= CLIENTES & PROVEEDORES (CRUD sin delete) ===========
# ======================================================================

# Helpers para permisos desde metadatos (asegura app_label correcto)
APP_CLIENTE = Clientes._meta.app_label       # "AthenasApp"
MN_CLIENTE  = Clientes._meta.model_name      # "clientes"
APP_PROV    = Proveedores._meta.app_label    # "AthenasApp"
MN_PROV     = Proveedores._meta.model_name   # "proveedores"


# ------------------------
# CLIENTES (ÉPIC 5)
# ------------------------
class ClienteListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Clientes
    template_name = 'athenas/clientes/lista.html'
    context_object_name = 'items'
    paginate_by = 20
    permission_required = f'{APP_CLIENTE}.view_{MN_CLIENTE}'

    def get_queryset(self):
        neg_id = self.request.session.get('negocio_id')
        if not neg_id:
            return Clientes.objects.none()

        qs = Clientes.objects.filter(negocio_id=neg_id).order_by('nombre')
        q = self.request.GET.get('q', '').strip()
        estado = self.request.GET.get('estado', 'activos')

        if q:
            qs = qs.filter(
                Q(nombre__icontains=q) | Q(dni__icontains=q)
            )
        if estado == 'activos':
            qs = qs.filter(activo=True)
        elif estado == 'inactivos':
            qs = qs.filter(activo=False)
        return qs


class ClienteCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Clientes
    form_class = ClienteForm
    template_name = 'athenas/clientes/crear.html'
    success_url = reverse_lazy('clientes_lista')
    permission_required = f'{APP_CLIENTE}.add_{MN_CLIENTE}'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        kwargs['negocio_id'] = self.request.session.get('negocio_id')
        return kwargs

    def form_valid(self, form):
        neg_id = self.request.session.get('negocio_id')
        if not neg_id:
            messages.error(self.request, "Debe seleccionar un negocio antes de continuar.")
            return redirect('seleccionar_negocio')

        obj = form.save(commit=False)
        obj.negocio_id = neg_id
        obj.save()
        messages.success(self.request, "Cliente creado correctamente.")
        return redirect(self.success_url)


class ClienteUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Clientes
    form_class = ClienteForm
    template_name = 'athenas/clientes/editar.html'
    success_url = reverse_lazy('clientes_lista')
    permission_required = f'{APP_CLIENTE}.change_{MN_CLIENTE}'

    def get_object(self, queryset=None):
        neg_id = self.request.session.get('negocio_id')
        return get_object_or_404(Clientes, pk=self.kwargs['pk'], negocio_id=neg_id)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        kwargs['negocio_id'] = self.request.session.get('negocio_id')
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Cliente actualizado correctamente.")
        return super().form_valid(form)


@login_required
@permission_required(f'{APP_CLIENTE}.change_{MN_CLIENTE}', raise_exception=True)
def cliente_toggle_activo(request, pk):
    neg_id = request.session.get('negocio_id')
    obj = get_object_or_404(Clientes, pk=pk, negocio_id=neg_id)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.info(request, f"Cliente {'habilitado' if obj.activo else 'deshabilitado'} correctamente.")
    return redirect('clientes_lista')



# ------------------------
# PROVEEDORES
# ------------------------
@method_decorator(requiere_negocio, name='dispatch')
class ProveedorListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Proveedores
    template_name = 'athenas/proveedores/lista.html'
    context_object_name = 'items'
    paginate_by = 20
    permission_required = f'{APP_PROV}.view_{MN_PROV}'

    def get_queryset(self):
        neg_id = _negocio_id_actual(self.request)
        qs = Proveedores.objects.all()

        # Filtro por negocio SIEMPRE
        if neg_id:
            qs = qs.filter(negocio_id=neg_id)

        # Búsqueda y estado
        q = (self.request.GET.get('q') or '').strip()
        estado = self.request.GET.get('estado', 'activos')  # activos | inactivos | todos

        if q:
            qs = qs.filter(Q(razon_social__icontains=q) | Q(cuit__icontains=q))

        if estado == 'activos':
            qs = qs.filter(activo=True)
        elif estado == 'inactivos':
            qs = qs.filter(activo=False)

        return qs.order_by('razon_social')


@method_decorator(requiere_negocio, name='dispatch')
class ProveedorCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Proveedores
    form_class = ProveedorForm
    template_name = 'athenas/proveedores/crear.html'
    success_url = reverse_lazy('proveedores_lista')
    permission_required = f'{APP_PROV}.add_{MN_PROV}'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Pasamos contexto al form para validar unicidad por negocio, etc.
        kwargs['request'] = self.request
        kwargs['negocio_id'] = _negocio_id_actual(self.request)
        return kwargs

    def form_valid(self, form):
        neg_id = _negocio_id_actual(self.request)
        obj = form.save(commit=False)
        if neg_id:
            obj.negocio_id = neg_id  # fuerza asociación al negocio actual
        obj.save()
        messages.success(self.request, "Proveedor creado correctamente.")
        return redirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, "Revisá los errores del formulario.")
        return super().form_invalid(form)


@method_decorator(requiere_negocio, name='dispatch')
class ProveedorUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Proveedores
    form_class = ProveedorForm
    template_name = 'athenas/proveedores/editar.html'
    success_url = reverse_lazy('proveedores_lista')
    permission_required = f'{APP_PROV}.change_{MN_PROV}'

    def get_queryset(self):
        # Limita la edición a proveedores del negocio activo (evita acceso por URL)
        neg_id = _negocio_id_actual(self.request)
        qs = super().get_queryset()
        if neg_id:
            qs = qs.filter(negocio_id=neg_id)
        return qs

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        kwargs['negocio_id'] = _negocio_id_actual(self.request)
        return kwargs

    def form_valid(self, form):
        obj = form.save(commit=False)
        if not obj.negocio_id:
            obj.negocio_id = _negocio_id_actual(self.request)
        obj.save()
        messages.success(self.request, "Proveedor actualizado correctamente.")
        return redirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, "Revisá los errores del formulario.")
        return super().form_invalid(form)


@login_required
@requiere_negocio
@permission_required(f'{APP_PROV}.change_{MN_PROV}', raise_exception=True)
def proveedor_toggle_activo(request, pk):
    neg_id = _negocio_id_actual(request)
    obj = get_object_or_404(Proveedores, pk=pk, negocio_id=neg_id)
    obj.activo = not obj.activo
    obj.save(update_fields=['activo'])
    messages.info(request, f"Proveedor {'habilitado' if obj.activo else 'deshabilitado'} correctamente.")
    return redirect('proveedores_lista')



# ===== Seguridad: crear usuario (solo admin) =====
@login_required
@user_passes_test(es_admin)
def crear_usuario(request):
    if request.method == 'POST':
        form = CrearUsuarioForm(request.POST, request=request)
        if form.is_valid():
            nuevo_user = form.save()

            # === Auditoría ===
            registrar_auditoria(
                request,
                accion="Creación de usuario",
                entidad="Usuario",
                id_registro=nuevo_user.pk
            )

            messages.success(request, "Usuario creado correctamente.")
            return redirect('dashboard')

        messages.error(request, "Revisá los errores del formulario.")
    else:
        form = CrearUsuarioForm(request=request)

    return render(request, "athenas/seguridad/crear_usuario.html", {"form": form})



# ===== USUARIOS (solo admin) =====
class UsuarioListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = User
    template_name = 'athenas/seguridad/usuarios_lista.html'
    context_object_name = 'items'
    paginate_by = 20
    permission_required = 'auth.view_user'

    def get_queryset(self):
        qs = User.objects.select_related('perfil').all().order_by('username')
        q = (self.request.GET.get('q') or '').strip()
        estado = self.request.GET.get('estado', 'activos')  # activos | inactivos | todos

        if q:
            qs = qs.filter(
                Q(username__icontains=q) |
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q) |
                Q(email__icontains=q) |
                Q(perfil__negocio__detalle__icontains=q)
            )
        if estado == 'activos':
            qs = qs.filter(is_active=True)
        elif estado == 'inactivos':
            qs = qs.filter(is_active=False)
        return qs


class UsuarioUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    ...
    def form_valid(self, form):
        response = super().form_valid(form)

        # === Auditoría ===
        registrar_auditoria(
            self.request,
            accion="Edición de usuario",
            entidad="Usuario",
            id_registro=self.object.pk
        )

        messages.success(self.request, "Usuario actualizado correctamente.")
        return response



@login_required
@user_passes_test(es_admin)
def usuario_toggle_activo(request, pk):
    obj = get_object_or_404(User, pk=pk)

    obj.is_active = not obj.is_active
    obj.save(update_fields=["is_active"])

    # === Auditoría ===
    registrar_auditoria(
        request,
        accion="Activación/Desactivación de usuario",
        entidad="Usuario",
        id_registro=obj.pk
    )

    messages.info(
        request,
        f"Usuario {'habilitado' if obj.is_active else 'deshabilitado'} correctamente."
    )
    return redirect("usuarios_lista")

