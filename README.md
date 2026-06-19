# Sistema Athenas

## Descripción breve
Sistema Athenas es una aplicación web Django para la gestión de negocios, incluyendo ventas, compras, stock, caja y reportes. Está pensada como una solución de punto de venta con aislamiento por negocio y control de flujos operativos.

## Stack técnico
- Python 3 / Django
- MySQL 8
- Docker Compose
- OpenPyXL para exportación Excel
- ReportLab para exportación PDF
- Matplotlib para generación de gráficos en reportes

## Estructura general del proyecto
- `docker-compose.yml` - definición de servicios Docker: `db`, `phpmyadmin`, `web`.
- `.env` - variables de entorno para la base de datos y configuración.
- `web/` - aplicación Django principal.
  - `AthenasProyecto/` - configuración Django (`settings.py`, `urls.py`, `wsgi.py`).
  - `AthenasApp/` - código de la aplicación: modelos, vistas, templates, urls, forms, utilidades.
  - `requirements.txt` - dependencias Python.

## Cómo levantar el sistema con Docker Compose
1. Crear y completar el archivo `.env` en la raíz con las credenciales de MySQL.
2. Desde la raíz del proyecto ejecutar:
   ```bash
   docker compose up -d
   ```
3. Para ver logs:
   ```bash
   docker compose logs -f web
   ```
4. Para detener los servicios:
   ```bash
   docker compose down
   ```

## URLs locales importantes
- Aplicación web: `http://localhost:8000`
- PhpMyAdmin: `http://localhost:8080`

## Comandos útiles de Django dentro del contenedor
- Migrar la base de datos:
  ```bash
  docker compose exec web python manage.py migrate
  ```
- Reiniciar el servidor Django (si no se usa `docker compose up`):
  ```bash
  docker compose exec web python manage.py runserver 0.0.0.0:8000
  ```
- Crear superusuario:
  ```bash
  docker compose exec web python manage.py createsuperuser
  ```
- Comprobar el proyecto:
  ```bash
  docker compose exec web python manage.py check
  ```
- Ejecutar tests:
  ```bash
  docker compose exec web python manage.py test
  ```

## Flujo básico de trabajo con Git
1. Crear rama para cambios:
   ```bash
   git checkout -b capa-1a-estabilidad
   ```
2. Revisar estado antes de trabajar:
   ```bash
   git status
   ```
3. Añadir cambios y confirmar:
   ```bash
   git add .
   git commit -m "Capa 1A: estabilidad operativa y correcciones de caja/ventas"
   ```
4. Sincronizar con el remoto:
   ```bash
   git fetch origin
   git rebase origin/main
   git push -u origin capa-1a-estabilidad
   ```

## Estado actual del proyecto
- Rama activa: `capa-1a-estabilidad`.
- Corrección aplicada en `web/AthenasApp/models.py` para mejorar la anulación de ventas y preservar la consistencia de caja.
- El cálculo de saldo de caja ya considera solo movimientos de tipo `INGRESO` y `EGRESO`, evitando sumar movimientos de `ARQUEO` como flujo operativo.
- No se generaron migraciones porque los cambios son de lógica y de elección de tipo de movimiento.
- Hay una dependencia de entorno pendiente: el comando `python manage.py check` en el entorno local falla si no está instalado `matplotlib`.

## Próximas mejoras pendientes
- Revisar el flujo de anulación para ventas con pagos mixtos y abonos parciales.
- Añadir validación de integridad extra en `Venta.anular()` para no generar reversión doble si la venta ya tiene movimientos de reversión.
- Mejorar el control de caja para que el arqueo sea un registro separado de conciliación y no se muestre como movimiento operativo en los listados financieros.
- Auditar el uso de `CajaUsuario` para verificar cierres de usuario independientes.

## Riesgos pendientes
- Dependencia de `matplotlib` requerida por la app de reportes; el entorno de desarrollo debe instalarla para ejecutar `manage.py check` y servir reportes.
- El cálculo de saldo de caja es correcto para los tipos actuales, pero la lógica del cierre depende de que no existan otros tipos de movimientos operativos no contemplados.
- Las pruebas automatizadas no se han ejecutado en el contenedor tras la corrección.

## Pruebas manuales recomendadas
1. Abrir una caja y verificar que `saldo_final` inicial queda igual a `saldo_inicial` antes de movimientos.
2. Realizar una venta confirmada y comprobar que se genera `MovimientoCaja` de tipo `INGRESO`.
3. Anular esa venta y comprobar que se crea un movimiento `EGRESO` de reversión con mismo monto.
4. Cerrar la caja y verificar que `Caja.calcular_saldo()` usa `INGRESO` menos `EGRESO`, sin sumar `ARQUEO`.
5. Registrar un arqueo de caja y confirmar que aparece en la lista de movimientos, pero no altera el saldo final operado.
6. Revisar el historial de `MovimientoStock` para asegurar que la anulación repone stock y registra `ENTRADA`.
