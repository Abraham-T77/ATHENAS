# AthenasApp/forms.py
from django import forms
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from decimal import Decimal, ROUND_HALF_UP
from django.forms import inlineformset_factory

from .models import (
    Usuarios, Roles, Clientes, Proveedores,
    TipoNegocio, PerfilUsuario,
    Productos, Categoria, Marca, UnidadMedida,
    Compras, DetalleCompras, ComprobantesCompra,
    ProveedorProducto,
)

# =========================================================
# Crear usuario (solo Admin)
# - Admin elige Grupo/Rol y Tipo de negocio
# - Sincroniza PerfilUsuario y la tabla espejo 'Usuarios'
# =========================================================
class CrearUsuarioForm(forms.ModelForm):
    grupo = forms.ModelChoiceField(
        queryset=Group.objects.filter(name__in=['administrador', 'encargado', 'caja', 'repositor']),
        label='Grupo / Rol'
    )
    negocio = forms.ModelChoiceField(
        queryset=TipoNegocio.objects.all(),
        label='Tipo de negocio'
    )
    password = forms.CharField(widget=forms.PasswordInput, label='Contraseña')

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active', 'password']

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        # Solo el admin (permiso can_switch_negocio) puede elegir el negocio
        if self.request and not self.request.user.has_perm('AthenasApp.can_switch_negocio'):
            self.fields['negocio'].widget = forms.HiddenInput()
            if hasattr(self.request.user, 'perfil') and self.request.user.perfil.negocio_id:
                self.initial['negocio'] = self.request.user.perfil.negocio_id

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])

        if commit:
            user.save()

            # Grupo (rol operativo de Django)
            grupo = self.cleaned_data['grupo']
            user.groups.set([grupo])

            # Rol (tabla de dominio)
            rol = Roles.objects.filter(descripcion__iexact=grupo.name).first()
            if not rol:
                rol, _ = Roles.objects.get_or_create(descripcion='encargado')

            # Negocio elegido por el admin (o fijado si no es admin)
            negocio = self.cleaned_data['negocio']

            # Perfil del usuario (negocio por FK)
            perfil, _ = PerfilUsuario.objects.get_or_create(user=user)
            perfil.negocio = negocio
            perfil.save()

            # Espejo en tabla 'Usuarios'
            nombre = (f"{user.first_name} {user.last_name}").strip() or user.username
            Usuarios.objects.update_or_create(
                usuario=user.username,
                defaults={
                    "nombre": nombre,
                    "contrasenia": user.password,  # hash de Django (solo consistencia)
                    "rol": rol,
                    "negocio": negocio,
                }
            )
        return user


# =========================================================
# Editar usuario (solo Admin)
# - Cambia datos básicos, Grupo/Rol y Negocio
# - Sincroniza PerfilUsuario y 'Usuarios'
# =========================================================
class UsuarioEditForm(forms.ModelForm):
    grupo = forms.ModelChoiceField(
        queryset=Group.objects.filter(name__in=['administrador', 'encargado', 'caja', 'repositor']),
        label='Grupo / Rol'
    )
    negocio = forms.ModelChoiceField(
        queryset=TipoNegocio.objects.all(),
        label='Tipo de negocio'
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'is_active']

    def __init__(self, *args, **kwargs):
        user_obj = kwargs.get('instance')
        super().__init__(*args, **kwargs)

        # Iniciales: grupo y negocio actuales
        if user_obj:
            g = user_obj.groups.first()
            if g:
                self.fields['grupo'].initial = g
            if hasattr(user_obj, 'perfil') and user_obj.perfil.negocio_id:
                self.fields['negocio'].initial = user_obj.perfil.negocio_id

    def save(self, commit=True):
        user = super().save(commit=commit)

        # Grupo (rol operativo)
        grupo = self.cleaned_data['grupo']
        user.groups.set([grupo])

        # Rol (tabla de dominio)
        rol = Roles.objects.filter(descripcion__iexact=grupo.name).first()
        if not rol:
            rol, _ = Roles.objects.get_or_create(descripcion='encargado')

        # Negocio
        negocio = self.cleaned_data['negocio']

        # PerfilUsuario
        perfil, _ = PerfilUsuario.objects.get_or_create(user=user)
        perfil.negocio = negocio
        perfil.save()

        # Espejo 'Usuarios'
        nombre = (f"{user.first_name} {user.last_name}").strip() or user.username
        Usuarios.objects.update_or_create(
            usuario=user.username,
            defaults={
                "nombre": nombre,
                "contrasenia": user.password,
                "rol": rol,
                "negocio": negocio,
            }
        )
        return user


