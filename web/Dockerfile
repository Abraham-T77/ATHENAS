FROM python:3.12-slim

# ----------------------------------------------------
# SISTEMA – DEPENDENCIAS PARA MYSQLCLIENT + MATPLOTLIB
# ----------------------------------------------------
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    pkg-config \
    libmariadb-dev \
    libmariadb-dev-compat \
    libfreetype6-dev \
    libpng-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# ----------------------------------------------------
# DIRECTORIO DEL PROYECTO
# ----------------------------------------------------
WORKDIR /app

# Copiar requirements primero (para cache de Docker)
COPY requirements.txt /app/

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar resto del proyecto
COPY . /app/

# Comando de inicio
CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]
