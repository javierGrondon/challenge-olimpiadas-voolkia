-- ════════════════════════════════════════════════════════════════════
-- ANÁLISIS DE VENTAS OLÍMPICAS — Marketplace Deportivo
-- Período: mayo–agosto 2026 | Juegos Olímpicos: 14–30 jul 2026
--
-- PREREQUISITO: Correr primero scripts/load_to_bigquery.py
-- que crea las 3 capas (Bronze / Silver / Gold).
--
-- Estructura del archivo:
--   SECCIÓN 1 — Documentación de decisiones metodológicas
--   SECCIÓN 2 — Queries de análisis (para exploración en BigQuery Console)
--   SECCIÓN 3 — Vistas (CREATE OR REPLACE VIEW) para conectar a Looker Studio
--
-- Proyecto BigQuery: cellular-effect-506218-h7
-- Datasets: olimpiadas_bronze | olimpiadas_silver | olimpiadas_gold
-- ════════════════════════════════════════════════════════════════════


-- ════════════════════════════════════════════════════════════════════
-- SECCIÓN 1 — DOCUMENTACIÓN DE DECISIONES METODOLÓGICAS
-- ════════════════════════════════════════════════════════════════════
--
-- CÓMO SE IDENTIFICARON LOS PRODUCTOS OLÍMPICOS
-- (lógica aplicada en Python/Silver — aquí se documenta la decisión)
--
--   es_olimpico = TRUE si se cumple AL MENOS UNO de estos criterios:
--
--     A) vendedor_id IN (700100, 700200, 700300, 700400, 700500)
--        → licenciatarios oficiales (un ID representativo por país)
--
--     B) LOWER(titulo) contiene alguna keyword del evento:
--        'olimpia', 'ol.mpic', 'juegos ol'
--        (configurable desde .env → KEYWORDS_EVENTO)
--        Captura: "olímpico", "olimpico", "olimpiadas", "juegos olímpicos", etc.
--
--   tipo_vendedor = 'oficial' | 'particular'
--
--   periodo = 'pre_evento' | 'durante' | 'post_evento'
--     Pre-evento  : antes del 2026-07-14
--     Durante     : 2026-07-14 al 2026-07-30  (Juegos Olímpicos)
--     Post-evento : después del 2026-07-30
--
-- DECISIÓN DOCUMENTADA: se aplica a TODAS las categorías
-- (no solo camisetas/álbumes/cartas) porque el licenciatario
-- también publica en mochilas, botellas y calzado.
--
-- REUTILIZACIÓN: para otro evento, solo cambiar KEYWORDS_EVENTO,
-- VENDEDORES_OFICIALES y FECHA_*_EVENTO en .env y volver a correr el pipeline.
-- Sin tocar una línea de código Python ni SQL.


-- ════════════════════════════════════════════════════════════════════
-- SECCIÓN 2 — QUERIES DE ANÁLISIS
-- Pegar cada una en BigQuery Console para explorar resultados
-- ════════════════════════════════════════════════════════════════════


-- ────────────────────────────────────────────────────────────────────
-- QUERY 1 — KPIs generales del marketplace
-- ¿Cuánto representaron los productos olímpicos sobre el total?
-- ────────────────────────────────────────────────────────────────────

SELECT
    revenue_total_usd,
    revenue_olimpico_usd,
    pct_revenue_olimpico,
    unidades_total,
    unidades_olimpicas,
    transacciones_total,
    transacciones_olimpicas
FROM `cellular-effect-506218-h7.olimpiadas_gold.kpis_generales`;


-- ────────────────────────────────────────────────────────────────────
-- QUERY 2 — Revenue olímpico por período
-- ¿Cuánto vendimos en cada etapa del evento?
-- ────────────────────────────────────────────────────────────────────

SELECT
    periodo,
    transacciones,
    unidades,
    revenue_usd,
    ROUND(revenue_usd / unidades, 2) AS ticket_promedio_usd
FROM `cellular-effect-506218-h7.olimpiadas_gold.revenue_por_periodo`
ORDER BY
    CASE periodo
        WHEN 'pre_evento'  THEN 1
        WHEN 'durante'     THEN 2
        WHEN 'post_evento' THEN 3
    END;


-- ────────────────────────────────────────────────────────────────────
-- QUERY 3 — Revenue olímpico por país y período
-- ¿Hubo países donde el evento impactó más?
-- ────────────────────────────────────────────────────────────────────

SELECT
    pais,
    periodo,
    revenue_usd,
    unidades,
    transacciones,
    ROUND(revenue_usd / unidades, 2) AS ticket_promedio_usd
FROM `cellular-effect-506218-h7.olimpiadas_gold.revenue_por_pais`
ORDER BY
    pais,
    CASE periodo
        WHEN 'pre_evento'  THEN 1
        WHEN 'durante'     THEN 2
        WHEN 'post_evento' THEN 3
    END;


