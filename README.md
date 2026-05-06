# 🌍 Pipeline de Calidad del Aire - Monterrey Respira

## 📋 Descripción
Sistema automatizado que monitorea la calidad del aire en ciudades del área metropolitana de Monterrey, México. Obtiene datos desde WAQI/AQICN como proveedor activo y los almacena en Supabase para alimentar el dashboard [mtyrespira.elelier.com](https://mtyrespira.elelier.com).

## 🏗️ Arquitectura

### 📊 Stack Tecnológico
- **Frontend**: React + Vite desplegado en Cloudflare Pages
- **Backend**: Supabase (PostgreSQL) con tablas `cities` y `air_quality_readings`
- **Pipeline**: Python + GitHub Actions (ejecución cada hora)
- **API de Datos activa**: WAQI/AQICN station feed API
- **API legacy/fallback**: IQAir/AirVisual v2 API. Actualmente responde HTTP 402 Payment Required con la key existente.

### 🏙️ Ciudades Monitoreadas

El pipeline conserva las ciudades existentes en Supabase y usa `city_id` como identidad estable. Con WAQI, la cobertura productiva depende de un mapeo explícito ciudad → estación.

#### Cobertura WAQI esperada para ciudades activas

| Ciudad activa | Estado WAQI | Estación | Evidencia |
| --- | --- | --- | --- |
| Monterrey | Verificada por página pública AQICN + validación runtime | `@6492` | Obispado, Nuevo León / Cloud API H6492. |
| San Nicolas de los Garza | Verificada | `@6493` | Mapping inicial validado en PR #3. |
| Guadalupe | Verificada | `@6494` | Mapping inicial validado en PR #3. |
| San Pedro Garza Garcia | Verificada | `@8282` | Mapping inicial validado en PR #3. |
| Santa Catarina | Verificada por página pública AQICN + validación runtime | `@6491` | S. Catarina, Nuevo León / Cloud API H6491. |
| General Escobedo | Verificada por página pública AQICN + validación runtime | `@6496` | Escobedo, Nuevo León / Cloud API H6496. |
| Garcia | Verificada por página pública AQICN + validación runtime | `@6495` | Garcia, Nuevo León / Cloud API H6495. |
| Ciudad Benito Juarez | Verificada por página pública AQICN + validación runtime | `@8113` | Juarez, Nuevo León / Cloud API H8113. |
| Cadereyta Jimenez | Verificada por página pública AQICN + validación runtime | `@10950` | Cadereyta, Monterrey, Nuevo León / Cloud API H10950. |

Las estaciones quedan sujetas a validación runtime antes de insertar: `status=ok`, AQI, timestamp y coordenadas dentro de Nuevo León. Si WAQI devuelve payload inválido o fuera de rango, el pipeline falla cerrado y no inserta lectura.

#### Criterio para habilitar o cambiar una estación WAQI

Antes de reemplazar cualquier `station_id` en `waqi_api.py`, validar en un run manual/runtime:

- WAQI feed real responde `status=ok`.
- Payload contiene AQI válido.
- Payload contiene timestamp válido.
- Payload contiene coordenadas dentro de Nuevo León: lat `25.0..26.5`, lon `-101.0..-99.0`.
- La estación corresponde razonablemente al municipio y no solo a una ciudad cercana.

Si cualquier punto queda dudoso, mantener o regresar el mapping a `None` + TODO explícito.

### ⚙️ Estrategia de Actualización
- **Frecuencia**: Cada hora (cron: `0 * * * *`)
- **Proveedor default**: `AIR_QUALITY_PROVIDER=waqi`
- **Lógica inteligente**: Solo actualiza ciudades con datos > 59 minutos de antigüedad, salvo `--force-update`
- **Rate limit handling**: 
  - Delay entre ciudades: 8-15s con jitter aleatorio
  - Timeout de 45s por request HTTP
- **Validación de datos**: 
  - Rechaza AQI fuera de rango 0-500
  - Rechaza temperatura < -50°C o > 60°C
  - Valida coordenadas dentro de Nuevo León (lat 25-26.5, lon -101 a -99)
- **Fail-closed**: Si faltan AQI, timestamp, coordenadas o mapeo de estación, se actualiza `cities.last_update_status` con `error:*` y no se inserta lectura.

## 📊 Estado del Pipeline (Mayo 2026)

- IQAir/AirVisual dejó de ser proveedor activo porque el endpoint `/v2/cities` responde HTTP 402 Payment Required.
- WAQI/AQICN es el proveedor activo para estaciones verificadas.
- La cobertura esperada de ciudades activas vive en `waqi_api.EXPECTED_ACTIVE_API_NAMES`.
- Las estaciones se trazan en logs por `provider_station_id` sin exponer tokens.
- Supabase y la RPC `get_latest_air_quality_per_city` se mantienen sin cambios.

## 🏗️ Componentes del Sistema

### 📦 Componentes Principales
- **waqi_api.py** 🔗: Adapter activo para WAQI/AQICN y registry fail-closed de estaciones.
- **airvisual_api.py** 🧭: Adapter legacy/fallback para IQAir/AirVisual.
- **supabase_client.py** 🗄️: Manejo de la base de datos.
- **sync_cities.py** 🔄: Sincronización de datos de ciudades. En WAQI no desactiva ciudades por lista upstream.
- **update_city.py** ⚡: Actualización de datos de calidad del aire.
- **utils.py** 🔧: Funciones auxiliares y utilidades.
- **main.py** 🚀: Punto de entrada principal del sistema.

## 📋 Requisitos

### 🐍 Dependencias
Este proyecto requiere Python 3.11 y las siguientes dependencias:

```
requests>=2.31.0
supabase>=1.0.0
python-dotenv>=1.0.0
pyjwt>=2.8.0
python-telegram-bot>=13.0
pytest>=7.4.0
```

### 🔐 Variables de Entorno

Variables requeridas para WAQI:

- **AIR_QUALITY_PROVIDER**: Proveedor activo. Default: `waqi`.
- **WAQI_API_TOKEN**: Token de API de WAQI/AQICN.
- **SUPABASE_URL**: URL de la base de datos Supabase.
- **SUPABASE_SERVICE_ROLE_KEY**: Clave de rol de servicio de Supabase.

Variables legacy/fallback para AirVisual:

- **AIRVISUAL_API_KEY**: Clave de API de AirVisual. Solo se usa si `AIR_QUALITY_PROVIDER=airvisual`.

Variables opcionales de alertas:

- **TELEGRAM_BOT_API_KEY**
- **TELEGRAM_CHAT_ID**

## 🛠️ Instalación

1. Clona el repositorio.
2. Crea el archivo `.env` con las variables necesarias.
3. Instala las dependencias:

```
pip install -r requirements.txt
```

## 🚀 Uso

### 🖥️ Ejecución Local con WAQI

```
AIR_QUALITY_PROVIDER=waqi python main.py
```

### 🔁 Ejecución Local Forzada

```
AIR_QUALITY_PROVIDER=waqi python main.py --force-update
```

### 🧭 Rollback a AirVisual si se recupera IQAir

```
AIR_QUALITY_PROVIDER=airvisual python main.py --force-update
```

### 🤖 Automatización
El sistema está configurado para ejecutarse automáticamente cada hora a través de GitHub Actions.

## 📊 Estructura de Datos

### 📊 Tabla `cities`
- **id**: Identificador único de la ciudad.
- **name**: Nombre de la ciudad.
- **api_name**: Nombre usado para mapear proveedor.
- **is_active**: Estado de la ciudad.
- **last_successful_update_at**: Última actualización exitosa.
- **last_update_status**: Estado del último intento de actualización.

### 📊 Tabla `air_quality_readings`
- **city_id**: Identificador estable de ciudad.
- **reading_timestamp**: Timestamp UTC de medición origen.
- **aqi_us**: AQI normalizado.
- **main_pollutant_us**: Contaminante principal si el proveedor lo entrega.
- **temperature_c**, **humidity_percent**, **wind_speed_ms**, **wind_direction_deg**: Campos meteorológicos si están disponibles.
- **raw_api_response**: Respuesta cruda del proveedor.

## ✨ Características Principales

### 🔄 Sistema de Proveedores
- WAQI/AQICN como provider activo.
- AirVisual como fallback explícito.
- Selección vía `AIR_QUALITY_PROVIDER`.
- Fail-closed para ciudades sin mapping o payload no confiable.

### ⚡ Manejo de Actualizaciones
- Intervalo de actualización: 59 minutos.
- Logging detallado.
- Resumen de operaciones.
- Estados operativos `success`, `error:*`, `skipped:*`.

## 🔧 Mantenimiento

### 📝 Logging
- Registro detallado de operaciones.
- Seguimiento de errores.
- Resumen operacional `[SUMMARY] Pipeline operacional`.
- No se deben exponer tokens en logs.

### 📊 Monitoreo
- Estado de actualizaciones por ciudad.
- Tiempos de respuesta.
- Errores y excepciones.
- Revisión de `pipeline.log` en GitHub Actions.

## 🔐 Seguridad

- Variables sensibles en `.env` y GitHub Actions Secrets.
- No exponer `WAQI_API_TOKEN`, `AIRVISUAL_API_KEY` ni `SUPABASE_SERVICE_ROLE_KEY`.
- Permisos en Supabase mediante service role solo en pipeline.

## 📌 Atribución

Los datos obtenidos desde WAQI/AQICN requieren atribución al World Air Quality Index Project y a la EPA/fuente originadora correspondiente. Mantener esta atribución visible en documentación y, si aplica, en la UI pública.

## 📄 Licencia

MIT.
