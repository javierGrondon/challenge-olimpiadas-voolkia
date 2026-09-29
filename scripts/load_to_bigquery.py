"""
load_to_bigquery.py
═════════════════════════════════════════════════════════════════════
Pipeline Medallion Architecture — Challenge Olimpiadas 2026
Marketplace Deportivo · MercadoLibre · mayo–agosto 2026

Capas:
  • BRONZE  — Ingesta raw de los CSVs sin transformaciones
  • SILVER  — Limpieza, tipado y enriquecimiento (clasificación olímpica)
  • GOLD    — Agregaciones listas para dashboard (KPIs por período, país, categoría)

Uso:
  1. Copiá .env.example → .env y completá los valores
  2. python scripts/load_to_bigquery.py

El pipeline es idempotente: cada ejecución reemplaza las tablas existentes
(WRITE_TRUNCATE), por lo que puede correrse tantas veces como sea necesario.

Para reutilizar en otro evento, modificá en .env:
  FECHA_INICIO_EVENTO, FECHA_FIN_EVENTO, VENDEDORES_OFICIALES y KEYWORDS_EVENTO

Autor: Javier Grondon
"""

import os
import logging
from pathlib import Path
from datetime import date, datetime

import pandas as pd
from dotenv import load_dotenv
from google.cloud import bigquery
from google.api_core.exceptions import Conflict

# ─────────────────────────────────────────────
# CONFIGURACIÓN — lee desde .env
# ─────────────────────────────────────────────
load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "cellular-effect-506218-h7")
DATA_DIR   = Path(__file__).parent.parent / "data"
LOGS_DIR   = Path(__file__).parent.parent / "logs"

DATASETS = {
    "bronze": os.getenv("DATASET_BRONZE", "olimpiadas_bronze"),
    "silver": os.getenv("DATASET_SILVER", "olimpiadas_silver"),
    "gold":   os.getenv("DATASET_GOLD",   "olimpiadas_gold"),
}

# Períodos del evento — configurables para reutilización en otros eventos
FECHA_INICIO_EVENTO = date.fromisoformat(os.getenv("FECHA_INICIO_EVENTO", "2026-07-14"))
FECHA_FIN_EVENTO    = date.fromisoformat(os.getenv("FECHA_FIN_EVENTO",    "2026-07-30"))

# IDs de vendedores licenciatarios oficiales (separados por coma en .env)
_ids_raw = os.getenv("VENDEDORES_OFICIALES", "700100,700200,700300,700400,700500")
VENDEDORES_OFICIALES = {int(v.strip()) for v in _ids_raw.split(",")}

# Keywords para detectar productos del evento en títulos de publicaciones
# Se leen desde .env — separadas por coma, aceptan expresiones regulares simples
# Ejemplo Copa América: copa america,copa am.rica,mundial
_kw_raw = os.getenv("KEYWORDS_EVENTO", "olimpia,ol.mpic,juegos ol")
KEYWORDS_EVENTO = [kw.strip() for kw in _kw_raw.split(",") if kw.strip()]

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
LOGS_DIR.mkdir(exist_ok=True)
_log_file = LOGS_DIR / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(_log_file, encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)
log.info(f"Log guardado en: {_log_file}")
log.info(f"Keywords del evento: {KEYWORDS_EVENTO}")
log.info(f"Vendedores oficiales: {sorted(VENDEDORES_OFICIALES)}")
log.info(f"Período: {FECHA_INICIO_EVENTO} → {FECHA_FIN_EVENTO}")


# ═════════════════════════════════════════════
# UTILIDADES
# ═════════════════════════════════════════════

def crear_dataset(client: bigquery.Client, dataset_id: str) -> None:
    """Crea el dataset si no existe; no falla si ya existe."""
    ref = bigquery.Dataset(f"{PROJECT_ID}.{dataset_id}")
    ref.location = "US"
    try:
        client.create_dataset(ref)
        log.info(f"Dataset '{dataset_id}' creado.")
    except Conflict:
        log.info(f"Dataset '{dataset_id}' ya existe — OK.")


def cargar_dataframe(
    client: bigquery.Client,
    df: pd.DataFrame,
    dataset_id: str,
    tabla: str,
    schema: list[bigquery.SchemaField],
) -> None:
    """Sube un DataFrame a BigQuery con WRITE_TRUNCATE."""
    table_id = f"{PROJECT_ID}.{dataset_id}.{tabla}"
    config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    log.info(f"  Cargando {len(df):,} filas → {dataset_id}.{tabla} ...")
    job = client.load_table_from_dataframe(df, table_id, job_config=config)
    job.result()
    log.info(f"  ✓ {tabla} — {len(df):,} filas cargadas.")