-- ────────────────────────────────────────────────────────────────────
-- QUERY 4 — Evolución semanal del revenue olímpico
-- ¿Cuánto duró el efecto olímpico semana a semana?
-- ────────────────────────────────────────────────────────────────────

SELECT
    semana,
    revenue_usd,
    unidades,
    transacciones,
    ROUND(
        (revenue_usd - LAG(revenue_usd) OVER (ORDER BY semana))
        / NULLIF(LAG(revenue_usd) OVER (ORDER BY semana), 0) * 100,
    1) AS var_pct_vs_semana_anterior
FROM `cellular-effect-506218-h7.olimpiadas_gold.revenue_semanal`
ORDER BY semana;


-- ────────────────────────────────────────────────────────────────────
-- QUERY 5 — Revenue por categoría y período
-- ¿Qué tipo de producto traccionó más durante el evento?
-- ────────────────────────────────────────────────────────────────────

SELECT
    categoria,
    periodo,
    revenue_usd,
    unidades,
    transacciones,
    ROUND(revenue_usd / unidades, 2) AS ticket_promedio_usd
FROM `cellular-effect-506218-h7.olimpiadas_gold.revenue_por_categoria`
ORDER BY
    CASE periodo
        WHEN 'pre_evento'  THEN 1
        WHEN 'durante'     THEN 2
        WHEN 'post_evento' THEN 3
    END,
    revenue_usd DESC;


-- ────────────────────────────────────────────────────────────────────
-- QUERY 6 — Vendedor oficial vs particular por período
-- ¿Valió la pena el merchandising oficial?
-- ────────────────────────────────────────────────────────────────────

SELECT
    tipo_vendedor,
    periodo,
    revenue_usd,
    unidades,
    transacciones,
    ROUND(revenue_usd / unidades, 2) AS ticket_promedio_usd
FROM `cellular-effect-506218-h7.olimpiadas_gold.vendedor_tipo_por_periodo`
ORDER BY
    tipo_vendedor,
    CASE periodo
        WHEN 'pre_evento'  THEN 1
        WHEN 'durante'     THEN 2
        WHEN 'post_evento' THEN 3
    END;


-- ────────────────────────────────────────────────────────────────────
-- QUERY BONUS — Share olímpico vs total marketplace (período evento)
-- ¿Qué peso tuvo el evento sobre TODAS las ventas del área?
-- ────────────────────────────────────────────────────────────────────

WITH total_marketplace AS (
    SELECT
        SUM(monto_usd) AS revenue_total,
        SUM(unidades)  AS unidades_total,
        COUNT(*)       AS transacciones_total
    FROM `cellular-effect-506218-h7.olimpiadas_silver.ventas`
    WHERE periodo = 'durante'
),
solo_olimpico AS (
    SELECT
        SUM(v.monto_usd) AS revenue_olimpico,
        SUM(v.unidades)  AS unidades_olimpico,
        COUNT(*)         AS transacciones_olimpico
    FROM `cellular-effect-506218-h7.olimpiadas_silver.ventas` v
    JOIN `cellular-effect-506218-h7.olimpiadas_silver.productos` p
        ON v.producto_id = p.producto_id
    WHERE p.es_olimpico = TRUE
      AND v.periodo = 'durante'
)
SELECT
    ROUND(o.revenue_olimpico, 2)                                     AS revenue_olimpico_usd,
    ROUND(t.revenue_total, 2)                                        AS revenue_total_marketplace_usd,
    ROUND(o.revenue_olimpico / t.revenue_total * 100, 1)             AS pct_revenue_olimpico,
    o.unidades_olimpico,
    t.unidades_total,
    ROUND(o.unidades_olimpico / t.unidades_total * 100, 1)           AS pct_unidades_olimpico,
    o.transacciones_olimpico,
    t.transacciones_total,
    ROUND(o.transacciones_olimpico / t.transacciones_total * 100, 1) AS pct_transacciones_olimpico
FROM solo_olimpico o, total_marketplace t;


-- ════════════════════════════════════════════════════════════════════
-- SECCIÓN 3 — VISTAS PARA LOOKER STUDIO
-- Ejecutar UNA VEZ en BigQuery Console (todas juntas o de a una).
-- Después en Looker Studio conectar cada vista: olimpiadas_gold.v_*
-- Las vistas se actualizan solas cuando el pipeline recorre los datos.
-- ════════════════════════════════════════════════════════════════════


-- Vista 1 — KPIs generales
CREATE OR REPLACE VIEW `cellular-effect-506218-h7.olimpiadas_gold.v_kpis_generales` AS
SELECT
    revenue_total_usd,
    revenue_olimpico_usd,
    pct_revenue_olimpico,
    unidades_total,
    unidades_olimpicas,
    transacciones_total,
    transacciones_olimpicas
FROM `cellular-effect-506218-h7.olimpiadas_gold.kpis_generales`;


