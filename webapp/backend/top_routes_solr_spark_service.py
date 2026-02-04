#!/usr/bin/env python3
"""
Top Routes Service - Spark-basierte Routen-Analyse

Dieser Service berechnet die lukrativsten Taxi-Routen durch:
1. Paralleles Laden von Daten aus allen Solr Shards via /export Handler
2. Verteilte Aggregation im Spark Cluster
3. Lukrativitäts-Scoring basierend auf Frequenz, Preis und Dauer

Architektur:
┌─────────────────────────────────────────────────────────────────────────┐
│                         SPARK CLUSTER                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      DRIVER (node0)                              │   │
│  │  - Empfängt API Request mit Filtern                             │   │
│  │  - Holt Shard-Info vom Solr Cluster                             │   │
│  │  - Verteilt Shard-Infos an Worker                               │   │
│  │  - Sammelt und aggregiert Ergebnisse                            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                 │                                       │
│         ┌───────────────────────┼───────────────────────┐              │
│         ▼                       ▼                       ▼              │
│  ┌─────────────┐         ┌─────────────┐         ┌─────────────┐       │
│  │ WORKER 1    │         │ WORKER 2    │         │ WORKER 3    │       │
│  │ (node1)     │         │ (node2)     │         │ (node3)     │       │
│  │             │         │             │         │             │       │
│  │ Lädt Shard1 │         │ Lädt Shard2 │         │ Lädt Shard3 │       │
│  │ von lokalem │         │ von lokalem │         │ von lokalem │       │
│  │ Solr Node   │         │ Solr Node   │         │ Solr Node   │       │
│  └──────┬──────┘         └──────┬──────┘         └──────┬──────┘       │
│         │                       │                       │              │
└─────────┼───────────────────────┼───────────────────────┼──────────────┘
          │                       │                       │
          ▼                       ▼                       ▼
   ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
   │ SOLR NODE 1 │         │ SOLR NODE 2 │         │ SOLR NODE 3 │
   │ (node1)     │         │ (node2)     │         │ (node3)     │
   │             │         │             │         │             │
   │ Shard 1     │         │ Shard 2     │         │ Shard 3     │
   │ /export     │         │ /export     │         │ /export     │
   └─────────────┘         └─────────────┘         └─────────────┘

Konfiguration via Umgebungsvariablen:
  SPARK_MASTER  - Spark Master URL (default: spark://node0.cloud.local:7077)
  SPARK_HOME    - Spark Installation (default: /opt/spark)
  SOLR_PORT     - Solr Port (default: 8983)
"""

import os
import time
import logging
import requests
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, IntegerType, DoubleType, StringType

logger = logging.getLogger(__name__)

# ============================================================
# Konfiguration
# ============================================================
SPARK_MASTER = os.getenv("SPARK_MASTER", "spark://node0.cloud.local:7077")
SPARK_HOME = os.getenv("SPARK_HOME", "/opt/spark")
SOLR_PORT = int(os.getenv("SOLR_PORT", "8983"))

# Solr Cluster Nodes (Co-Located mit Spark Workers)
SOLR_NODES = ["node1.cloud.local", "node2.cloud.local", "node3.cloud.local", "node4.cloud.local"]
COLLECTION = "nyc-taxi-raw"

# Spark Session (lazy init, singleton)
_spark = None
_spark_error = None


# ============================================================
# Spark Session Management
# ============================================================

def get_spark():
    """
    Lazy Spark Session Initialisierung für Cluster-Modus.
    
    Resilient: Versucht bei jedem Aufruf eine Verbindung herzustellen.
    Gibt (spark, None) bei Erfolg zurück, (None, error_msg) bei Fehler.
    """
    global _spark, _spark_error
    
    # Prüfen ob bestehende Session noch aktiv ist
    if _spark is not None:
        try:
            _ = _spark.sparkContext.applicationId
            _spark_error = None
            return _spark, None
        except Exception as e:
            logger.warning(f"Spark Session war gestoppt: {e}")
            _spark = None
    
    # Neue Session erstellen
    try:
        logger.info(f"Initialisiere Spark Session mit Master: {SPARK_MASTER}")
        os.environ["SPARK_HOME"] = SPARK_HOME
        
        _spark = SparkSession.builder \
            .appName("TopRoutes-API") \
            .master(SPARK_MASTER) \
            .config("spark.executor.memory", "16g") \
            .config("spark.executor.cores", "4") \
            .config("spark.cores.max", "16") \
            .config("spark.executor.instances", "4") \
            .config("spark.driver.memory", "4g") \
            .config("spark.sql.shuffle.partitions", "32") \
            .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
            .config("spark.network.timeout", "120s") \
            .config("spark.executor.heartbeatInterval", "60s") \
            .getOrCreate()
        
        logger.info("Spark Session bereit (Cluster-Modus)")
        _spark_error = None
        return _spark, None
    except Exception as e:
        error_msg = f"Spark-Cluster nicht erreichbar: {str(e)}"
        logger.error(error_msg)
        _spark = None
        _spark_error = error_msg
        return None, error_msg


