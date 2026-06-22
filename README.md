# Sistema Athenas

## Descripcion

Sistema Athenas es una aplicacion web administrativa y comercial desarrollada con Django. Esta orientada a la gestion diaria de negocios: productos, ventas, compras, caja, stock, clientes, proveedores, cuentas corrientes, alertas, reportes, bitacora y usuarios.

El sistema trabaja con negocio activo, permisos por rol y flujos operativos pensados para punto de venta y administracion interna.

## Estado actual

El sistema cuenta con modulos funcionales para gestion comercial y administrativa. La rama actual incluye correcciones recientes de consistencia en ventas anuladas, caja, cuentas corrientes, pagos de clientes, reportes financieros y stock.

No se deben considerar estos cambios como despliegue productivo final sin una ronda adicional de pruebas con datos reales, backups y configuracion segura de entorno.

## Stack tecnico

- Backend: Python 3.12 y Django 5.
- Base de datos: MySQL 8.
- Frontend/templates: Django Templates, HTML, CSS propio y JavaScript puntual.
- Docker/Docker Compose: servicios `web`, `db` y `phpmyadmin`.
- Dependencias principales:
  - `mysqlclient` para conexion MySQL.
  - `python-dotenv` para configuracion por entorno.
  - `matplotlib` para graficos de reportes.
  - `reportlab` para exportaciones PDF.
  - `openpyxl` para exportaciones Excel.

## Modulos principales

- Dashboard: acceso inicial segun rol y permisos.
- Productos: alta, edicion, filtros, stock, codigo de barras y catalogacion.
- Categorias, marcas y unidades: catalogos auxiliares para productos.
- Ventas: creacion de venta, carrito, pagos, stock y anulacion.
- Ticket de venta: vista imprimible de la operacion.
- Caja: apertura, cierre, arqueo, movimientos, ingresos, egresos y reversas.
- Stock y movimientos: consulta de stock, ajustes y trazabilidad operativa.
- Clientes: gestion de cartera y saldo de cuenta corriente.
- Cuentas corrientes: deudas de clientes, pagos, saldos y proveedor/compras.
- Proveedores: gestion de proveedores y compras asociadas.
- Compras: registro, confirmacion, anulacion y detalle de compras.
- Alertas: stock minimo, vencimientos, morosidad y alertas generales.
- Reportes: ventas, compras, stock, graficos y exportaciones PDF/Excel.
- Bitacora: auditoria de acciones relevantes del sistema.
- Usuarios/permisos: gestion de usuarios, roles y accesos.

## Mejoras recientes aplicadas

- Correccion de paginacion y filtros en productos.
- Manejo de error 403 con redireccion y mensaje claro.
- Mejor visualizacion de stock, estados y botones de filtrado.
- Preservacion de datos al crear categoria, marca o unidad desde producto.
- Visualizacion clara de ventas anuladas.
- Mejoras de carrito, cantidad manual y lector de codigo de barras.
- Pulido del ticket de venta.
- Consistencia entre ventas anuladas y caja mediante reversas.
- Consistencia de cuentas corrientes y pagos de clientes.
- Reportes financieros y stock alineados con filtros, negocio activo y exportaciones.
- Pulido visual general en tablas, filtros, formularios, botones y responsive basico.

## Como levantar el proyecto con Docker

Desde la raiz del proyecto:

```bash
docker compose up -d --build
```

Verificar servicios:

```bash
docker compose ps
```

Ver logs del servicio web:

```bash
docker compose logs -f web
```

Detener servicios:

```bash
docker compose down
```

## URLs locales

- Sistema: `http://localhost:8000`
- Admin Django: `http://localhost:8000/admin/`
- phpMyAdmin: `http://localhost:8080`

## Comandos utiles

Ejecutar dentro del contenedor web:

```bash
docker compose exec web python manage.py check
```

```bash
docker compose exec web python manage.py migrate
```

```bash
docker compose exec web python manage.py makemigrations
```

```bash
docker compose exec web python manage.py createsuperuser
```

Otros comandos utiles:

```bash
docker compose exec web python manage.py shell
```

```bash
docker compose exec web python manage.py test
```

## Flujo Git recomendado

Revisar estado antes de empezar:

```bash
git status
```

Crear una rama por capa de trabajo:

```bash
git checkout -b capa-nombre-del-trabajo
```

Agregar cambios:

```bash
git add .
```

Crear commit:

```bash
git commit -m "Describe el cambio aplicado"
```

Subir rama:

```bash
git push -u origin capa-nombre-del-trabajo
```

Recomendacion: trabajar por capas pequenas y verificables. Evitar mezclar cambios funcionales, visuales y migraciones en un mismo commit salvo que esten directamente relacionados.

## Pruebas manuales recomendadas

- Crear producto.
- Editar producto.
- Crear venta manual.
- Crear venta usando codigo de barras.
- Escanear varias veces el mismo producto y verificar cantidades.
- Editar cantidad manual en carrito.
- Confirmar venta.
- Revisar ticket.
- Anular venta.
- Revisar caja y movimientos de reversa.
- Crear venta a cuenta corriente.
- Registrar pago parcial y total de cliente.
- Revisar cuentas corrientes.
- Revisar reporte de ventas.
- Revisar reporte de compras.
- Revisar reporte de stock.
- Exportar PDF/Excel cuando corresponda.
- Revisar que no aparezcan datos de otro negocio.
- Navegar el sistema en pantalla mediana o angosta.

## Pendientes sugeridos

- Responsive avanzado para pantallas complejas y tablas grandes.
- Mas metricas y graficos en dashboard/reportes.
- Optimizacion de consultas y uso de `select_related`/`prefetch_related` donde haga falta.
- Pruebas automatizadas para ventas, caja, stock, cuentas corrientes y reportes.
- Documentacion tecnica mas profunda de modelos, permisos y flujos.
- Preparacion para despliegue productivo: variables seguras, `DEBUG=False`, backups, logs, HTTPS y servidor WSGI/ASGI.
- Revision de permisos por rol con usuarios reales.

## Notas de mantenimiento

- No hardcodear credenciales en el codigo.
- No borrar ventas, pagos, movimientos ni historial operativo.
- No crear migraciones sin revisar impacto en datos existentes.
- Validar siempre con `python manage.py check` antes de cerrar una capa.
- Comparar exportaciones contra la pantalla correspondiente cuando se ajusten reportes.
