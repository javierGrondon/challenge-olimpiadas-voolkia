# Challenge Reporting & Automation — Olimpiadas 2026

**Autor:** Javier Grondon  
**Fecha:** Septiembre 2026  
**Posición:** Analista de Reporting & Automation Sr — Aliantec

---

## Contexto

Análisis del impacto de los Juegos Olímpicos 2026 (14–30 de julio) sobre las ventas del área de artículos deportivos de un marketplace online. El objetivo es responder el pedido del equipo comercial y generar insumos para decisiones sobre futuros eventos similares.

---

## Entregables

| Archivo / Link | Descripción |
|---|---|
| [`queries.sql`](./queries.sql) | Todas las consultas SQL usadas (BigQuery) |
| [`docs/presentacion.pptx`](./docs/) | Presentación ejecutiva — 8 slides |
| [Dashboard Looker Studio](https://datastudio.google.com/s/jWuonG5OqQ8) | Dashboard interactivo con apertura por país, categoría y vendedor |
| `data/` | CSVs originales del challenge (`ventas.csv`, `productos.csv`, `categorias.csv`) |

---

## Arquitectura — Medallion en BigQuery

```
data/
├── ventas.csv          ──►  bronze_ventas
├── productos.csv       ──►  bronze_productos
└── categorias.csv      ──►  bronze_categorias
                                   │
                                   ▼
                           silver_ventas
                    (clasificación olímpica + período)
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼               ▼
           gold_kpis_generales  gold_por_periodo_pais
           gold_revenue_semanal gold_por_periodo_categoria
           gold_efecto_post_evento gold_por_periodo_vendedor
                                   │
                                   ▼
                            Looker Studio
```

**Bronze:** carga directa de los CSV sin transformación.  
**Silver:** tipado de fechas, enriquecimiento con categoría y vendedor, clasificación olímpica y asignación de período (pre / durante / post).  
**Gold:** tablas pre-agregadas por las dimensiones que consume el dashboard.

---

## Criterio de clasificación olímpica

No existe un campo que indique si un producto es del evento. La detección se hizo en dos capas:

1. **Vendedor oficial (licenciataria):** IDs `700100`, `700200`, `700300`, `700400`, `700500`. Todo lo que publican es olímpico por definición.
2. **Vendedores particulares:** búsqueda por expresión regular en el título de la publicación — `olimpia|juegos ol[ií]mpic|ol[ií]mpic` — filtrada a las categorías relevantes: Camisetas, Álbumes de Figuritas y Cartas (tal como indica el pedido).

Esta lógica vive en `silver_ventas` y es el único punto donde se toma la decisión. Cualquier ajuste (agregar palabras clave, sumar categorías) se hace ahí y se propaga a todo el Gold.

---

## Hallazgos principales

| Pregunta | Respuesta |
|---|---|
| ¿Cuánto creció el revenue? | **$415K adicionales** — 18,75% del revenue total anual. Pico ×18 vs semanas normales |
| ¿Qué países y categorías lideraron? | **Brasil** #1 estructural. **Camisetas** dominó los 3 períodos. **Libros** escaló al 2.° durante el evento |
| ¿Cuánto duró el efecto post? | **2 semanas** con revenue superior al pre-evento antes de normalizarse |
| ¿Los oficiales aprovecharon más? | Ambos crecieron. Particulares en volumen (×2,3), Oficiales en ticket ($19,94 vs $19,39) |

---

## Sobre escala — si el mes que viene otra área pide lo mismo

El pipeline está pensado para ser reutilizable con mínima configuración:

**Lo que cambiaría entre eventos son 4 variables:**
```
FECHA_INICIO_EVENTO = '2026-07-14'
FECHA_FIN_EVENTO    = '2026-07-30'
VENDEDORES_OFICIALES = [700100, 700200, 700300, 700400, 700500]
KEYWORDS_TITULO      = 'olimpia|juegos ol[ií]mpic|ol[ií]mpic'
```

**Lo que no cambiaría:** la lógica de Silver, las tablas Gold, el dashboard (que solo necesita reconectarse a las nuevas tablas).

**Mejoras concretas para producción:**
- Parametrizar esas 4 variables en un archivo `.env` o en una tabla de configuración en BigQuery, para que cualquier analista pueda lanzar el análisis sin tocar SQL.
- Reemplazar la carga manual de CSV por un ingesta automática (Cloud Storage + Cloud Functions o Dataform scheduled queries).
- Versionar los runs: añadir una columna `evento_id` en Silver para poder comparar múltiples eventos en el mismo dataset sin reescribir.
- Automatizar la actualización del dashboard con un scheduled refresh para que el equipo comercial lo vea sin intervención manual.

Con ese diseño, el tiempo de onboarding de un nuevo evento pasa de días a horas.

---

## Decisiones tomadas

- **Período pre-evento:** definido como todo lo anterior al 14/07. El challenge no especifica un límite; tomé desde el inicio del dataset (1/5/2026) para tener suficiente baseline.
- **Período post-evento:** todo lo posterior al 30/07 hasta el 31/08. No recorté a "2 semanas post" para que el análisis muestre naturalmente cuándo se normalizó.
- **Ticket promedio:** calculado como `monto_usd / unidades` por venta individual, no como ratio de totales, para evitar distorsiones por ventas de alto volumen.
- **Categorías de particulares:** seguí exactamente las mencionadas en el pedido (camisetas, álbumes, cartas). No expandí a otras categorías por criterio propio.

---

## Uso de IA

Utilicé **Claude (Anthropic)** como asistente a lo largo del proyecto:

- **Diseño del pipeline:** consulté opciones de arquitectura para BigQuery y elegí Medallion por su claridad y capacidad de reutilización.
- **Debugging SQL:** Claude me ayudó a identificar que `pct_revenue_olimpico` se almacenaba como `18.75` (no como ratio 0–1), y que Looker Studio aplicaba SUM en lugar de MAX en tablas de una fila — lo que generaba el porcentaje incorrecto.
- **Presentación:** generé las 8 slides del PPTX ejecutivo con asistencia de Claude, usando `pptxgenjs`.
- **Redacción:** este README fue redactado con apoyo de Claude a partir de mis notas y decisiones.

Todo el código SQL, la lógica de clasificación y los criterios analíticos son propios; Claude actuó como par de revisión y acelerador de productividad.

---

## Cómo reproducir el pipeline

```bash
# 1. Clonar el repo
git clone https://github.com/javierGrondon/challenge-olimpiadas-voolkia
cd challenge-olimpiadas-voolkia

# 2. Configurar credenciales de BigQuery
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"

# 3. Cargar los CSV a las tablas Bronze
python scripts/load_bronze.py

# 4. Ejecutar las queries en orden
#    (desde la consola de BigQuery o con bq CLI)
bq query --use_legacy_sql=false < queries.sql
```

> **Nota:** el archivo de service account no está en el repo por seguridad. Solicitarlo al autor.