def get_spark_status():
    """Gibt den aktuellen Spark-Status zurück."""
    spark, error = get_spark()
    return {
        "connected": spark is not None,
        "master": SPARK_MASTER,
        "error": error
    }


# ============================================================
# Solr Cluster Integration
# ============================================================

def get_shard_info():
    """
    Holt Shard-zu-Node Mapping von Solr Cluster Status.
    
    Returns: Liste von Shard-Infos:
        [
            {"shard": "shard1", "node": "node1.cloud.local", "core": "nyc-taxi-raw_shard1_replica_n6"},
            {"shard": "shard2", "node": "node2.cloud.local", "core": "nyc-taxi-raw_shard2_replica_n4"},
            ...
        ]
    
    Diese Info wird genutzt, um jeden Spark Worker seinen lokalen Shard laden zu lassen.
    """
    url = f"http://{SOLR_NODES[0]}:{SOLR_PORT}/solr/admin/collections"
    params = {"action": "CLUSTERSTATUS", "collection": COLLECTION, "wt": "json"}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        shards = data["cluster"]["collections"][COLLECTION]["shards"]
        shard_info = []
        
        for shard_name, shard_data in shards.items():
            for replica_name, replica_data in shard_data["replicas"].items():
                if replica_data.get("leader") == "true":
                    node_name = replica_data["node_name"].replace(":8983_solr", "")
                    shard_info.append({
                        "shard": shard_name,
                        "node": node_name,
                        "core": replica_data["core"],
                        "base_url": replica_data["base_url"]
                    })
        
        logger.info(f"Shard-Info: {shard_info}")
        return shard_info
        
    except Exception as e:
        logger.error(f"Fehler beim Holen der Shard-Info: {e}")
        # Fallback: Alle Nodes gleichmäßig
        return [{"shard": f"shard{i+1}", "node": node, "core": f"{COLLECTION}_shard{i+1}"} 
                for i, node in enumerate(SOLR_NODES)]


def build_solr_query(filters):
    """
    Baut Solr Query aus Filter-Objekt oder -Array.
    
    Objektformat (neu):
        filters: {"pickup_hour": [18, 19], "pickup_dayofweek": [6]}
        filters: {"total_amount": ["[10 TO 20]"]}  # Range-Filter
    
    Arrayformat (alt, Kompatibilität):
        filters: ["pickup_hour:18", "pickup_dayofweek:6"]
    
    Returns:
        Solr Query String, z.B. "pickup_hour:(18 OR 19) AND pickup_dayofweek:6"
    """
    if not filters:
        return "*:*"
    
    # Objekt-Format
    if isinstance(filters, dict):
        parts = []
        for field, values in filters.items():
            if isinstance(values, list):
                # Range-Filter erkennen (beginnt mit '[')
                range_values = [v for v in values if isinstance(v, str) and v.startswith('[')]
                normal_values = [v for v in values if not (isinstance(v, str) and v.startswith('['))]
                
                # Range-Filter direkt anhängen
                for rv in range_values:
                    parts.append(f"{field}:{rv}")
                
                # Normale Werte mit OR gruppieren
                if normal_values:
                    value_str = " OR ".join([str(v) for v in normal_values])
                    parts.append(f"{field}:({value_str})")
            else:
                parts.append(f"{field}:{values}")
        return " AND ".join(parts) if parts else "*:*"
    
    # Array-Format (Kompatibilität)
    parts = [f"({f})" for f in filters]
    return " AND ".join(parts)


# ============================================================
# Top Routes Berechnung (Spark Job)
# ============================================================