# ═════════════════════════════════════════════
# CAPA BRONZE — Ingesta raw
# ═════════════════════════════════════════════

BRONZE_SCHEMAS = {
    "ventas": [
        bigquery.SchemaField("venta_id",    "STRING"),
        bigquery.SchemaField("pais",        "STRING"),
        bigquery.SchemaField("fecha",       "STRING"),
        bigquery.SchemaField("producto_id", "STRING"),
        bigquery.SchemaField("unidades",    "STRING"),
        bigquery.SchemaField("monto_usd",   "STRING"),
    ],
    "productos": [
        bigquery.SchemaField("producto_id", "STRING"),
        bigquery.SchemaField("pais",        "STRING"),
        bigquery.SchemaField("titulo",      "STRING"),
        bigquery.SchemaField("categoria",   "STRING"),
        bigquery.SchemaField("vendedor_id", "STRING"),
    ],
    "categorias": [
        bigquery.SchemaField("categoria",        "STRING"),
        bigquery.SchemaField("categoria_nombre", "STRING"),
    ],
}


def cargar_bronze(client: bigquery.Client) -> dict[str, pd.DataFrame]:
    """Lee los CSVs y los sube tal cual a la capa Bronze."""
    log.info("── BRONZE: ingesta raw ──────────────────────")
    dfs = {}
    for tabla in ["categorias", "productos", "ventas"]:
        csv_path = DATA_DIR / f"{tabla}.csv"
        df = pd.read_csv(csv_path, dtype=str)
        cargar_dataframe(client, df, DATASETS["bronze"], tabla, BRONZE_SCHEMAS[tabla])
        dfs[tabla] = df
    return dfs


# ═════════════════════════════════════════════
# CAPA SILVER — Limpieza y enriquecimiento
# ═════════════════════════════════════════════

def clasificar_periodo(fecha: date) -> str:
    """Asigna período del evento a una fecha."""
    if fecha < FECHA_INICIO_EVENTO:
        return "pre_evento"
    elif fecha <= FECHA_FIN_EVENTO:
        return "durante"
    else:
        return "post_evento"


def es_producto_del_evento(titulo: str, vendedor_id: int) -> bool:
    """
    Detecta si un producto es del evento por dos criterios:
      A) vendedor_id está en la lista de licenciatarios oficiales (.env)
      B) el título contiene alguna keyword del evento (.env → KEYWORDS_EVENTO)
    """
    if vendedor_id in VENDEDORES_OFICIALES:
        return True
    titulo_lower = titulo.lower()
    return any(kw in titulo_lower for kw in KEYWORDS_EVENTO)