# =========================================================
# Clientes (Épic 5)
# - DNI y Email opcionales (contacto)
# - Normaliza DNI (solo dígitos) y Email (minúsculas)
# - Unicidad por negocio: DNI (si está cargado)
# - Recibe request/negocio_id para validar y asociar
# =========================================================
class ClienteForm(forms.ModelForm):
    class Meta:
        model = Clientes
        fields = ['nombre', 'dni', 'email', 'direccion', 'telefono', 'saldo_cuenta_corriente', 'activo']
        labels = {
            'nombre': 'Nombre',
            'dni': 'DNI (opcional)',
            'email': 'Email (opcional)',
            'direccion': 'Dirección',
            'telefono': 'Teléfono',
            'saldo_cuenta_corriente': 'Saldo C/C',
            'activo': 'Activo',
        }
        widgets = {
            'nombre': forms.TextInput(attrs={'autofocus': True}),
        }

    def __init__(self, *args, request=None, negocio_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.negocio_id = negocio_id

        # Placeholders / UX
        self.fields['nombre'].widget.attrs.setdefault('placeholder', 'Nombre y apellido / Razón social')
        self.fields['dni'].widget.attrs.setdefault('placeholder', 'Solo números (opcional)')
        self.fields['email'].widget.attrs.setdefault('placeholder', 'email@dominio.com (opcional)')
        self.fields['telefono'].widget.attrs.setdefault('placeholder', 'Ej: 387-5555555')
        self.fields['direccion'].widget.attrs.setdefault('placeholder', 'Calle 123')
        # Opcionales
        self.fields['dni'].required = False
        self.fields['email'].required = False

    # Normaliza DNI (deja solo dígitos); valida longitud mínima si viene
    def clean_dni(self):
        dni = (self.cleaned_data.get('dni') or '').strip()
        if not dni:
            return dni
        dni_digits = ''.join(ch for ch in dni if ch.isdigit())
        if len(dni_digits) < 7:  # admite DNI antiguos (7) y modernos (8+)
            raise ValidationError("DNI inválido: demasiado corto.")
        return dni_digits

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        return email

    def clean(self):
        cleaned = super().clean()

        # Resolver negocio: preferimos 'negocio_id' (kwarg de la vista),
        # si no, intentamos con request.user.perfil.negocio
        neg_id = self.negocio_id
        if not neg_id and self.request:
            neg = getattr(getattr(self.request.user, 'perfil', None), 'negocio', None)
            neg_id = getattr(neg, 'id', None)

        if not neg_id:
            # La vista exigirá negocio con @requiere_negocio; no frenamos aquí
            return cleaned

        dni = (cleaned.get('dni') or '').strip()
        if dni:
            qs = Clientes.objects.filter(negocio_id=neg_id, dni=dni)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('dni', "Ya existe un cliente con ese DNI en el negocio actual.")

        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        # Asegura asociación al negocio si vino en kwargs
        if self.negocio_id and not getattr(obj, 'negocio_id', None):
            obj.negocio_id = self.negocio_id
        if commit:
            obj.save()
        return obj



# =========================================================
# Proveedores (Épic 4)
# - Email opcional (contacto); no se usa para filtrar
# - Valida unicidad por negocio (CUIT y, opcionalmente, Razón Social)
# - Normaliza CUIT (solo dígitos) y email (minúsculas, trim)
# - Recibe request y negocio_id desde las vistas
# - En save() fuerza el negocio si viene por kwargs
# =========================================================
class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedores
        # Agregamos email como campo opcional de contacto
        fields = ['razon_social', 'cuit', 'email', 'telefono', 'direccion', 'activo']
        labels = {
            'razon_social': 'Razón Social',
            'cuit': 'CUIT',
            'email': 'Email (opcional)',
            'telefono': 'Teléfono',
            'direccion': 'Dirección',
            'activo': 'Activo',
        }
        widgets = {
            'razon_social': forms.TextInput(attrs={'autofocus': True}),
        }

    def __init__(self, *args, request=None, negocio_id=None, **kwargs):
        """
        Se inyecta desde las CBVs:
          - request (por si necesitás user.perfil.negocio como fallback)
          - negocio_id (preferido para validar por negocio)
        """
        super().__init__(*args, **kwargs)
        self.request = request
        self.negocio_id = negocio_id

        # Placeholders (UX consistente con productos)
        self.fields['razon_social'].widget.attrs.setdefault('placeholder', 'Razón Social')
        self.fields['cuit'].widget.attrs.setdefault('placeholder', 'CUIT (solo números)')
        self.fields['email'].widget.attrs.setdefault('placeholder', 'email@dominio.com')
        self.fields['telefono'].widget.attrs.setdefault('placeholder', 'Ej: 387-5555555')
        self.fields['direccion'].widget.attrs.setdefault('placeholder', 'Calle 123')

        # Email NO es obligatorio
        self.fields['email'].required = False

    # Normalización simple de CUIT (deja solo dígitos y valida mínimo)
    def clean_cuit(self):
        cuit = (self.cleaned_data.get('cuit') or '').strip()
        if not cuit:
            return cuit
        cuit_digits = ''.join(ch for ch in cuit if ch.isdigit())
        if len(cuit_digits) < 8:
            raise ValidationError("CUIT/DNI inválido: demasiado corto.")
        return cuit_digits

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        # No forzamos obligatorio, ni unicidad
        return email

    def clean(self):
        """
        Valida unicidad por negocio:
          - CUIT único por negocio (si viene cargado)
          - (Opcional) Razón Social única por negocio (case-insensitive)
        """
        cleaned = super().clean()

        # Resolver negocio: preferimos negocio_id (kwarg de la vista),
        # si no, intentamos con request.user.perfil.negocio
        neg_id = self.negocio_id
        if not neg_id and self.request:
            neg = getattr(getattr(self.request.user, 'perfil', None), 'negocio', None)
            neg_id = getattr(neg, 'id', None)

        if not neg_id:
            # La CBV ya exige negocio con @requiere_negocio; no interrumpimos aquí
            return cleaned

        razon = (cleaned.get('razon_social') or '').strip()
        cuit = (cleaned.get('cuit') or '').strip()

        qs = Proveedores.objects.filter(negocio_id=neg_id)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        # Unicidad por negocio: CUIT
        if cuit and qs.filter(cuit=cuit).exists():
            self.add_error('cuit', "Ya existe un proveedor con este CUIT en el negocio actual.")

        # (Opcional) Unicidad por negocio: Razón Social
        if razon and qs.filter(razon_social__iexact=razon).exists():
            self.add_error('razon_social', "Ya existe un proveedor con esa Razón Social en el negocio actual.")

        return cleaned

    def save(self, commit=True):
        """
        Asegura que el objeto quede asociado al negocio actual si vino en kwargs.
        (Las vistas igualmente ya lo fuerzan.)
        """
        obj = super().save(commit=False)
        if self.negocio_id and not getattr(obj, 'negocio_id', None):
            obj.negocio_id = self.negocio_id
        if commit:
            obj.save()
        return obj



# =========================================================
# Productos (Épic 3)
# - Filtra combos por negocio actual
# - Valida unicidad por negocio: descripcion, codigo_barra, sku
# =========================================================
class ProductoForm(forms.ModelForm):
    class Meta:
        model = Productos
        fields = [
            "descripcion", "categoria", "marca", "unidad",
            "codigo_barra", "sku",
            "precio_compra", "margen_ganancia", "precio_venta",
            "stock_actual", "stock_minimo",
            "fecha_vencimiento", "activo",
        ]
        labels = {
            "margen_ganancia": "Margen de ganancia (%)",
        }
        widgets = {
            "descripcion":       forms.TextInput(attrs={"class": "form-control", "autofocus": True}),
            "categoria":         forms.Select(attrs={"class": "form-select"}),
            "marca":             forms.Select(attrs={"class": "form-select"}),
            "unidad":            forms.Select(attrs={"class": "form-select"}),
            "codigo_barra":      forms.TextInput(attrs={"class": "form-control"}),
            "sku":               forms.TextInput(attrs={"class": "form-control"}),
            "precio_compra":     forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "margen_ganancia":   forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0", "max": "100"}),
            "precio_venta":      forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "stock_actual":      forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "stock_minimo":      forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "fecha_vencimiento": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "activo":            forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        help_texts = {
            "margen_ganancia": "Si cargás un margen (0–100), el precio de venta se calcula automáticamente a partir del precio de compra.",
        }

    def __init__(self, *args, **kwargs):
        # necesitamos el request para saber el negocio del usuario
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        negocio = getattr(getattr(self.request.user, "perfil", None), "negocio", None) if self.request else None

        # Filtrar combos por negocio actual
        if negocio:
            self.fields["categoria"].queryset = Categoria.objects.filter(negocio=negocio).order_by("nombre")
            self.fields["marca"].queryset     = Marca.objects.filter(negocio=negocio).order_by("nombre")
        self.fields["unidad"].queryset = UnidadMedida.objects.all().order_by("nombre")

    def clean(self):
        cleaned = super().clean()
        negocio = getattr(getattr(self.request.user, "perfil", None), "negocio", None) if self.request else None

        # -------- Validaciones de unicidad por negocio --------
        if negocio:
            qs = Productos.objects.filter(negocio=negocio)

            # Unicidad por negocio: descripción
            desc = cleaned.get("descripcion")
            if desc:
                q = qs.filter(descripcion__iexact=desc)
                if self.instance.pk:
                    q = q.exclude(pk=self.instance.pk)
                if q.exists():
                    raise ValidationError({"descripcion": "Ya existe un producto con esa descripción en este negocio."})

            # Unicidad por negocio: código de barras
            cb = cleaned.get("codigo_barra")
            if cb:
                q = qs.filter(codigo_barra=cb)
                if self.instance.pk:
                    q = q.exclude(pk=self.instance.pk)
                if q.exists():
                    raise ValidationError({"codigo_barra": "El código de barras ya está usado en este negocio."})

            # Unicidad por negocio: SKU
            sku = cleaned.get("sku")
            if sku:
                q = qs.filter(sku__iexact=sku)
                if self.instance.pk:
                    q = q.exclude(pk=self.instance.pk)
                if q.exists():
                    raise ValidationError({"sku": "El SKU ya está usado en este negocio."})

        # -------- Cálculo de precio_venta por margen --------
        margen = cleaned.get("margen_ganancia")
        precio_compra = cleaned.get("precio_compra")
        if margen is not None and margen != "":
            # Validación suave del margen (0..100)
            try:
                m = Decimal(margen)
            except Exception:
                raise ValidationError({"margen_ganancia": "Margen inválido."})
            if m < 0 or m > 100:
                raise ValidationError({"margen_ganancia": "El margen debe estar entre 0 y 100."})

            if precio_compra is not None:
                pv = (Decimal(precio_compra) * (Decimal("1.00") + m / Decimal("100"))).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                cleaned["precio_venta"] = pv

        return cleaned

# =========================================================
# Catálogos rápidos: Categoría / Marca / Unidad de Medida
# =========================================================
class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nombre"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "autofocus": True}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

    def clean_nombre(self):
        nombre = (self.cleaned_data.get("nombre") or "").strip()
        if not nombre:
            raise ValidationError("Ingresá un nombre.")
        # Unicidad por negocio
        negocio = getattr(getattr(self.request.user, "perfil", None), "negocio", None) if self.request else None
        if negocio and Categoria.objects.filter(negocio=negocio, nombre__iexact=nombre).exists():
            raise ValidationError("Ya existe una categoría con ese nombre en este negocio.")
        return nombre

    def save(self, commit=True):
        obj = super().save(commit=False)
        negocio = getattr(getattr(self.request.user, "perfil", None), "negocio", None) if self.request else None
        if negocio:
            obj.negocio = negocio
        if commit:
            obj.save()
        return obj


class MarcaForm(forms.ModelForm):
    class Meta:
        model = Marca
        fields = ["nombre"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "autofocus": True}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

    def clean_nombre(self):
        nombre = (self.cleaned_data.get("nombre") or "").strip()
        if not nombre:
            raise ValidationError("Ingresá un nombre.")
        negocio = getattr(getattr(self.request.user, "perfil", None), "negocio", None) if self.request else None
        if negocio and Marca.objects.filter(negocio=negocio, nombre__iexact=nombre).exists():
            raise ValidationError("Ya existe una marca con ese nombre en este negocio.")
        return nombre

    def save(self, commit=True):
        obj = super().save(commit=False)
        negocio = getattr(getattr(self.request.user, "perfil", None), "negocio", None) if self.request else None
        if negocio:
            obj.negocio = negocio
        if commit:
            obj.save()
        return obj


class UnidadMedidaForm(forms.ModelForm):
    class Meta:
        model = UnidadMedida
        fields = ["codigo", "nombre"]
        widgets = {
            "codigo": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej: UN, KG, LT", "autofocus": True}),
            "nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Unidad, Kilogramo, Litro"}),
        }

    def clean_codigo(self):
        codigo = (self.cleaned_data.get("codigo") or "").strip().upper()
        if not codigo:
            raise ValidationError("Ingresá un código.")
        if UnidadMedida.objects.filter(codigo__iexact=codigo).exists():
            raise ValidationError("Ya existe una unidad con ese código.")
        return codigo

    def clean_nombre(self):
        nombre = (self.cleaned_data.get("nombre") or "").strip()
        if not nombre:
            raise ValidationError("Ingresá un nombre.")
        return nombre


