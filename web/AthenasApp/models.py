from django.db import models, transaction
from django.db.models import Q
from django.utils.text import slugify
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User




# =========================================================
# SECCIÓN 1: MODELOS DE CONFIGURACIÓN Y SEGURIDAD
# =========================================================

class TipoNegocio(models.Model):
    """
    Define los tipos de negocio disponibles dentro del sistema
    (por ejemplo: Despensa, Vinería). 
    Permite agrupar y segmentar la información de manera independiente.
    """
    id_negocio = models.AutoField(primary_key=True)
    detalle = models.CharField(max_length=100)

    class Meta:
        db_table = 'tipo_negocio'
        verbose_name = "Tipo de Negocio"
        verbose_name_plural = "Tipos de Negocio"

    def __str__(self):
        return self.detalle


class Roles(models.Model):
    """
    Contiene los roles funcionales que determinan los permisos y 
    responsabilidades de los usuarios dentro del sistema.
    """
    id_rol = models.AutoField(primary_key=True)
    descripcion = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = 'roles'
        verbose_name = "Rol"
        verbose_name_plural = "Roles"

    def __str__(self):
        return self.descripcion


class Usuarios(models.Model):
    """
    Tabla espejo que representa los usuarios operativos del sistema.
    Está asociada a un rol (función) y a un tipo de negocio específico.
    """
    id_usuario = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    usuario = models.CharField(max_length=50, unique=True)
    contrasenia = models.CharField(max_length=255)
    rol = models.ForeignKey(Roles, on_delete=models.RESTRICT, db_column='id_rol', null=True, blank=True)
    negocio = models.ForeignKey(
        'TipoNegocio',
        on_delete=models.RESTRICT,
        db_column='id_negocio',
        to_field='id_negocio',
        null=True,
        blank=True,
        verbose_name="Negocio"
    )

    class Meta:
        db_table = 'usuarios'
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"

    def __str__(self):
        return self.usuario