def transformar_silver(dfs_raw: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Aplica limpieza, tipado y enriquecimiento sobre los DataFrames raw."""
    log.info("── SILVER: limpieza y enriquecimiento ───────")

    # ── Categorías ──────────────────────────────────────────────────────
    cat = dfs_raw["categorias"].copy()
    cat["categoria"]        = cat["categoria"].str.strip().str.lower()
    cat["categoria_nombre"] = cat["categoria_nombre"].str.strip()

    # ── Productos ────────────────────────────────────────────────────────
    prod = dfs_raw["productos"].copy()
    prod["producto_id"] = prod["producto_id"].astype(int)
    prod["vendedor_id"] = prod["vendedor_id"].astype(int)
    prod["pais"]        = prod["pais"].str.strip()
    prod["titulo"]      = prod["titulo"].str.strip()
    prod["categoria"]   = prod["categoria"].str.strip().str.lower()

    prod["es_olimpico"]   = prod.apply(
        lambda r: es_producto_del_evento(r["titulo"], r["vendedor_id"]), axis=1
    )
    prod["tipo_vendedor"] = prod["vendedor_id"].apply(
        lambda v: "oficial" if v in VENDEDORES_OFICIALES else "particular"
    )

    # ── Ventas ───────────────────────────────────────────────────────────
    ven = dfs_raw["ventas"].copy()
    ven["venta_id"]    = ven["venta_id"].astype(int)
    ven["producto_id"] = ven["producto_id"].astype(int)
    ven["unidades"]    = ven["unidades"].astype(int)
    ven["monto_usd"]   = ven["monto_usd"].astype(float)
    ven["pais"]        = ven["pais"].str.strip()
    ven["fecha"]       = pd.to_datetime(ven["fecha"]).dt.date

    ven["periodo"] = ven["fecha"].apply(clasificar_periodo)
    ven["semana"]  = pd.to_datetime(ven["fecha"]).dt.to_period("W").apply(
        lambda p: str(p.start_time.date())
    )

    log.info(f"  ✓ {len(ven):,} ventas tipadas y enriquecidas.")
    log.info(f"  ✓ {prod['es_olimpico'].sum()} productos del evento identificados "
             f"de {len(prod)} totales.")

    return {"categorias": cat, "productos": prod, "ventas": ven}


SILVER_SCHEMAS = {
    "ventas": [
        bigquery.SchemaField("venta_id",    "INTEGER"),
        bigquery.SchemaField("pais",        "STRING"),
        bigquery.SchemaField("fecha",       "DATE"),
        bigquery.SchemaField("producto_id", "INTEGER"),
        bigquery.SchemaField("unidades",    "INTEGER"),
        bigquery.SchemaField("monto_usd",   "FLOAT64"),
        bigquery.SchemaField("periodo",     "STRING"),
        bigquery.SchemaField("semana",      "STRING"),
    ],
    "productos": [
        bigquery.SchemaField("producto_id",   "INTEGER"),
        bigquery.SchemaField("pais",          "STRING"),
        bigquery.SchemaField("titulo",        "STRING"),
        bigquery.SchemaField("categoria",     "STRING"),
        bigquery.SchemaField("vendedor_id",   "INTEGER"),
        bigquery.SchemaField("es_olimpico",   "BOOLEAN"),
        bigquery.SchemaField("tipo_vendedor", "STRING"),
    ],
    "categorias": [
        bigquery.SchemaField("categoria",        "STRING"),
        bigquery.SchemaField("categoria_nombre", "STRING"),
    ],
}


def cargar_silver(client: bigquery.Client, dfs_silver: dict[str, pd.DataFrame]) -> None:
    """Sube las tablas Silver a BigQuery."""
    for tabla in ["categorias", "productos", "ventas"]:
        cargar_dataframe(
            client, dfs_silver[tabla],
            DATASETS["silver"], tabla, SILVER_SCHEMAS[tabla]
        )


# ═════════════════════════════════════════════
# CAPA GOLD — Agregaciones para dashboard
# ═════════════════════════════════════════════

def construir_gold(dfs_silver: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Genera las tablas agregadas Gold a partir de los datos Silver."""
    log.info("── GOLD: agregaciones para dashboard ────────")

    ven  = dfs_silver["ventas"]
    prod = dfs_silver["productos"]

    df = ven.merge(prod[["producto_id", "categoria", "es_olimpico", "tipo_vendedor"]],
                   on="producto_id", how="left")
    df_olimpico = df[df["es_olimpico"] == True]

    # gold.kpis_generales
    kpis = pd.DataFrame([{
        "revenue_total_usd":          round(df["monto_usd"].sum(), 2),
        "revenue_olimpico_usd":       round(df_olimpico["monto_usd"].sum(), 2),
        "unidades_total":             int(df["unidades"].sum()),
        "unidades_olimpicas":         int(df_olimpico["unidades"].sum()),
        "transacciones_total":        len(df),
        "transacciones_olimpicas":    len(df_olimpico),
        "pct_revenue_olimpico":       round(df_olimpico["monto_usd"].sum() / df["monto_usd"].sum() * 100, 2),
    }])

    # gold.revenue_por_periodo
    por_periodo = (
        df_olimpico.groupby("periodo")
        .agg(revenue_usd=("monto_usd","sum"), unidades=("unidades","sum"), transacciones=("venta_id","count"))
        .reset_index().round({"revenue_usd": 2})
    )

    # gold.revenue_por_pais
    por_pais = (
        df_olimpico.groupby(["pais", "periodo"])
        .agg(revenue_usd=("monto_usd","sum"), unidades=("unidades","sum"), transacciones=("venta_id","count"))
        .reset_index().round({"revenue_usd": 2})
    )

    # gold.revenue_por_categoria
    por_categoria = (
        df_olimpico.groupby(["categoria", "periodo"])
        .agg(revenue_usd=("monto_usd","sum"), unidades=("unidades","sum"), transacciones=("venta_id","count"))
        .reset_index().round({"revenue_usd": 2})
    )

    # gold.revenue_semanal
    semanal = (
        df_olimpico.groupby("semana")
        .agg(revenue_usd=("monto_usd","sum"), unidades=("unidades","sum"), transacciones=("venta_id","count"))
        .reset_index().sort_values("semana").round({"revenue_usd": 2})
    )

    # gold.vendedor_tipo_por_periodo
    por_tipo_vendedor = (
        df_olimpico.groupby(["tipo_vendedor", "periodo"])
        .agg(revenue_usd=("monto_usd","sum"), unidades=("unidades","sum"), transacciones=("venta_id","count"))
        .reset_index().round({"revenue_usd": 2})
    )

    log.info(f"  ✓ kpis_generales — 1 fila")
    log.info(f"  ✓ revenue_por_periodo — {len(por_periodo)} filas")
    log.info(f"  ✓ revenue_por_pais — {len(por_pais)} filas")
    log.info(f"  ✓ revenue_por_categoria — {len(por_categoria)} filas")
    log.info(f"  ✓ revenue_semanal — {len(semanal)} filas")
    log.info(f"  ✓ vendedor_tipo_por_periodo — {len(por_tipo_vendedor)} filas")

    return {
        "kpis_generales":            kpis,
        "revenue_por_periodo":       por_periodo,
        "revenue_por_pais":          por_pais,
        "revenue_por_categoria":     por_categoria,
        "revenue_semanal":           semanal,
        "vendedor_tipo_por_periodo": por_tipo_vendedor,
    }


GOLD_SCHEMAS = {
    "kpis_generales": [
        bigquery.SchemaField("revenue_total_usd",       "FLOAT64"),
        bigquery.SchemaField("revenue_olimpico_usd",    "FLOAT64"),
        bigquery.SchemaField("unidades_total",          "INTEGER"),
        bigquery.SchemaField("unidades_olimpicas",      "INTEGER"),
        bigquery.SchemaField("transacciones_total",     "INTEGER"),
        bigquery.SchemaField("transacciones_olimpicas", "INTEGER"),
        bigquery.SchemaField("pct_revenue_olimpico",    "FLOAT64"),
    ],
    "revenue_por_periodo": [
        bigquery.SchemaField("periodo",       "STRING"),
        bigquery.SchemaField("revenue_usd",   "FLOAT64"),
        bigquery.SchemaField("unidades",      "INTEGER"),
        bigquery.SchemaField("transacciones", "INTEGER"),
    ],
    "revenue_por_pais": [
        bigquery.SchemaField("pais",          "STRING"),
        bigquery.SchemaField("periodo",       "STRING"),
        bigquery.SchemaField("revenue_usd",   "FLOAT64"),
        bigquery.SchemaField("unidades",      "INTEGER"),
        bigquery.SchemaField("transacciones", "INTEGER"),
    ],
    "revenue_por_categoria": [
        bigquery.SchemaField("categoria",     "STRING"),
        bigquery.SchemaField("periodo",       "STRING"),
        bigquery.SchemaField("revenue_usd",   "FLOAT64"),
        bigquery.SchemaField("unidades",      "INTEGER"),
        bigquery.SchemaField("transacciones", "INTEGER"),
    ],
    "revenue_semanal": [
        bigquery.SchemaField("semana",        "STRING"),
        bigquery.SchemaField("revenue_usd",   "FLOAT64"),
        bigquery.SchemaField("unidades",      "INTEGER"),
        bigquery.SchemaField("transacciones", "INTEGER"),
    ],
    "vendedor_tipo_por_periodo": [
        bigquery.SchemaField("tipo_vendedor", "STRING"),
        bigquery.SchemaField("periodo",       "STRING"),
        bigquery.SchemaField("revenue_usd",   "FLOAT64"),
        bigquery.SchemaField("unidades",      "INTEGER"),
        bigquery.SchemaField("transacciones", "INTEGER"),
    ],
}


def cargar_gold(client: bigquery.Client, dfs_gold: dict[str, pd.DataFrame]) -> None:
    """Sube todas las tablas Gold a BigQuery."""
    for tabla, df in dfs_gold.items():
        cargar_dataframe(client, df, DATASETS["gold"], tabla, GOLD_SCHEMAS[tabla])


# ═════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════

def main() -> None:
    print()
    print("═" * 55)
    print("  Pipeline Medallion — Challenge Olimpiadas 2026")
    print(f"  Proyecto: {PROJECT_ID}")
    print("═" * 55)
    print()

    client = bigquery.Client(project=PROJECT_ID)

    log.info("Creando datasets Bronze / Silver / Gold ...")
    for ds in DATASETS.values():
        crear_dataset(client, ds)
    print()

    dfs_raw    = cargar_bronze(client)
    print()
    dfs_silver = transformar_silver(dfs_raw)
    cargar_silver(client, dfs_silver)
    print()
    dfs_gold   = construir_gold(dfs_silver)
    cargar_gold(client, dfs_gold)
    print()

    log.info("✓ Pipeline completo.")
    print()
    print("  Tablas disponibles en BigQuery:")
    print(f"  • {DATASETS['bronze']}  → ventas, productos, categorias (raw)")
    print(f"  • {DATASETS['silver']}  → ventas, productos, categorias (limpias + enriquecidas)")
    print(f"  • {DATASETS['gold']}    → kpis_generales, revenue_por_periodo,")
    print( "                             revenue_por_pais, revenue_por_categoria,")
    print( "                             revenue_semanal, vendedor_tipo_por_periodo")
    print()


if __name__ == "__main__":
    main()