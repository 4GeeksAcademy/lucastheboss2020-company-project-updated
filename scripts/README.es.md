# Carpeta `scripts`

Esta carpeta contiene **scripts auxiliares** del monorepo: automatizaciones de desarrollo, utilidades de mantenimiento, tareas repetitivas (setup, lint, migraciones, generación de datos, etc.) y tooling interno.

- **Propósito principal**: agrupar herramientas de soporte que no pertenecen a una app/agente/pipeline específico, pero facilitan el trabajo del equipo.
- **Recomendación**: documenta cada script (qué hace, parámetros, requisitos, ejemplos de uso) y procura que sean reproducibles (y seguros) en distintos entornos.

## Prueba de almacenamiento de telemetría — `seed_telemetry_proof.py`

Crea + verifica filas en la tabla Supabase `telemetry_events` para el entregable
de la Fase 3 (compañero de `create_telemetry_table.sql`).

- **Crea** eventos deterministas a través de la misma ruta de persistencia de
  producción (`services.telemetry_storage.insert_telemetry_events`), de modo que
  `event_type` y el JSONB `tags` (recortado al allowlist) llegan a la tabla igual
  que con el endpoint real.
- **Verifica** leyendo las filas más recientes e imprime un reporte tabular
  (event_type / service / tags) más la **evidencia de recorte**: un evento
  sembrado incluye claves fuera del allowlist (`password_raw`, `tracking_number`)
  y el reporte confirma que se eliminan del `tags` antes del INSERT.

```bash
# Aplica primero el DDL (editor SQL de Supabase): scripts/create_telemetry_table.sql

# Crea un lote y muestra la tabla (para tu captura de pantalla):
TELEMETRY_DATABASE_URL=postgresql://... python -m scripts.seed_telemetry_proof

# Solo mostrar lo que ya hay en la tabla (sin inserts):
TELEMETRY_DATABASE_URL=postgresql://... python -m scripts.seed_telemetry_proof --verify-only

# Crea un lote mayor:
TELEMETRY_DATABASE_URL=postgresql://... python -m scripts.seed_telemetry_proof --count 20
```

`TELEMETRY_DATABASE_URL` o `DATABASE_URL` deben apuntar a la base PostgreSQL de
Supabase y la tabla debe existir. Código de salida `0` = éxito; el reporte
termina con un veredicto claro ✅/❌ de recorte antes de la captura.