class PerfilUsuario(models.Model):
    """
    Extiende el modelo de usuario interno de Django, asociando cada cuenta 
    con un tipo de negocio específico. Permite manejar la sesión, 
    la selección de negocio y la restricción de acceso por entorno.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil")
    negocio = models.ForeignKey(TipoNegocio, on_delete=models.PROTECT)

    class Meta:
        db_table = 'perfil_usuario'
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuarios"
        permissions = [
            ('can_switch_negocio', 'Puede cambiar/seleccionar el negocio actual'),
        ]

    def __str__(self):
        return f"{self.user.username} → {self.negocio.detalle}"



# =========================================================
# SECCIÓN 3: MODELOS DE CLIENTES Y PROVEEDORES
# =========================================================

class Clientes(models.Model):
    """
    Contiene los datos básicos de los clientes asociados a un negocio.
    Permite registrar deudas, cuentas corrientes y estado activo.
    """
    id_cliente = models.AutoField(primary_key=True)

    # Negocio al que pertenece el cliente (multi-negocio)
    negocio = models.ForeignKey(
        TipoNegocio,
        on_delete=models.RESTRICT,
        db_column='id_negocio',
        null=True,
        blank=True,
        verbose_name="Negocio"
    )

    nombre = models.CharField(max_length=100)
    dni = models.CharField(max_length=20, blank=True, null=True)          # opcional
    email = models.EmailField(max_length=120, blank=True, null=True)      # opcional
    direccion = models.CharField(max_length=150, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    saldo_cuenta_corriente = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'clientes'
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        # Índices útiles para búsquedas y filtros
        indexes = [
            models.Index(fields=['negocio', 'nombre']),
            models.Index(fields=['negocio', 'dni']),
            models.Index(fields=['negocio', 'activo']),
        ]
        # Unicidad por negocio (si DNI está cargado; múltiples NULL se permiten)
        constraints = [
            models.UniqueConstraint(
                fields=['negocio', 'dni'],
                name='uniq_cliente_dni_por_negocio'
            ),
        ]

    def __str__(self):
        return self.nombre



class Proveedores(models.Model):
    """
    Registra los proveedores de cada negocio, con su CUIT y datos de contacto.
    """
    id_proveedor = models.AutoField(primary_key=True)

    # Negocio al que pertenece el proveedor (clave para multi-negocio)
    negocio = models.ForeignKey(
        TipoNegocio,
        on_delete=models.RESTRICT,
        db_column='id_negocio',
        null=True,
        blank=True,
        verbose_name="Negocio"
    )

    razon_social = models.CharField(max_length=100)
    # Quitar unique=True: la unicidad pasa a ser por (negocio, cuit) en Meta.constraints
    cuit = models.CharField(max_length=20)
    email = models.EmailField(max_length=120, blank=True, null=True)  # contacto opcional
    telefono = models.CharField(max_length=20, blank=True, null=True)
    direccion = models.CharField(max_length=150, blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'proveedores'
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        # Índices útiles para búsquedas y filtros
        indexes = [
            models.Index(fields=['negocio', 'razon_social']),
            models.Index(fields=['negocio', 'cuit']),
            models.Index(fields=['negocio', 'activo']),
        ]
        # Unicidad por negocio (no global)
        constraints = [
            models.UniqueConstraint(
                fields=['negocio', 'cuit'],
                name='uniq_proveedor_cuit_por_negocio'
            ),
        ]

    def __str__(self):
        return self.razon_social



# =========================================================
# SECCIÓN 4: MODELOS DE PRODUCTOS Y STOCK
# =========================================================

class Categoria(models.Model):
    id_categoria = models.AutoField(primary_key=True)
    negocio = models.ForeignKey(TipoNegocio, on_delete=models.RESTRICT, db_column='id_negocio')
    nombre = models.CharField(max_length=100)

    class Meta:
        db_table = 'categorias'
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        unique_together = (('negocio', 'nombre'),)
        indexes = [
            models.Index(fields=['negocio', 'nombre']),
        ]

    def __str__(self):
        return f"{self.nombre}"


class Marca(models.Model):
    id_marca = models.AutoField(primary_key=True)
    negocio = models.ForeignKey(TipoNegocio, on_delete=models.RESTRICT, db_column='id_negocio')
    nombre = models.CharField(max_length=100)

    class Meta:
        db_table = 'marcas'
        verbose_name = "Marca"
        verbose_name_plural = "Marcas"
        unique_together = (('negocio', 'nombre'),)
        indexes = [
            models.Index(fields=['negocio', 'nombre']),
        ]

    def __str__(self):
        return f"{self.nombre}"


class UnidadMedida(models.Model):
    id_unidad = models.AutoField(primary_key=True)
    codigo = models.CharField(max_length=10, unique=True)   # ej: UN, KG, LT
    nombre = models.CharField(max_length=50)                # ej: Unidad, Kilogramo, Litro

    class Meta:
        db_table = 'unidades_medida'
        verbose_name = "Unidad de medida"
        verbose_name_plural = "Unidades de medida"

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"

class Productos(models.Model):
    """
    Define los productos disponibles, sus atributos y stock por negocio.
    """
    id_producto = models.AutoField(primary_key=True)

    # negocio propietario del producto
    negocio = models.ForeignKey(
        TipoNegocio, on_delete=models.RESTRICT, db_column='id_negocio', null=True, blank=True
    )

    # descripción y atributos de catálogo
    descripcion = models.CharField(max_length=120)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True, db_column='id_categoria')
    marca = models.ForeignKey(Marca, on_delete=models.SET_NULL, null=True, blank=True, db_column='id_marca')
    unidad = models.ForeignKey(UnidadMedida, on_delete=models.SET_NULL, null=True, blank=True, db_column='id_unidad')

    # identificadores
    codigo_barra = models.CharField(max_length=50, blank=True, null=True)  # único por negocio
    sku = models.CharField(max_length=30, blank=True, null=True)           # blindado por negocio

    # precios
    precio_compra = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    margen_ganancia = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)  # % 0..100
    precio_venta = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # stock
    stock_actual = models.PositiveIntegerField(default=0)
    stock_minimo = models.PositiveIntegerField(default=0)

    # estado / control
    fecha_vencimiento = models.DateField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'productos'
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        unique_together = (
            ('negocio', 'codigo_barra'),
            ('negocio', 'sku'),
        )
        indexes = [
            models.Index(fields=['negocio', 'descripcion']),
            models.Index(fields=['negocio', 'categoria']),
            models.Index(fields=['negocio', 'marca']),
            models.Index(fields=['negocio', 'activo']),
            models.Index(fields=['negocio', 'codigo_barra']),
        ]
        constraints = [
            models.CheckConstraint(check=Q(precio_compra__gte=0), name='chk_precio_compra_no_neg'),
            models.CheckConstraint(check=Q(precio_venta__gte=0),  name='chk_precio_venta_no_neg'),
            models.CheckConstraint(check=Q(stock_actual__gte=0), name='chk_stock_actual_no_neg'),
            models.CheckConstraint(check=Q(stock_minimo__gte=0), name='chk_stock_minimo_no_neg'),
            models.CheckConstraint(
                check=(Q(margen_ganancia__isnull=True) |
                       (Q(margen_ganancia__gte=0) & Q(margen_ganancia__lte=100))),
                name='chk_margen_0_100'
            ),
        ]

    def __str__(self):
        return self.descripcion

    # ===== SKU automático (solo si viene vacío) =====
    def _generar_sku_si_falta(self):
        if self.sku:
            return
        neg = self.negocio_id or 0
        slug = slugify(self.descripcion or '')[:12] or 'prod'
        ts = timezone.now().strftime('%Y%m%d-%H%M')
        base = f"N{neg}-{slug}-{ts}"

        candidate = base
        i = 1
        while Productos.objects.filter(negocio_id=neg, sku=candidate).exclude(pk=self.pk).exists() and i <= 20:
            candidate = f"{base}-{i}"
            i += 1
        self.sku = candidate

    def save(self, *args, **kwargs):
        self._generar_sku_si_falta()
        super().save(*args, **kwargs)




# =========================================================
# SECCIÓN 5: MODELOS DE VENTAS (RENOVADOS)
# =========================================================

class Venta(models.Model):
    """
    Cabecera de venta minorista.
    - Multi-negocio: numeración separada por negocio y año.
    - Estados operativos: Borrador, Confirmada, Anulada.
    - Pagos: ver modelo VentaPago (soporta mixto).
    - Descuentos: global a nivel venta; por ítem en VentaDetalle.
    """

    # Estados
    ESTADO_BORRADOR = "BORRADOR"
    ESTADO_CONFIRMADA = "CONFIRMADA"
    ESTADO_ANULADA = "ANULADA"
    ESTADOS = [
        (ESTADO_BORRADOR, "Borrador"),
        (ESTADO_CONFIRMADA, "Confirmada"),
        (ESTADO_ANULADA, "Anulada"),
    ]

    # Formas de pago (para referencia global de la venta)
    FP_EFECTIVO = "EFECTIVO"
    FP_TARJETA = "TARJETA"
    FP_TRANSFERENCIA = "TRANSFERENCIA"
    FP_MIXTO = "MIXTO"
    FORMAS_PAGO = [
        (FP_EFECTIVO, "Efectivo"),
        (FP_TARJETA, "Tarjeta"),
        (FP_TRANSFERENCIA, "Transferencia"),
        (FP_MIXTO, "Mixto"),
    ]

    id_venta = models.AutoField(primary_key=True)

    # --- Multi-negocio y numeración ---
    negocio = models.ForeignKey(TipoNegocio, on_delete=models.PROTECT, db_column='id_negocio', verbose_name="Negocio")
    anio = models.PositiveIntegerField(editable=False)
    nro_secuencial = models.PositiveIntegerField(editable=False)
    numero_ticket = models.CharField(max_length=20, editable=False)

    # --- Datos operativos ---
    fecha = models.DateTimeField(default=timezone.now)
    usuario = models.ForeignKey(Usuarios, on_delete=models.PROTECT, db_column='id_usuario', null=True, blank=True)
    cliente = models.ForeignKey(Clientes, on_delete=models.PROTECT, db_column='id_cliente', null=True, blank=True)
    caja = models.ForeignKey('Caja', on_delete=models.PROTECT, db_column='id_caja', null=True, blank=True)

    # Totales y descuentos
    total_bruto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    descuento_global_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    total_neto = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Forma de pago principal
    forma_pago = models.CharField(max_length=20, choices=FORMAS_PAGO, default=FP_EFECTIVO)

    # Estado operativo
    estado = models.CharField(max_length=12, choices=ESTADOS, default=ESTADO_BORRADOR)

    # Timestamps
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ventas'
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ['-fecha', '-id_venta']
        indexes = [
            models.Index(fields=['negocio', 'fecha']),
            models.Index(fields=['negocio', 'estado']),
            models.Index(fields=['negocio', 'anio', 'nro_secuencial']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['negocio', 'anio', 'nro_secuencial'],
                name='uniq_venta_num_por_negocio_y_anio'
            ),
        ]
        permissions = [
            ("can_confirm_sale", "Puede confirmar ventas"),
            ("cancel_venta", "Puede anular ventas"),
        ]
    

    def anular(self, usuario):
        """
        Anula una venta confirmada: repone stock, revierte caja y marca estado como ANULADA.
        Registra bitácora y un movimiento de stock de ENTRADA por cada ítem.
        """
        if self.estado != self.ESTADO_CONFIRMADA:
            raise ValueError("Solo se pueden anular ventas confirmadas.")

        detalles = VentaDetalle.objects.filter(venta=self).select_related("producto")
        for det in detalles:
            prod = det.producto
            prod.stock_actual = (prod.stock_actual or 0) + det.cantidad
            prod.save()

            # Movimiento de stock (entrada por anulación)
            MovimientoStock.objects.create(
                fecha=timezone.now(),
                tipo="ENTRADA",
                cantidad=det.cantidad,
                producto=prod,
                usuario=self.usuario  # espejo (Usuarios) si tu Venta.usuario es Usuarios
            )

        # Revertir los ingresos de caja generados por la venta cancelada
        if self.caja_id:
            ingresos_venta = MovimientoCaja.objects.filter(
                caja_usuario__caja=self.caja,
                tipo="INGRESO",
                referencia=str(self.pk)
            )
            for ingreso in ingresos_venta:
                reversa_existente = MovimientoCaja.objects.filter(
                    caja_usuario=ingreso.caja_usuario,
                    tipo="EGRESO",
                    referencia=str(self.pk),
                    monto=ingreso.monto,
                    motivo__icontains="Anulacion venta",
                ).exists()
                if reversa_existente:
                    continue

                MovimientoCaja.registrar_automatico(
                    caja_usuario=ingreso.caja_usuario,
                    tipo="EGRESO",
                    monto=ingreso.monto,
                    motivo=f"Anulacion venta {self.numero_ticket}",
                    referencia=str(self.pk)
                )

        if self.forma_pago == "CUENTA_CORRIENTE" and self.cliente_id:
            cliente = Clientes.objects.select_for_update().get(pk=self.cliente_id)
            saldo_actual = cliente.saldo_cuenta_corriente or 0
            cliente.saldo_cuenta_corriente = max(0, saldo_actual - self.total_neto)
            cliente.save(update_fields=["saldo_cuenta_corriente"])

        self.estado = self.ESTADO_ANULADA
        self.save()


    def __str__(self):
        return f"{self.numero_ticket} ({self.fecha:%d/%m/%Y %H:%M})"

    def _prefijo_negocio(self) -> str:
        det = (self.negocio.detalle or '').strip()
        if not det:
            return "NEG"
        base = slugify(det).replace('-', '').upper()
        return (base[:4] or "NEG")

    def _generar_numeracion_si_falta(self):
        """Genera el número secuencial por negocio y año."""
        if self.pk:
            return
        now = timezone.localtime(self.fecha if self.fecha else timezone.now())
        self.anio = now.year

        ultimo = (
            Venta.objects
            .filter(negocio=self.negocio, anio=self.anio)
            .aggregate(max_n=models.Max('nro_secuencial'))
            .get('max_n')
            or 0
        )
        self.nro_secuencial = ultimo + 1
        pref = self._prefijo_negocio()
        self.numero_ticket = f"{pref}-{self.nro_secuencial:06d}"

    def save(self, *args, **kwargs):
        if self.descuento_global_pct is not None:
            self.descuento_global_pct = max(0, min(self.descuento_global_pct, 100))
        if not self.pk:
            self._generar_numeracion_si_falta()
        super().save(*args, **kwargs)


class VentaDetalle(models.Model):
    """
    Ítems de la venta.
    Desnormaliza nombre del producto y congela precio_unitario.
    """
    id_detalle_venta = models.AutoField(primary_key=True)
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, db_column='id_venta', related_name='detalles')

    producto = models.ForeignKey(
        Productos,
        on_delete=models.PROTECT,
        db_column='id_producto',
        null=True,
        blank=True
    )
    nombre_producto = models.CharField(max_length=120)  # snapshot
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    descuento_item_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = 'detalle_ventas'
        verbose_name = "Detalle de Venta"
        verbose_name_plural = "Detalles de Ventas"
        indexes = [
            models.Index(fields=['venta']),
            models.Index(fields=['producto']),
        ]

    def save(self, *args, **kwargs):
        d = self.descuento_item_pct or 0
        d = max(0, min(d, 100))
        if not self.nombre_producto and self.producto:
            self.nombre_producto = self.producto.descripcion
        if self.cantidad is not None and self.precio_unitario is not None:
            factor = (100 - d) / 100
            self.subtotal = self.cantidad * self.precio_unitario * factor
        super().save(*args, **kwargs)


class VentaPago(models.Model):
    """Desglose de pagos por venta (soporta mixto)."""
    METODO_CHOICES = Venta.FORMAS_PAGO

    id_pago_venta = models.AutoField(primary_key=True)
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, db_column='id_venta', related_name='pagos')
    metodo = models.CharField(max_length=20, choices=METODO_CHOICES)
    monto = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = 'pago_ventas'
        verbose_name = "Pago de Venta"
        verbose_name_plural = "Pagos de Ventas"
        indexes = [
            models.Index(fields=['venta']),
            models.Index(fields=['metodo']),
        ]

    def __str__(self):
        return f"{self.metodo} ${self.monto:.2f}"




# =========================================================
# SECCIÓN 6: MODELOS DE COMPRAS Y PROVEEDORES
# =========================================================

class Compras(models.Model):
    """
    Registra las compras realizadas a proveedores por cada negocio.
    Evolucionada para soportar estados, forma de pago y trazabilidad.
    """
    # Estados
    ESTADO_BORRADOR = "BORRADOR"
    ESTADO_CONFIRMADA = "CONFIRMADA"
    ESTADO_ANULADA = "ANULADA"
    ESTADOS = [
        (ESTADO_BORRADOR, "Borrador"),
        (ESTADO_CONFIRMADA, "Confirmada"),
        (ESTADO_ANULADA, "Anulada"),
    ]

    # Formas de pago
    FP_EFECTIVO = "EFECTIVO"
    FP_TARJETA = "TARJETA"
    FP_TRANSFERENCIA = "TRANSFERENCIA"
    FP_MIXTO = "MIXTO"
    FORMAS_PAGO = [
        (FP_EFECTIVO, "Efectivo"),
        (FP_TARJETA, "Tarjeta"),
        (FP_TRANSFERENCIA, "Transferencia"),
        (FP_MIXTO, "Mixto"),
    ]

    id_compra = models.AutoField(primary_key=True)

    # Negocio (denormalizado para filtrar rápido por negocio)
    negocio = models.ForeignKey(
        TipoNegocio,
        on_delete=models.RESTRICT,
        db_column='id_negocio',
        null=True, blank=True,
        verbose_name="Negocio",
    )

    fecha = models.DateTimeField(default=timezone.now)

    # Trazabilidad operativa (seguimos tu patrón y usamos Usuarios, no auth.User)
    usuario = models.ForeignKey(
        Usuarios, on_delete=models.RESTRICT, db_column='id_usuario',
        null=True, blank=True, related_name='compras_creadas'
    )
    # (opcional) último usuario que actualizó
    usuario_actualiza = models.ForeignKey(
        Usuarios, on_delete=models.RESTRICT, db_column='id_usuario_actualiza',
        null=True, blank=True, related_name='compras_actualizadas'
    )

    proveedor = models.ForeignKey(
        Proveedores, on_delete=models.RESTRICT, db_column='id_proveedor',
        null=True, blank=True
    )

    # Totales y metadatos de comprobante
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    numero_comprobante = models.CharField(max_length=50, blank=True, null=True)
    forma_pago = models.CharField(max_length=20, choices=FORMAS_PAGO, default=FP_EFECTIVO)
    estado = models.CharField(max_length=12, choices=ESTADOS, default=ESTADO_BORRADOR)
    observaciones = models.TextField(blank=True, null=True)

    # Timestamps
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'compras'
        verbose_name = "Compra"
        verbose_name_plural = "Compras"
        ordering = ['-fecha', '-id_compra']
        indexes = [
            models.Index(fields=['negocio', 'fecha']),
            models.Index(fields=['negocio', 'proveedor']),
            models.Index(fields=['estado']),
        ]
        permissions = [
            ("can_confirm_purchase", "Puede confirmar compras"),
            ("can_cancel_purchase", "Puede anular compras"),
        ]

    
    def anular(self, usuario):
        """Anula una compra confirmada y revierte stock"""
        if self.estado != self.ESTADO_CONFIRMADA:
            raise ValueError("Solo se pueden anular compras confirmadas.")

        for det in DetalleCompras.objects.filter(compra=self):
            prod = det.producto
            prod.stock_actual = max(0, prod.stock_actual - det.cantidad)
            prod.save()

        self.estado = self.ESTADO_ANULADA
        self.save()





    def __str__(self):
        return f"Compra {self.id_compra} - {self.fecha:%d/%m/%Y %H:%M}"

    @property
    def total_calculado(self):
        agg = self.detalle_compras.aggregate(
            total=models.Sum(models.F('cantidad') * models.F('costo_unitario'))
        )
        return agg['total'] or 0


class DetalleCompras(models.Model):
    """
    Detalle de productos adquiridos en cada compra.
    Se agregan campos opcionales de vencimiento y lote.
    """
    id_detalle_compra = models.AutoField(primary_key=True)
    compra = models.ForeignKey(
        Compras, on_delete=models.CASCADE, db_column='id_compra',
        null=True, blank=True, related_name='detalle_compras'
    )
    producto = models.ForeignKey(
        Productos, on_delete=models.RESTRICT, db_column='id_producto',
        null=True, blank=True
    )
    cantidad = models.PositiveIntegerField()
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    # Nuevos (opcionales)
    vencimiento = models.DateField(blank=True, null=True)
    lote = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        db_table = 'detalle_compras'
        verbose_name = "Detalle de Compra"
        verbose_name_plural = "Detalles de Compras"
        indexes = [
            models.Index(fields=['compra']),
            models.Index(fields=['producto']),
        ]

    def save(self, *args, **kwargs):
        # Blindaje de integridad: subtotal = cantidad * costo_unitario
        if self.cantidad is not None and self.costo_unitario is not None:
            self.subtotal = self.cantidad * self.costo_unitario
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.producto} x {self.cantidad}"


class ComprobantesCompra(models.Model):
    """
    Comprobantes/adjuntos asociados a una compra (Factura A/B/C, ticket, etc.)
    """
    id_comprobante_compra = models.AutoField(primary_key=True)
    compra = models.ForeignKey(
        Compras, on_delete=models.CASCADE, db_column='id_compra',
        related_name='comprobantes_compra'
    )
    tipo = models.CharField(max_length=10, blank=True, null=True)   # A, B, C, Ticket, etc.
    numero = models.CharField(max_length=50, blank=True, null=True)
    archivo = models.FileField(upload_to='compras/comprobantes/%Y/%m/', blank=True, null=True)
    notas = models.CharField(max_length=200, blank=True, null=True)
    cargado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'comprobantes_compra'
        verbose_name = "Comprobante de Compra"
        verbose_name_plural = "Comprobantes de Compra"
        indexes = [
            models.Index(fields=['compra']),
            models.Index(fields=['tipo', 'numero']),
        ]

    def __str__(self):
        tiponum = " ".join([self.tipo or "", self.numero or ""]).strip()
        return tiponum or f"Comprobante #{self.id_comprobante_compra}"


# ======================================
# RELACIÓN PRODUCTO–PROVEEDOR (EPIC 6 fix)
# ======================================
class ProveedorProducto(models.Model):
    proveedor = models.ForeignKey(
        'Proveedores', on_delete=models.CASCADE, related_name='productos_asociados'
    )
    producto = models.ForeignKey(
        'Productos', on_delete=models.CASCADE, related_name='proveedores_asociados'
    )
    activo = models.BooleanField(default=True)
    precio_referencia = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = 'proveedor_producto'
        unique_together = ('proveedor', 'producto')
        verbose_name = 'Relación Proveedor–Producto'
        verbose_name_plural = 'Relaciones Proveedor–Producto'

    def __str__(self):
        return f"{self.proveedor.razon_social} → {self.producto.descripcion}"



# =========================================================
# SECCIÓN 7: MODELOS DE CAJA Y MOVIMIENTOS AVANZADOS (PR-3)
# =========================================================

class Caja(models.Model):
    ESTADO_ABIERTA = "ABIERTA"
    ESTADO_CERRADA = "CERRADA"
    ESTADOS = [
        (ESTADO_ABIERTA, "Abierta"),
        (ESTADO_CERRADA, "Cerrada"),
    ]

    id_caja = models.AutoField(primary_key=True)
    negocio = models.ForeignKey(TipoNegocio, on_delete=models.RESTRICT, null=True, blank=True)
    descripcion = models.CharField(max_length=100)
    fecha_apertura = models.DateTimeField(default=timezone.now)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    saldo_inicial = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    saldo_final = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=ESTADO_ABIERTA)

    class Meta:
        db_table = "caja"
        permissions = [
            ("can_open_caja", "Puede abrir caja"),
            ("can_close_caja", "Puede cerrar caja"),
            ("can_view_caja", "Puede ver caja"),
        ]

    def calcular_saldo(self):
        # El arqueo registra un recuento de efectivo, pero no debe sumarse como
        # ingreso o egreso operativos al saldo final de la caja.
        ingresos = MovimientoCaja.objects.filter(caja_usuario__caja=self, tipo="INGRESO").aggregate(models.Sum("monto"))["monto__sum"] or 0
        egresos = MovimientoCaja.objects.filter(caja_usuario__caja=self, tipo="EGRESO").aggregate(models.Sum("monto"))["monto__sum"] or 0
        return self.saldo_inicial + ingresos - egresos

    def __str__(self):
        return f"Caja {self.id_caja} ({self.estado})"


class CajaUsuario(models.Model):
    caja = models.ForeignKey(Caja, to_field='id_caja', on_delete=models.CASCADE)
    usuario = models.ForeignKey(Usuarios, on_delete=models.RESTRICT)
    fecha_apertura = models.DateTimeField(default=timezone.now)
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=10, choices=Caja.ESTADOS, default=Caja.ESTADO_ABIERTA)
    saldo_inicial = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    saldo_final = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def cerrar(self):
        self.estado = Caja.ESTADO_CERRADA
        self.fecha_cierre = timezone.now()
        self.save()

    def __str__(self):
        return f"{self.usuario} - {self.estado}"


class MovimientoCaja(models.Model):
    TIPOS = [
        ("INGRESO", "Ingreso"),
        ("EGRESO", "Egreso"),
        ("ARQUEO", "Arqueo"),
    ]

    caja_usuario = models.ForeignKey(CajaUsuario, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=TIPOS)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    motivo = models.CharField(max_length=100)
    referencia = models.CharField(max_length=100, blank=True, null=True)
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "movimientos_caja"

    @classmethod
    def registrar_automatico(cls, caja_usuario, tipo, monto, motivo, referencia=None):
        cls.objects.create(
            caja_usuario=caja_usuario,
            tipo=tipo,
            monto=monto,
            motivo=motivo,
            referencia=referencia,
            fecha=timezone.now()
        )


class MovimientoStock(models.Model):
    TIPOS = [
        ("ENTRADA", "Entrada"),
        ("SALIDA", "Salida"),
        ("AJUSTE", "Ajuste"),
        ("ANULACIÓN", "Anulación"),
    ]

    producto = models.ForeignKey(Productos, on_delete=models.RESTRICT)
    tipo = models.CharField(max_length=15, choices=TIPOS)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    usuario = models.ForeignKey(Usuarios, on_delete=models.RESTRICT)
    motivo = models.CharField(max_length=100)
    negocio = models.ForeignKey(TipoNegocio, on_delete=models.RESTRICT, null=True, blank=True)
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "movimientos_stock"
        permissions = [
            ("can_adjust_stock", "Puede ajustar stock"),
        ]

    @classmethod
    def registrar_automatico(cls, producto, tipo, cantidad, usuario, motivo):
        cls.objects.create(
            producto=producto,
            tipo=tipo,
            cantidad=cantidad,
            usuario=usuario,
            motivo=motivo,
            negocio=producto.negocio,
            fecha=timezone.now()
        )




# =========================================================
# SECCIÓN 8: PAGOS Y AUDITORÍA
# =========================================================


class PagoClientes(models.Model):
    """
    Registra los pagos realizados por los clientes, con descripción y fecha.
    """
    id_pago = models.AutoField(primary_key=True)
    fecha = models.DateTimeField()
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    cliente = models.ForeignKey(Clientes, on_delete=models.RESTRICT, db_column='id_cliente', null=True, blank=True)
    descripcion = models.CharField(max_length=150, blank=True, null=True)

    class Meta:
        db_table = 'pago_clientes'
        verbose_name = "Pago de Cliente"
        verbose_name_plural = "Pagos de Clientes"



class LogAuditoria(models.Model):
    """
    Guarda los registros de auditoría para cada acción realizada por un usuario.
    Permite seguimiento de cambios y trazabilidad del sistema.
    """
    id_log = models.AutoField(primary_key=True)
    fecha_hora = models.DateTimeField(default=timezone.now)
    usuario = models.ForeignKey(Usuarios, on_delete=models.RESTRICT, db_column='id_usuario', null=True, blank=True)
    accion = models.CharField(max_length=100)
    entidad_afectada = models.CharField(max_length=50)
    id_registro = models.PositiveIntegerField()

    class Meta:
        db_table = 'log_auditoria'
        verbose_name = "Log de Auditoría"
        verbose_name_plural = "Logs de Auditoría"




# =========================================================
# SECCIÓN 9: MODELOS DE CUENTAS CORRIENTES Y GESTIÓN DE CRÉDITOS
# =========================================================

class CuentaCorrienteCliente(models.Model):
    """
    Representa la cuenta corriente de un cliente.
    Registra las ventas a crédito, los saldos pendientes y el estado general del crédito.
    """
    id_cuenta = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(Clientes, on_delete=models.RESTRICT, db_column='id_cliente')
    negocio = models.ForeignKey(TipoNegocio, on_delete=models.RESTRICT, db_column='id_negocio')
    fecha_apertura = models.DateField(default=timezone.now)
    saldo_actual = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    limite_credito = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'cuentas_corrientes_clientes'
        verbose_name = "Cuenta Corriente de Cliente"
        verbose_name_plural = "Cuentas Corrientes de Clientes"
        indexes = [
            models.Index(fields=['cliente']),
            models.Index(fields=['negocio']),
            models.Index(fields=['activo']),
        ]

        permissions = [
            ("can_view_cuentas_corrientes", "Puede ver cuentas corrientes"),
        ]


    def __str__(self):
        return f"Cuenta Corriente de {self.cliente.nombre}"


class MovimientoCuentaCorriente(models.Model):
    """
    Detalla los movimientos dentro de la cuenta corriente:
    - Cargos (ventas a crédito)
    - Abonos (pagos, ajustes o descuentos)
    """
    TIPO_MOV = [
        ("CARGO", "Cargo por venta a crédito"),
        ("ABONO", "Pago o ajuste"),
    ]

    id_movimiento = models.AutoField(primary_key=True)
    cuenta = models.ForeignKey(CuentaCorrienteCliente, on_delete=models.CASCADE, related_name='movimientos')
    fecha = models.DateTimeField(default=timezone.now)
    tipo = models.CharField(max_length=10, choices=TIPO_MOV)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    descripcion = models.CharField(max_length=150, blank=True, null=True)
    usuario = models.ForeignKey(Usuarios, on_delete=models.RESTRICT, db_column='id_usuario', null=True, blank=True)

    class Meta:
        db_table = 'movimientos_cuenta_corriente'
        verbose_name = "Movimiento de Cuenta Corriente"
        verbose_name_plural = "Movimientos de Cuenta Corriente"
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.tipo} - ${self.monto:.2f} ({self.fecha:%d/%m/%Y})"


class PagoCuentaCorriente(models.Model):
    """
    Registra los pagos realizados por los clientes a sus cuentas corrientes.
    Permite pagos parciales o totales con fecha y observaciones.
    """
    id_pago_cc = models.AutoField(primary_key=True)
    cuenta = models.ForeignKey(CuentaCorrienteCliente, on_delete=models.CASCADE, related_name='pagos')
    fecha_pago = models.DateField(default=timezone.now)
    monto_pagado = models.DecimalField(max_digits=12, decimal_places=2)
    observaciones = models.CharField(max_length=200, blank=True, null=True)
    usuario_registra = models.ForeignKey(Usuarios, on_delete=models.RESTRICT, db_column='id_usuario', null=True, blank=True)

    class Meta:
        db_table = 'pagos_cuenta_corriente'
        verbose_name = "Pago de Cuenta Corriente"
        verbose_name_plural = "Pagos de Cuentas Corrientes"
        ordering = ['-fecha_pago']

    def __str__(self):
        return f"Pago ${self.monto_pagado:.2f} ({self.fecha_pago})"


class ConfiguracionCredito(models.Model):
    """
    Define reglas generales de crédito y mora para un negocio:
    - Límite de crédito por defecto
    - Porcentaje de interés por mora
    - Días de tolerancia antes de bloqueo
    """
    id_config_credito = models.AutoField(primary_key=True)
    negocio = models.ForeignKey(TipoNegocio, on_delete=models.RESTRICT, db_column='id_negocio')
    limite_por_defecto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    dias_mora = models.PositiveIntegerField(default=0)
    interes_mora = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'configuracion_credito'
        verbose_name = "Configuración de Crédito"
        verbose_name_plural = "Configuraciones de Crédito"

    def __str__(self):
        return f"Regla de crédito para {self.negocio.detalle}"


class EstadoMorosidad(models.Model):
    """
    Controla el estado de morosidad del cliente y su suspensión temporal.
    """
    id_estado_mora = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(Clientes, on_delete=models.RESTRICT, db_column='id_cliente')
    en_mora = models.BooleanField(default=False)
    fecha_inicio_mora = models.DateField(blank=True, null=True)
    fecha_fin_mora = models.DateField(blank=True, null=True)
    motivo = models.CharField(max_length=150, blank=True, null=True)

    class Meta:
        db_table = 'estado_morosidad'
        verbose_name = "Estado de Morosidad"
        verbose_name_plural = "Estados de Morosidad"
        indexes = [
            models.Index(fields=['cliente']),
            models.Index(fields=['en_mora']),
        ]

    def __str__(self):
        return f"{self.cliente.nombre} - {'En mora' if self.en_mora else 'Al día'}"



# =========================================================
# SECCIÓN 10: MODELOS DE ALERTAS Y NOTIFICACIONES INTERNAS
# =========================================================

class AlertaSistema(models.Model):
    """
    Registra las alertas internas del sistema (operativas y automáticas),
    permitiendo su trazabilidad y resolución posterior.
    Incluye alertas por stock bajo, productos vencidos, cuentas en mora,
    irregularidades de caja y avisos generales del sistema.
    """

    # Tipos de alerta
    TIPO_STOCK = "STOCK"
    TIPO_VENCIMIENTO = "VENCIMIENTO"
    TIPO_MORA = "MORA"
    TIPO_CAJA = "CAJA"
    TIPO_GENERAL = "GENERAL"

    TIPOS_ALERTA = [
        (TIPO_STOCK, "Stock Bajo"),
        (TIPO_VENCIMIENTO, "Producto Vencido / Próximo a Vencer"),
        (TIPO_MORA, "Cliente en Mora"),
        (TIPO_CAJA, "Irregularidad en Caja"),
        (TIPO_GENERAL, "Aviso General"),
    ]

    # Niveles de severidad
    NIVEL_INFO = "INFO"
    NIVEL_WARNING = "WARNING"
    NIVEL_CRITICO = "CRITICAL"

    NIVELES = [
        (NIVEL_INFO, "Información"),
        (NIVEL_WARNING, "Advertencia"),
        (NIVEL_CRITICO, "Crítico"),
    ]

    # Estados de la alerta
    ESTADO_PENDIENTE = "PENDIENTE"
    ESTADO_RESUELTA = "RESUELTA"
    ESTADO_DESCARTADA = "DESCARTADA"

    ESTADOS = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_RESUELTA, "Resuelta"),
        (ESTADO_DESCARTADA, "Descartada"),
    ]

    # Identificación y contexto
    id_alerta = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=20, choices=TIPOS_ALERTA, default=TIPO_GENERAL)
    nivel = models.CharField(max_length=10, choices=NIVELES, default=NIVEL_INFO)
    mensaje = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True, null=True)

    # Relaciones
    negocio = models.ForeignKey(TipoNegocio, on_delete=models.RESTRICT, null=True, blank=True)
    usuario_asignado = models.ForeignKey(
        Usuarios, on_delete=models.SET_NULL, null=True, blank=True, related_name="alertas_asignadas"
    )

    # Control y estado
    estado = models.CharField(max_length=12, choices=ESTADOS, default=ESTADO_PENDIENTE)
    creado_en = models.DateTimeField(auto_now_add=True)
    resuelto_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "alertas_sistema"
        verbose_name = "Alerta del Sistema"
        verbose_name_plural = "Alertas del Sistema"
        ordering = ["-creado_en"]
        indexes = [
            models.Index(fields=["tipo"]),
            models.Index(fields=["nivel"]),
            models.Index(fields=["estado"]),
            models.Index(fields=["negocio"]),
        ]

        permissions = [
            ("can_view_alertas", "Puede ver alertas del sistema"),
        ]


    def __str__(self):
        return f"[{self.get_nivel_display()}] {self.get_tipo_display()}: {self.mensaje}"

    # =========================
    # MÉTODOS AUXILIARES
    # =========================
    @classmethod
    def registrar_alerta(cls, tipo, mensaje, nivel=NIVEL_WARNING, negocio=None, usuario=None, descripcion=None):
        """
        Crea una alerta nueva en el sistema, usada por otros módulos (ventas, compras, caja, etc.)
        Ejemplo:
            AlertaSistema.registrar_alerta(
                tipo=AlertaSistema.TIPO_STOCK,
                mensaje="El producto 'Pan Lactal' tiene stock por debajo del mínimo",
                nivel=AlertaSistema.NIVEL_WARNING,
                negocio=producto.negocio,
                usuario=usuario
            )
        """
        return cls.objects.create(
            tipo=tipo,
            mensaje=mensaje,
            nivel=nivel,
            negocio=negocio,
            usuario_asignado=usuario,
            descripcion=descripcion or "",
        )

    @classmethod
    def limpiar_resueltas(cls, dias=30):
        """
        Elimina alertas resueltas o descartadas con antigüedad mayor a 'dias' (por defecto 30).
        Ideal para tareas programadas de mantenimiento o respaldo.
        """
        limite = timezone.now() - timezone.timedelta(days=dias)
        cls.objects.filter(
            estado__in=[cls.ESTADO_RESUELTA, cls.ESTADO_DESCARTADA],
            resuelto_en__lt=limite
        ).delete()


# =========================================================
# SECCIÓN 11: MODELOS DE REPORTES Y GRÁFICOS (EPIC 12)
# =========================================================

class ReporteSistema(models.Model):
    """
    Registra los reportes generados por el sistema (ventas, compras, caja, stock, etc.)
    Permite conservar el historial de reportes creados y los archivos asociados (PDF, PNG, XLSX).
    """

    # Tipos de reporte admitidos
    TIPO_VENTAS = "VENTAS"
    TIPO_COMPRAS = "COMPRAS"
    TIPO_STOCK = "STOCK"
    TIPO_CLIENTES = "CLIENTES"
    TIPO_PROVEEDORES = "PROVEEDORES"
    TIPO_CAJA = "CAJA"
    TIPO_GENERAL = "GENERAL"

    TIPOS_REPORTE = [
        (TIPO_VENTAS, "Reporte de Ventas"),
        (TIPO_COMPRAS, "Reporte de Compras"),
        (TIPO_STOCK, "Reporte de Stock"),
        (TIPO_CLIENTES, "Reporte de Clientes"),
        (TIPO_PROVEEDORES, "Reporte de Proveedores"),
        (TIPO_CAJA, "Reporte de Caja"),
        (TIPO_GENERAL, "Reporte General"),
    ]

    # Identificación
    id_reporte = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=20, choices=TIPOS_REPORTE, default=TIPO_GENERAL)
    titulo = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)

    # Contexto operativo
    negocio = models.ForeignKey(TipoNegocio, on_delete=models.RESTRICT, null=True, blank=True)
    usuario = models.ForeignKey(Usuarios, on_delete=models.SET_NULL, null=True, blank=True)

    # Fechas
    fecha_inicio = models.DateField(blank=True, null=True)
    fecha_fin = models.DateField(blank=True, null=True)
    generado_en = models.DateTimeField(auto_now_add=True)

    # Archivo o gráfico asociado
    archivo = models.FileField(upload_to="reportes/%Y/%m/", blank=True, null=True)
    grafico = models.ImageField(upload_to="reportes/graficos/%Y/%m/", blank=True, null=True)

    class Meta:
        db_table = "reportes_sistema"
        verbose_name = "Reporte del Sistema"
        verbose_name_plural = "Reportes del Sistema"
        ordering = ["-generado_en"]
        indexes = [
            models.Index(fields=["tipo"]),
            models.Index(fields=["negocio"]),
            models.Index(fields=["usuario"]),
        ]

        permissions = [
            ("can_view_reportes", "Puede ver reportes del sistema"),
        ]


    def __str__(self):
        return f"{self.titulo} ({self.get_tipo_display()})"

    # =========================
    # MÉTODOS AUXILIARES
    # =========================
    @classmethod
    def registrar_reporte(cls, tipo, titulo, usuario=None, negocio=None, descripcion=None, archivo=None, grafico=None):
        """
        Crea un nuevo registro de reporte en la base de datos.
        Este método se usará en las views que generen reportes dinámicos.
        """
        return cls.objects.create(
            tipo=tipo,
            titulo=titulo,
            usuario=usuario,
            negocio=negocio,
            descripcion=descripcion or "",
            archivo=archivo,
            grafico=grafico
        )

    @classmethod
    def ultimos(cls, limite=10):
        """
        Devuelve los últimos reportes generados para mostrar en paneles.
        """
        return cls.objects.all().order_by("-generado_en")[:limite]


class ParametroReporte(models.Model):
    """
    Define los parámetros usados al generar un reporte (por ejemplo: rango de fechas, filtro por usuario o negocio).
    Permite registrar los filtros para reproducir reportes antiguos o trazabilidad.
    """
    id_parametro = models.AutoField(primary_key=True)
    reporte = models.ForeignKey(ReporteSistema, on_delete=models.CASCADE, related_name="parametros")
    clave = models.CharField(max_length=50)
    valor = models.CharField(max_length=200)

    class Meta:
        db_table = "parametros_reporte"
        verbose_name = "Parámetro de Reporte"
        verbose_name_plural = "Parámetros de Reporte"
        indexes = [
            models.Index(fields=["reporte"]),
            models.Index(fields=["clave"]),
        ]

    def __str__(self):
        return f"{self.clave}: {self.valor}"





# =========================================================
# SECCIÓN 12: BITÁCORA Y RESPALDO DEL SISTEMA (EPIC 13)
# =========================================================

class BitacoraSistema(models.Model):
    """
    Registra las acciones generales y eventos relevantes del sistema
    que no están cubiertos directamente por LogAuditoria.
    Se utiliza para control de tareas automáticas, mantenimientos,
    respaldos, restauraciones, limpiezas de alertas o reportes, etc.
    """

    id_bitacora = models.AutoField(primary_key=True)
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(Usuarios, on_delete=models.SET_NULL, null=True, blank=True)
    accion = models.CharField(max_length=150)
    detalle = models.TextField(blank=True, null=True)
    exito = models.BooleanField(default=True)

    class Meta:
        db_table = "bitacora_sistema"
        verbose_name = "Bitácora del Sistema"
        verbose_name_plural = "Bitácoras del Sistema"
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["fecha"]),
            models.Index(fields=["usuario"]),
        ]

        permissions = [
            ("can_view_bitacora", "Puede ver bitácora del sistema"),
        ]


    def __str__(self):
        estado = "OK" if self.exito else "Error"
        return f"{self.fecha:%d/%m/%Y %H:%M} - {self.accion} ({estado})"

    @classmethod
    def registrar_evento(cls, accion, usuario=None, detalle="", exito=True):
        """
        Registra un evento del sistema en la bitácora.
        Ejemplo:
            BitacoraSistema.registrar_evento(
                accion="Respaldo automático",
                usuario=request.user,
                detalle="Copia de seguridad completada correctamente"
            )
        """
        return cls.objects.create(accion=accion, usuario=usuario, detalle=detalle, exito=exito)


class RespaldoSistema(models.Model):
    """
    Mantiene el control de los respaldos realizados, permitiendo guardar
    la ubicación del archivo y la fecha en que se generó.
    Permite auditoría sobre la frecuencia y estado de los respaldos.
    """

    id_respaldo = models.AutoField(primary_key=True)
    fecha_respaldo = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(Usuarios, on_delete=models.SET_NULL, null=True, blank=True)
    archivo = models.FileField(upload_to="respaldos/%Y/%m/", blank=True, null=True)
    descripcion = models.CharField(max_length=200, blank=True, null=True)
    exito = models.BooleanField(default=True)

    class Meta:
        db_table = "respaldos_sistema"
        verbose_name = "Respaldo del Sistema"
        verbose_name_plural = "Respaldos del Sistema"
        ordering = ["-fecha_respaldo"]
        indexes = [
            models.Index(fields=["fecha_respaldo"]),
            models.Index(fields=["usuario"]),
        ]

    def __str__(self):
        estado = "OK" if self.exito else "Error"
        return f"Respaldo {self.fecha_respaldo:%d/%m/%Y %H:%M} ({estado})"

    @classmethod
    def registrar_respaldo(cls, usuario=None, archivo=None, descripcion=None, exito=True):
        """
        Crea un nuevo registro de respaldo en la base de datos.
        Ideal para usar tras generar un backup automático o manual.
        """
        return cls.objects.create(
            usuario=usuario,
            archivo=archivo,
            descripcion=descripcion or "",
            exito=exito
        )

    @classmethod
    def limpiar_antiguos(cls, dias=60):
        """
        Elimina respaldos con más de 'dias' días de antigüedad (por defecto 60).
        Puede invocarse desde tareas automáticas.
        """
        limite = timezone.now() - timezone.timedelta(days=dias)
        cls.objects.filter(fecha_respaldo__lt=limite).delete()
