# 🌍 Pipeline de Calidad del Aire - Monterrey Respira

## 📋 Descripción
Sistema automatizado que monitorea la calidad del aire en 10 ciudades del área metropolitana de Monterrey, México. Obtiene datos de la API de IQAir (AirVisual) y los almacena en Supabase para alimentar el dashboard [mtyrespira.elelier.com](https://mtyrespira.elelier.com).

## 🏗️ Arquitectura

### 📊 Stack Tecnológico
- **Frontend**: React + Vite desplegado en Cloudflare Pages
- **Backend**: Supabase (PostgreSQL) con tablas `cities` y `air_quality_readings`
- **Pipeline**: Python + GitHub Actions (ejecución cada hora)
- **API de Datos**: IQAir (AirVisual) v2 API (~10,000 llamadas/mes)

### 🏙️ Ciudades Monitoreadas (9)
1. Monterrey (ID: 9)
2. San Nicolas de los Garza (ID: 11)
3. San Pedro Garza Garcia (ID: 12)
4. Guadalupe (ID: 7)
5. Santa Catarina (ID: 13)
6. General Escobedo (ID: 6)
7. Garcia (ID: 5)
8. Ciudad Benito Juárez (ID: 4)
9. Cadereyta Jimenez (ID: 1)

**Nota**: Apodaca (ID: 2) no tiene estación de monitoreo en AirVisual API.

### ⚙️ Estrategia de Actualización
- **Frecuencia**: Cada hora (cron: `0 * * * *`)
- **Lógica inteligente**: Solo actualiza ciudades con datos > 59 minutos de antigüedad
- **Rate limit handling**: 
  - 3 reintentos automáticos con exponential backoff
  - Delay entre ciudades: 8-15s con jitter aleatorio
  - Timeout de 45s por request HTTP
- **Validación de datos**: 
  - Rechaza AQI fuera de rango 0-500
  - Rechaza temperatura < -50°C o > 60°C
  - Valida coordenadas dentro de Nuevo León (lat 25-26.5, lon -101 a -99)
- **Sincronización automática**: Los nombres de ciudades en BD coinciden exactamente con API para evitar desactivaciones

## 📊 Estado del Pipeline (Enero 2026)
✅ **Todas las 9 ciudades se actualizan exitosamente cada hora**
- ✅ Integración backend ↔ frontend funcionando
- ✅ Datos visibles en dashboard en tiempo real
- ✅ Sin desactivaciones automáticas
- ✅ Rate limiting manejado correctamente

## 🏗️ Componentes del Sistema

### 📦 Componentes Principales
- **airvisual_api.py** 🔗: Interfaz con la API de AirVisual.
- **supabase_client.py** 🗄️: Manejo de la base de datos.
- **sync_cities.py** 🔄: Sincronización de datos de ciudades.
- **update_city.py** ⚡: Actualización de datos de calidad del aire.
- **utils.py** 🔧: Funciones auxiliares y utilidades.
- **main.py** 🚀: Punto de entrada principal del sistema.

## 🔔 Nuevo Componente

### air_quality_alert.py 🚨
- **Descripción** 📝: Componente encargado de enviar alertas sobre la calidad del aire a través de Telegram en caso de que los valores superen un umbral crítico.
- **Responsabilidades** 📋:
  - Conectar con la API de AirVisual para obtener los niveles de calidad del aire.
  - Verificar si los niveles de calidad del aire superan un umbral predefinido.
  - Enviar un mensaje a un bot de Telegram con la alerta si los niveles son peligrosos.

### 🛠️ Ejemplo de Uso
Para utilizar este componente, simplemente invoca la función `send_air_quality_alert()` de `air_quality_alert.py` después de cada sincronización o actualización de datos:

```python
from air_quality_alert import send_air_quality_alert

# Verifica si la calidad del aire en una ciudad supera el umbral crítico
send_air_quality_alert(city_id, air_quality_data)
```

## 📋 Requisitos

### 🐍 Dependencias
Este proyecto requiere Python 3.11 y las siguientes dependencias:

```
requests>=2.31.0
supabase>=1.0.0
python-dotenv>=1.0.0
pyjwt>=2.8.0
python-telegram-bot>=13.0
```

### 🔐 Variables de Entorno
Asegúrate de agregar las siguientes variables al archivo `.env` en la raíz del proyecto:

- **AIRVISUAL_API_KEY** 🔑: Clave de API de AirVisual (obtenida desde AirVisual).
- **SUPABASE_URL** 🌐: URL de la base de datos Supabase.
- **SUPABASE_SERVICE_ROLE_KEY** 🔑: Clave de rol de servicio de Supabase.
- **TELEGRAM_BOT_API_KEY** 🔑: Clave de API de tu bot de Telegram.
- **TELEGRAM_CHAT_ID** 📝: ID del chat de Telegram donde se enviarán las alertas.

## 🛠️ Instalación

1. 📋 Clona el repositorio.
2. 🔑 Crea el archivo `.env` con las variables necesarias.
3. 📦 Instala las dependencias:

```
pip install -r requirements.txt
```

## 🚀 Uso

### 🖥️ Ejecución Local
Para ejecutar el sistema de manera local, utiliza el siguiente comando:

```
python main.py
```

### 🤖 Automatización
El sistema está configurado para ejecutarse automáticamente cada 3 horas a través de GitHub Actions.

## 📊 Estructura de Datos

### 📊 Tabla `cities`
- **id** 🔢: Identificador único de la ciudad.
- **name** 🏙️: Nombre de la ciudad.
- **api_name** 🌐: Nombre usado en la API.
- **is_active** ✅: Estado de la ciudad.
- **last_successful_update_at** ⏱️: Última actualización exitosa.
- **last_update_status** 📝: Estado del último intento de actualización.

## ✨ Características Principales

### 🔄 Sistema de Sincronización
- Agregado automático de nuevas ciudades 🏗️.
- Desactivación de ciudades obsoletas ❌.
- Validación de datos 🔍.
- Resumen de operaciones 📋.

### ⚡ Manejo de Actualizaciones
- Intervalo de actualización: 59 minutos ⏱️.
- Sistema de reintentos 🔁.
- Logging detallado 📝.
- Manejo de estados 📊.

## 🔧 Mantenimiento

### 📝 Logging
- Registro detallado de operaciones 📋.
- Seguimiento de errores 🚨.
- Resumen de operaciones 📊.

### 📊 Monitoreo
- Estado de actualizaciones 📊.
- Tiempos de respuesta ⏱️.
- Errores y excepciones 🚨.

## 🔐 Seguridad

- Variables sensibles en `.env` 🔑.
- Validación de configuración 🔍.
- Manejo seguro de claves API 🔑.
- Permisos en Supabase 🔐.

## 🤝 Contribución

1. 📝 Revisar el archivo `roadmap.md` para ver las metas y mejoras planeadas.
2. 🌱 Crear una rama para nuevas características.
3. 🔧 Realizar cambios y pruebas.
4. 📝 Crear Pull Request.
5. 👀 Esperar revisión y aprobación.

## 📄 Licencia

MIT.