-- Vista 2 — Revenue por período (con ticket promedio calculado)
CREATE OR REPLACE VIEW `cellular-effect-506218-h7.olimpiadas_gold.v_revenue_por_periodo` AS
SELECT
    periodo,
    transacciones,
    unidades,
    revenue_usd,
    ROUND(revenue_usd / unidades, 2)  AS ticket_promedio_usd,
    CASE periodo
        WHEN 'pre_evento'  THEN 1
        WHEN 'durante'     THEN 2
        WHEN 'post_evento' THEN 3
    END                               AS orden_periodo
FROM `cellular-effect-506218-h7.olimpiadas_gold.revenue_por_periodo`;


-- Vista 3 — Revenue por país y período
CREATE OR REPLACE VIEW `cellular-effect-506218-h7.olimpiadas_gold.v_revenue_por_pais` AS
SELECT
    pais,
    periodo,
    revenue_usd,
    unidades,
    transacciones,
    ROUND(revenue_usd / unidades, 2)  AS ticket_promedio_usd,
    CASE periodo
        WHEN 'pre_evento'  THEN 1
        WHEN 'durante'     THEN 2
        WHEN 'post_evento' THEN 3
    END                               AS orden_periodo
FROM `cellular-effect-506218-h7.olimpiadas_gold.revenue_por_pais`;


-- Vista 4 — Evolución semanal con variación semana a semana
CREATE OR REPLACE VIEW `cellular-effect-506218-h7.olimpiadas_gold.v_revenue_semanal` AS
SELECT
    semana,
    revenue_usd,
    unidades,
    transacciones,
    ROUND(
        (revenue_usd - LAG(revenue_usd) OVER (ORDER BY semana))
        / NULLIF(LAG(revenue_usd) OVER (ORDER BY semana), 0) * 100,
    1) AS var_pct_vs_semana_anterior
FROM `cellular-effect-506218-h7.olimpiadas_gold.revenue_semanal`;


-- Vista 5 — Revenue por categoría y período
CREATE OR REPLACE VIEW `cellular-effect-506218-h7.olimpiadas_gold.v_revenue_por_categoria` AS
SELECT
    categoria,
    periodo,
    revenue_usd,
    unidades,
    transacciones,
    ROUND(revenue_usd / unidades, 2)  AS ticket_promedio_usd,
    CASE periodo
        WHEN 'pre_evento'  THEN 1
        WHEN 'durante'     THEN 2
        WHEN 'post_evento' THEN 3
    END                               AS orden_periodo
FROM `cellular-effect-506218-h7.olimpiadas_gold.revenue_por_categoria`;


-- Vista 6 — Oficial vs particular por período
CREATE OR REPLACE VIEW `cellular-effect-506218-h7.olimpiadas_gold.v_vendedor_tipo_por_periodo` AS
SELECT
    tipo_vendedor,
    periodo,
    revenue_usd,
    unidades,
    transacciones,
    ROUND(revenue_usd / unidades, 2)  AS ticket_promedio_usd,
    CASE periodo
        WHEN 'pre_evento'  THEN 1
        WHEN 'durante'     THEN 2
        WHEN 'post_evento' THEN 3
    END                               AS orden_periodo
FROM `cellular-effect-506218-h7.olimpiadas_gold.vendedor_tipo_por_periodo`;


-- Vista 7 (Bonus) — Share olímpico vs total marketplace durante el evento
CREATE OR REPLACE VIEW `cellular-effect-506218-h7.olimpiadas_gold.v_share_olimpico` AS
WITH total_marketplace AS (
    SELECT
        SUM(monto_usd) AS revenue_total,
        SUM(unidades)  AS unidades_total,
        COUNT(*)       AS transacciones_total
    FROM `cellular-effect-506218-h7.olimpiadas_silver.ventas`
    WHERE periodo = 'durante'
),
solo_olimpico AS (
    SELECT
        SUM(v.monto_usd) AS revenue_olimpico,
        SUM(v.unidades)  AS unidades_olimpico,
        COUNT(*)         AS transacciones_olimpico
    FROM `cellular-effect-506218-h7.olimpiadas_silver.ventas` v
    JOIN `cellular-effect-506218-h7.olimpiadas_silver.productos` p
        ON v.producto_id = p.producto_id
    WHERE p.es_olimpico = TRUE
      AND v.periodo = 'durante'
)
SELECT
    ROUND(o.revenue_olimpico, 2)                                     AS revenue_olimpico_usd,
    ROUND(t.revenue_total, 2)                                        AS revenue_total_marketplace_usd,
    ROUND(o.revenue_olimpico / t.revenue_total * 100, 1)             AS pct_revenue_olimpico,
    o.unidades_olimpico,
    t.unidades_total,
    ROUND(o.unidades_olimpico / t.unidades_total * 100, 1)           AS pct_unidades_olimpico,
    o.transacciones_olimpico,
    t.transacciones_total,
    ROUND(o.transacciones_olimpico / t.transacciones_total * 100, 1) AS pct_transacciones_olimpico
FROM solo_olimpico o, total_marketplace t;