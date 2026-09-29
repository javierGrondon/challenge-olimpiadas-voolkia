# Documentación Técnica — Pipeline Olimpiadas 2026

*2026-09-29 · Javier Grondon*

Este documento describe la arquitectura, decisiones técnicas y procedimientos del pipeline construido para analizar el impacto de los Juegos Olímpicos 2026 en las ventas de un marketplace deportivo latinoamericano.

---

## Contexto y objetivo

Un marketplace deportivo latinoamericano necesitaba medir el impacto de los Juegos Olímpicos (14–30 jul 2026) en sus ventas. El área de Reporting requirió un análisis que respondiera:

- ¿Cuánto creció el revenue durante el evento vs. semanas normales?
- ¿Qué países y categorías lideraron?
- ¿Cuánto duró el efecto post-evento?
- ¿Los vendedores oficiales aprovecharon el evento mejor que los particulares?

El dataset cubre 30.871 transacciones de mayo a agosto 2026, sobre un catálogo de 700 productos en 8 categorías, con ventas en Brasil, Argentina y Colombia.

---

## Arquitectura Medallion

El pipeline sigue el patrón medallón en tres capas, cada una con una responsabilidad clara y almacenada en su propio dataset de BigQuery.

### Bronze — Ingesta cruda

Dataset: `olimpiadas_bronze`. Todas las columnas se almacenan como STRING para garantizar que ningún dato se pierda en la ingesta. La tabla `ventas_raw` replica el CSV fuente. Carga con WRITE_TRUNCATE (idempotente: re-correr el pipeline no duplica filas).

### Silver — Tipado y enriquecimiento

Dataset: `olimpiadas_silver`. Dos tablas: `ventas` (FLOAT64, DATE, INT64) y `productos` (catálogo enriquecido). Python calcula los campos de negocio: `es_olimpico`, `tipo_vendedor` (oficial | particular) y `periodo` (pre_evento | durante | post_evento) según las fechas en `.env`.

### Gold — Agregaciones para análisis

Dataset: `olimpiadas_gold`. Seis tablas de KPIs pre-agregadas: `kpis_generales`, `revenue_por_periodo`, `revenue_por_pais`, `revenue_semanal`, `revenue_por_categoria`, `vendedor_tipo_por_periodo`. Las vistas `v_*` se crean encima y son las que consume Looker Studio, evitando JOINs costosos en cada recarga.

**Flujo:** CSV → Bronze (strings) → Silver (tipado + negocio) → Gold (KPIs) → Vistas v_* → Looker Studio

---

## Decisiones técnicas

**Python + pandas sobre SQL puro.** La lógica de clasificación de productos (`es_olimpico`, `tipo_vendedor`, `periodo`) requiere lógica condicional con variables externas (`.env`). Python es más legible y testeable que stored procedures en BigQuery.

**WRITE_TRUNCATE en cada capa.** Hace el pipeline idempotente: correrlo dos veces produce el mismo resultado. Elimina la necesidad de lógica de upsert o deduplicate.

**Bronze recibe todo como STRING.** Protege contra fuentes con formatos inconsistentes (fechas, montos con coma decimal). El tipado se hace una sola vez en Silver, con validación explícita.

**Se clasifican TODAS las categorías, no solo las deportivas.** Los licenciatarios oficiales publican en mochilas, botellas y calzado, no solo en camisetas. Filtrar por categoría hubiera perdido revenue olímpico real.

**Variables de configuración en `.env`.** Cuatro variables controlan todo el comportamiento del evento: `KEYWORDS_EVENTO`, `VENDEDORES_OFICIALES`, `FECHA_INICIO_EVENTO` y `FECHA_FIN_EVENTO`. Cambiarlas adapta el pipeline a cualquier otro evento sin tocar código.

**Vistas `v_*` sobre tablas Gold.** Looker Studio apunta a vistas, no a tablas. Si se renombra una tabla Gold, solo se actualiza la vista; los dashboards no se rompen.

---

## Estructura de tablas

### Bronze — olimpiadas_bronze

**ventas_raw:** `fecha` STRING, `producto_id` STRING, `vendedor_id` STRING, `pais` STRING, `categoria` STRING, `unidades` STRING, `monto_usd` STRING, `titulo` STRING

### Silver — olimpiadas_silver

**ventas:** `fecha` DATE, `producto_id` INT64, `vendedor_id` INT64, `pais` STRING, `categoria` STRING, `unidades` INT64, `monto_usd` FLOAT64, `periodo` STRING

**productos:** `producto_id` INT64, `titulo` STRING, `categoria` STRING, `vendedor_id` INT64, `tipo_vendedor` STRING, `es_olimpico` BOOL

### Gold — olimpiadas_gold

**kpis_generales:** `revenue_total_usd` FLOAT64, `revenue_olimpico_usd` FLOAT64, `pct_revenue_olimpico` FLOAT64, `unidades_total` INT64, `unidades_olimpicas` INT64, `transacciones_total` INT64, `transacciones_olimpicas` INT64

**revenue_por_periodo:** `periodo` STRING, `transacciones` INT64, `unidades` INT64, `revenue_usd` FLOAT64

**revenue_por_pais:** `pais` STRING, `periodo` STRING, `transacciones` INT64, `unidades` INT64, `revenue_usd` FLOAT64

**revenue_semanal:** `semana` DATE, `transacciones` INT64, `unidades` INT64, `revenue_usd` FLOAT64

**revenue_por_categoria:** `categoria` STRING, `periodo` STRING, `transacciones` INT64, `unidades` INT64, `revenue_usd` FLOAT64

