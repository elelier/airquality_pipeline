# Roadmap – Pipeline de Calidad del Aire

Este documento describe las metas y mejoras planeadas para evolucionar el pipeline. Las fechas son aproximadas y los hitos podrán ajustarse según prioridades y resultados durante el desarrollo.

## Fase 1: Consolidación y Estabilización (Corto Plazo – Q2 2025)
- **Estabilización de la Integración**  
  - Verificar y mejorar la confiabilidad del pipeline mediante pruebas unitarias e integración continua.  
  - Reforzar el manejo de errores y alertas, incluyendo notificaciones mediante Telegram para incidencias críticas.  
- **Documentación y Monitorización**  
  - Completar la documentación del proyecto (README, comentarios en el código, roadmap).
  - Implementar un dashboard básico de monitorización (logs, métricas de actualización y errores).  
- **Optimización de Procesos**  
  - Revisar el proceso de sincronización para optimizar consultas a Supabase.
  - Validar la estrategia de reintentos y ajustar tiempos de espera según el rendimiento.

## Fase 2: Ampliación de Funcionalidades (Mediano Plazo – Q3 2025)
- **Nuevas Fuentes y Enriquecimiento de Datos**  
  - Integrar datos de fuentes complementarias (por ejemplo, sensores locales o datos gubernamentales) para enriquecer la información de calidad del aire.
  - Implementar un sistema de fusión de datos (data fusion) para mejorar la precisión de las mediciones.
- **Interfaz y Experiencia de Usuario**  
  - Desarrollar una interfaz web/portal que permita visualizar gráficos y tendencias en tiempo real.
  - Permitir configuraciones personalizadas para notificaciones (umbrales, horarios, etc.).
- **Automatización y Escalabilidad**  
  - Revisar la arquitectura para soportar mayor volumen de datos y escalado horizontal.
  - Agregar tests de performance y carga al pipeline.

## Fase 3: Innovación y Expansión (Largo Plazo – Q4 2025 en adelante)
- **Inteligencia Artificial y Análisis Predictivo**  
  - Implementar modelos predictivos para anticipar cambios en la calidad del aire.
  - Integrar alertas inteligentes basadas en aprendizaje automático.
- **Expansión Geográfica y Multi-API**  
  - Ampliar el pipeline para soportar datos de otras ciudades o regiones con diferentes proveedores de datos.
  - Implementar un sistema modular que permita conectar nuevas APIs de medición de la calidad del aire de forma sencilla.
- **Integraciones Adicionales y Ecosistema IoT**  
  - Integrar con plataformas de IoT para recopilar datos en tiempo real de sensores distribuidos.
  - Desarrollar integraciones con plataformas de terceros y servicios de análisis en la nube.

## Consideraciones Finales
- **Feedback Continuo:**  
  - Se mantendrá una retroalimentación constante desde la comunidad y usuarios finales para ajustar prioridades y nuevas funcionalidades.
- **Actualizaciones del Roadmap:**  
  - Este roadmap se revisará y actualizará de forma trimestral para reflejar avances y cambios en el entorno tecnológico.