def calculate_top_routes(filters=None, limit=5):
    """
    Berechnet die Top N lukrativsten Routen basierend auf Filtern.
    
    Diese Funktion orchestriert einen verteilten Spark-Job:
    1. Shard-Infos vom Solr Cluster holen
    2. Broadcast der Query an alle Worker
    3. Jeder Worker lädt seinen lokalen Shard via /export
    4. Verteilte Aggregation nach Route
    5. Top N nach Lukrativitäts-Score
    
    Args:
        filters: Filter-Objekt oder -Array (optional)
        limit: Anzahl der Top-Routen (default: 5)
    
    Returns:
        dict mit routes, total_trips, spark_time_ms, etc.
    """
    start_time = time.time()
    
    # Spark Session holen (resilient)
    spark, spark_error = get_spark()
    if spark is None:
        return {
            "routes": [],
            "total_trips": 0,
            "spark_time_ms": 0,
            "error": spark_error,
            "message": "Spark-Cluster nicht verfügbar. Bitte später erneut versuchen."
        }
    
    try:
        # Solr Query bauen
        solr_query = build_solr_query(filters)
        logger.info(f"Solr Query: {solr_query}")
        
        # Shard-Info holen
        shard_info = get_shard_info()
        
        # Felder für Export (nur was wir brauchen)
        fields = "PULocationID,DOLocationID,total_amount,trip_distance,tpep_pickup_datetime,tpep_dropoff_datetime"
        
        # ============================================================
        # BROADCAST: Query und Fields an alle Worker senden
        # ============================================================
        # Diese Variablen werden einmal an alle Worker gesendet,
        # anstatt bei jeder Task-Ausführung serialisiert zu werden.
        query_bc = spark.sparkContext.broadcast(solr_query)
        fields_bc = spark.sparkContext.broadcast(fields)
        solr_port_bc = spark.sparkContext.broadcast(SOLR_PORT)
        
        # ============================================================
        # RDD mit Shard-Infos (1 Partition pro Shard)
        # ============================================================
        # Jeder Eintrag entspricht einem Shard, der auf einem Worker
        # geladen wird. Die Partitionierung stellt sicher, dass
        # jeder Shard auf genau einem Worker landet.
        shard_rdd = spark.sparkContext.parallelize(shard_info, len(shard_info))
        
        # ============================================================
        # WORKER FUNKTION: Lädt Daten von lokalem Solr Shard
        # ============================================================
        def load_shard_via_export(shard):
            """
            Diese Funktion läuft auf jedem Spark Worker!
            
            Sie lädt Shard-Daten via Solr /export Handler.
            Der /export Handler ist optimiert für vollständige Ergebnis-Streams
            ohne Cursor/Pagination Overhead.
            
            Args:
                shard: Dict mit node, core, etc.
            
            Returns:
                Liste von Dokumenten als Dicts
            """
            import requests  # Import hier, da auf Worker ausgeführt
            
            node = shard["node"]
            core = shard["core"]
            query = query_bc.value    # Broadcast-Variable abrufen
            fl = fields_bc.value      # Broadcast-Variable abrufen
            port = solr_port_bc.value # Broadcast-Variable abrufen
            
            # /export URL für diesen spezifischen Core (Shard)
            # Wichtig: Wir sprechen den Core direkt an, nicht die Collection!
            export_url = f"http://{node}:{port}/solr/{core}/export"
            
            params = {
                "q": query,
                "fl": fl,
                "sort": "PULocationID asc, DOLocationID asc",  # /export braucht sort
                "wt": "json"
            }
            
            docs = []
            try:
                response = requests.get(export_url, params=params, timeout=120, stream=True)
                response.raise_for_status()
                
                result = response.json()
                docs = result.get("response", {}).get("docs", [])
                
            except Exception as e:
                # Fehler loggen aber nicht abbrechen - andere Shards können erfolgreich sein
                print(f"Fehler beim Laden von {node}/{core}: {e}")
            
            return docs
        
        # ============================================================
        # PARALLEL LADEN: Jeder Worker lädt seinen Shard
        # ============================================================
        docs_rdd = shard_rdd.flatMap(load_shard_via_export)
        
        # ============================================================
        # ZU DATAFRAME KONVERTIEREN
        # ============================================================
        # Schema explizit definieren für bessere Performance
        schema = StructType([
            StructField("PULocationID", IntegerType(), True),
            StructField("DOLocationID", IntegerType(), True),
            StructField("total_amount", DoubleType(), True),
            StructField("trip_distance", DoubleType(), True),
            StructField("tpep_pickup_datetime", StringType(), True),
            StructField("tpep_dropoff_datetime", StringType(), True)
        ])
        
        df = spark.createDataFrame(docs_rdd, schema)
        
        # Cache für mehrfache Nutzung (count + Aggregation)
        df.cache()
        total_trips = df.count()
        
        load_time = int((time.time() - start_time) * 1000)
        logger.info(f"Parallel geladen: {total_trips} Dokumente von {len(shard_info)} Shards in {load_time}ms")
        
        if total_trips == 0:
            return {
                "routes": [],
                "total_trips": 0,
                "spark_time_ms": load_time,
                "load_strategy": "parallel_shards",
                "message": "Keine Daten für diese Filter gefunden"
            }
        
        # ============================================================
        # FAHRTDAUER BERECHNEN
        # ============================================================
        # Solr liefert ISO 8601 Format: 2023-01-18T15:21:19Z
        df_with_duration = df.withColumn(
            "duration_min",
            (F.unix_timestamp("tpep_dropoff_datetime", "yyyy-MM-dd'T'HH:mm:ss'Z'") - 
             F.unix_timestamp("tpep_pickup_datetime", "yyyy-MM-dd'T'HH:mm:ss'Z'")) / 60.0
        )
        
        # ============================================================
        # DATENQUALITÄT: Nur gültige Fahrten
        # ============================================================
        df_valid = df_with_duration.filter(
            (F.col("duration_min").isNotNull()) &
            (F.col("duration_min") > 1) &       # Mindestens 1 Minute
            (F.col("duration_min") < 120) &     # Maximal 2 Stunden
            (F.col("total_amount") > 0)         # Positive Fahrpreise
        )
        
        # ============================================================
        # AGGREGATION NACH ROUTE
        # ============================================================
        route_stats = df_valid.groupBy("PULocationID", "DOLocationID").agg(
            F.count("*").alias("trip_count"),
            F.avg("total_amount").alias("avg_fare"),
            F.avg("duration_min").alias("avg_duration_min"),
            F.avg("trip_distance").alias("avg_distance"),
            F.sum("total_amount").alias("total_revenue")
        )
        
        # ============================================================
        # LUKRATIVITÄTS-SCORE
        # ============================================================
        # Score = (trip_count * avg_fare) / avg_duration_min
        # Hohe Frequenz + hoher Preis + kurze Dauer = lukrativ
        route_stats = route_stats.withColumn(
            "score",
            (F.col("trip_count") * F.col("avg_fare")) / F.col("avg_duration_min")
        )
        
        # Fare per minute für zusätzliche Insights
        route_stats = route_stats.withColumn(
            "fare_per_minute",
            F.col("avg_fare") / F.col("avg_duration_min")
        )
        
        # ============================================================
        # TOP N SORTIEREN UND SAMMELN
        # ============================================================
        top_routes = route_stats.orderBy(F.desc("score")).limit(limit)
        
        # Ergebnisse zum Driver holen und in Python-Liste umwandeln
        routes_list = []
        for row in top_routes.collect():
            routes_list.append({
                "PULocationID": int(row["PULocationID"]),
                "DOLocationID": int(row["DOLocationID"]),
                "trip_count": int(row["trip_count"]),
                "avg_fare": round(float(row["avg_fare"]), 2),
                "avg_duration_min": round(float(row["avg_duration_min"]), 1),
                "avg_distance": round(float(row["avg_distance"]), 2),
                "fare_per_minute": round(float(row["fare_per_minute"]), 2),
                "total_revenue": round(float(row["total_revenue"]), 2),
                "score": round(float(row["score"]), 1)
            })
        
        # Cache freigeben
        df.unpersist()
        
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Top Routes berechnet in {elapsed_ms}ms für {total_trips} Fahrten")
        
        return {
            "routes": routes_list,
            "total_trips": total_trips,
            "spark_time_ms": elapsed_ms,
            "load_strategy": "parallel_shards",
            "shards_used": len(shard_info),
            "query": solr_query
        }
        
    except Exception as e:
        logger.exception("Fehler bei Top-Routes Berechnung")
        return {
            "error": str(e),
            "routes": [],
            "total_trips": 0
        }