**vendedor_tipo_por_periodo:** `tipo_vendedor` STRING, `periodo` STRING, `transacciones` INT64, `unidades` INT64, `revenue_usd` FLOAT64

---

## Cómo correr el pipeline

### Prerequisitos

- Python 3.9+
- Cuenta de servicio de Google Cloud con permisos BigQuery Data Editor y Job User
- Archivo JSON de la cuenta de servicio (**NO subir al repo**)

### Instalación de dependencias

```bash
pip install google-cloud-bigquery pandas python-dotenv
```

### Configuración del .env

Crear el archivo `.env` en la raíz del proyecto (nunca commitear):

```
GOOGLE_APPLICATION_CREDENTIALS=cellular-effect-506218-h7-bfacbe309cc6.json
BIGQUERY_PROJECT=cellular-effect-506218-h7
FECHA_INICIO_EVENTO=2026-07-14
FECHA_FIN_EVENTO=2026-07-30
KEYWORDS_EVENTO=olimpia,ol.mpic,juegos ol
```

### Ejecución

```bash
python scripts/load_to_bigquery.py
```

El script carga Bronze, Silver y Gold en ese orden. Al final imprime un resumen con el conteo de filas en cada tabla.

### Creación de vistas (una sola vez)

Copiar la Sección 3 de `sql/queries_olimpiadas.sql` y ejecutarla en BigQuery Console. Las vistas se actualizan solas cuando el pipeline vuelve a correr.

### Verificación rápida

Ejecutar la Query 1 del archivo SQL para confirmar que los KPIs generales tienen datos. Si `revenue_olimpico_usd` es 0, verificar que las keywords en `.env` coinciden con los títulos reales de los productos.

---

## Vistas y Looker Studio

Las vistas `v_*` en `olimpiadas_gold` actúan como capa de abstracción entre las tablas Gold y el dashboard. Looker Studio apunta a vistas, no a tablas: si el schema de una tabla cambia, solo se actualiza la vista.

### Vistas disponibles

**v_kpis_generales** — Un único registro con los KPIs del período completo. Ideal para scorecards de resumen en la parte superior del dashboard.

**v_revenue_por_periodo** — Revenue, unidades y transacciones agrupados por período (pre / durante / post). Incluye ticket promedio calculado y campo `orden_periodo` (1/2/3) para ordenar correctamente en Looker.

**v_revenue_por_pais** — Mismo desglose por país y período. Permite comparar cómo impactó el evento en cada mercado.

**v_revenue_semanal** — Evolución semana a semana con variación porcentual calculada vía función de ventana `LAG()`. Permite graficar el "efecto olímpico" y cuánto duró post-evento.

**v_revenue_por_categoria** — Desglose por categoría y período. Identifica qué tipo de producto traccionó más durante el evento.

**v_vendedor_tipo_por_periodo** — Oficial vs particular por período. Mide si el merchandising oficial tuvo mayor ticket promedio o share de revenue.

**v_share_olimpico** — Compara revenue olímpico vs total del marketplace durante el evento. KPI clave para el resumen ejecutivo.

### Conexión en Looker Studio

1. Nueva fuente de datos → BigQuery
2. Proyecto: `cellular-effect-506218-h7`
3. Dataset: `olimpiadas_gold`
4. Seleccionar la vista deseada (prefijo `v_`)
5. Repetir para cada vista que necesite el dashboard

---

## Reutilización para otros eventos

El pipeline fue diseñado para adaptarse a cualquier evento deportivo con cero cambios en el código. Solo hay que actualizar cuatro variables en `.env`:

| Variable | Descripción | Ejemplo Copa América |
|---|---|---|
| `KEYWORDS_EVENTO` | Palabras clave en títulos de productos | `copa america,copa am.rica,mundial` |
| `VENDEDORES_OFICIALES` | IDs de licenciatarios oficiales del evento | `800100,800200,800300` |
| `FECHA_INICIO_EVENTO` | Inicio del período 'durante' | `2027-06-14` |
| `FECHA_FIN_EVENTO` | Fin del período 'durante' | `2027-07-14` |

Luego correr `python scripts/load_to_bigquery.py` y las tres capas se reconstruyen con la nueva clasificación. Las vistas `v_*` en BigQuery se actualizan automáticamente. El dashboard en Looker Studio no necesita cambios.

> El archivo `.env.example` en el repo documenta todas las variables con sus valores de ejemplo y comentarios explicativos.

---

## Versiones y roadmap

### v1.0 — MVP (actual)

- Pipeline Bronze / Silver / Gold en un solo script Python
- Clasificación de productos olímpicos por keywords y vendedores oficiales, configurables desde `.env`
- 6 tablas Gold + 7 vistas BigQuery para Looker Studio
- Dataset de 30.871 transacciones, mayo–agosto 2026
- Reutilizable para cualquier evento cambiando solo `.env`

### Mejoras futuras (v1.1+)

- **Tests automatizados:** validar que los totales Silver coincidan con Bronze antes de cargar Gold
- **Alertas de calidad:** notificar si el % de productos clasificados como olímpicos baja de un umbral (posible drift en keywords)
- **Ingesta incremental:** en lugar de WRITE_TRUNCATE completo, cargar solo las transacciones nuevas del día
- **Parametrización CLI:** pasar las fechas del evento como argumentos al script para facilitar backfills
- **Soporte multi-evento:** permitir clasificar el mismo dataset contra múltiples eventos simultáneamente (ej: Olimpiadas + Copa América en el mismo período)
- **Dashboard automático:** script que cree el Looker Studio report vía API usando las vistas ya creadas