# =========================================================
# ÉPIC 6 — COMPRAS (Form principal + formsets + form singular)
# =========================================================
from decimal import Decimal, ROUND_HALF_UP
from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory

from .models import Compras, DetalleCompras, ComprobantesCompra, Proveedores, Productos

class CompraForm(forms.ModelForm):
    class Meta:
        model = Compras
        fields = ["proveedor", "fecha", "forma_pago", "observaciones"]
        widgets = {
            "fecha": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "proveedor": "Proveedor",
            "fecha": "Fecha y hora",
            "forma_pago": "Forma de pago",
            "observaciones": "Observaciones",
        }

    def __init__(self, *args, negocio_id=None, **kwargs):
        """Filtra proveedores por negocio activo (si viene)"""
        super().__init__(*args, **kwargs)
        if negocio_id:
            self.fields["proveedor"].queryset = Proveedores.objects.filter(
                negocio_id=negocio_id, activo=True
            ).order_by("razon_social")

    def clean(self):
        cleaned = super().clean()
        prov = cleaned.get("proveedor")
        # Si vino negocio_id en __init__, el queryset ya filtra.
        # Si querés 100% blindaje, podés validar con prov.negocio_id == negocio_id
        return cleaned


class DetalleCompraForm(forms.ModelForm):
    class Meta:
        model = DetalleCompras
        fields = ["producto", "cantidad", "costo_unitario", "subtotal", "vencimiento", "lote"]
        widgets = {"vencimiento": forms.DateInput(attrs={"type": "date"})}
        labels = {
            "producto": "Producto",
            "cantidad": "Cantidad",
            "costo_unitario": "Costo unit.",
            "subtotal": "Subtotal",
            "vencimiento": "Vencimiento",
            "lote": "Lote",
        }

    def __init__(self, *args, negocio_id=None, proveedor_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.negocio_id = negocio_id
        self.proveedor_id = proveedor_id

        if negocio_id:
            if proveedor_id:
                self.fields['producto'].queryset = Productos.objects.filter(
                    negocio_id=negocio_id,
                    activo=True,
                    proveedores_asociados__proveedor_id=proveedor_id
                ).order_by('descripcion')
            else:
                self.fields['producto'].queryset = Productos.objects.none()


    def clean(self):
        cleaned = super().clean()
        cant = cleaned.get("cantidad")
        costo = cleaned.get("costo_unitario")
        if cant is not None and costo is not None:
            cleaned["subtotal"] = (Decimal(cant) * Decimal(costo)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        producto = cleaned.get('producto')
        if self.proveedor_id and producto:
            existe_relacion = ProveedorProducto.objects.filter(
                proveedor_id=self.proveedor_id, producto=producto
            ).exists()
            if not existe_relacion:
                self.add_error('producto', "Este producto no está asociado al proveedor seleccionado.")
        return cleaned


# --- Formsets (inline) ---
DetalleComprasFormSet = inlineformset_factory(
    parent_model=Compras,
    model=DetalleCompras,
    form=DetalleCompraForm,
    extra=1,
    can_delete=True,
)

ComprobantesCompraFormSet = inlineformset_factory(
    parent_model=Compras,
    model=ComprobantesCompra,
    fields=["tipo", "numero", "archivo", "notas"],
    extra=1,
    can_delete=True,
)

# --- Formulario singular para adjuntar un comprobante ---
class ComprobanteCompraForm(forms.ModelForm):
    class Meta:
        model = ComprobantesCompra
        fields = ["tipo", "numero", "archivo", "notas"]
        labels = {"tipo": "Tipo", "numero": "Número", "archivo": "Archivo", "notas": "Notas"}


# =========================================================
# PR-4 — NUEVOS FORMULARIOS DE GESTIÓN
# =========================================================

from .models import CuentaCorrienteCliente, AlertaSistema, ReporteSistema, BitacoraSistema


class CuentaCorrienteClienteForm(forms.ModelForm):
    class Meta:
        model = CuentaCorrienteCliente
        fields = ["cliente", "saldo_actual"]
        labels = {
            "cliente": "Cliente",
            "saldo_actual": "Saldo actual",
        }


class AlertaSistemaForm(forms.ModelForm):
    class Meta:
        model = AlertaSistema
        fields = ["descripcion"]
        labels = {
            "descripcion": "Descripción",
        }


class ReporteSistemaForm(forms.ModelForm):
    class Meta:
        model = ReporteSistema
        fields = ["titulo", "descripcion", "negocio"]
        labels = {
            "titulo": "Título del reporte",
            "descripcion": "Descripción",
            "negocio": "Negocio",
        }


class BitacoraSistemaForm(forms.ModelForm):
    class Meta:
        model = BitacoraSistema
        fields = ["usuario", "accion", "detalle"]
        labels = {
            "usuario": "Usuario",
            "accion": "Acción realizada",
            "detalle": "Detalle",
        }

