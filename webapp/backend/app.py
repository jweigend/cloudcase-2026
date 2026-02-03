#!/usr/bin/env python3
"""
Flask Backend für Top-Routen-Berechnung mit PySpark
Nutzt nodelokales Laden via /export Handler für maximale Performance
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, IntegerType, DoubleType, StringType
import logging
import json

app = Flask(__name__)
CORS(app)

# Logging einrichten
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Solr/ZooKeeper Konfiguration
SOLR_NODES = ["node1.cloud.local", "node2.cloud.local", "node3.cloud.local", "node4.cloud.local"]
SOLR_PORT = 8983
COLLECTION = "nyc-taxi-raw"

# Spark Session (lazy init)
_spark = None
_spark_error = None  # Letzter Fehler für Diagnose

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
        logger.info("Initialisiere Spark Session (Cluster-Modus)...")
        _spark = SparkSession.builder \
            .appName("TopRoutes-API") \
            .master("spark://node0.cloud.local:7077") \
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


def get_shard_info():
    """
    Holt Shard-zu-Node Mapping von Solr Cluster Status.
    Returns: Liste von {"shard": "shard1", "node": "node4.cloud.local", "core": "nyc-taxi-raw_shard1_replica_n6"}
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
    
    Arrayformat (alt, Kompatibilität):
    filters: ["pickup_hour:18", "pickup_dayofweek:6"]
    """
    if not filters:
        return "*:*"
    
    # Objekt-Format
    if isinstance(filters, dict):
        parts = []
        for field, values in filters.items():
            if isinstance(values, list):
                value_str = " OR ".join([str(v) for v in values])
                parts.append(f"{field}:({value_str})")
            else:
                parts.append(f"{field}:{values}")
        return " AND ".join(parts) if parts else "*:*"
    
    # Array-Format (Kompatibilität)
    parts = [f"({f})" for f in filters]
    return " AND ".join(parts)


@app.route('/api/health', methods=['GET'])
def health():
    """Health Check Endpoint mit Spark-Status"""
    spark, spark_error = get_spark()
    spark_status = "connected" if spark else "unavailable"
    
    response = {
        "status": "ok" if spark else "degraded",
        "service": "top-routes-api",
        "spark_status": spark_status,
        "spark_master": "spark://node0.cloud.local:7077"
    }
    
    if spark_error:
        response["spark_error"] = spark_error
    
    return jsonify(response)


@app.route('/api/count', methods=['POST'])
def count_trips():
    """
    Zählt Fahrten basierend auf Filtern (schnell via Solr).
    
    Request Body:
    {
        "filters": {"pickup_hour": [18, 19], "pickup_dayofweek": [6]}
    }
    """
    import requests
    
    try:
        data = request.get_json() or {}
        filters = data.get('filters', {})
        
        # Filter zu Solr fq Parametern konvertieren
        fq_parts = []
        for field, values in filters.items():
            if isinstance(values, list):
                # OR für mehrere Werte im selben Feld
                value_str = " OR ".join([str(v) for v in values])
                fq_parts.append(f"{field}:({value_str})")
            else:
                fq_parts.append(f"{field}:{values}")
        
        # Solr Query mit rows=0 (nur Count)
        solr_url = "http://node1.cloud.local:8983/solr/nyc-taxi-raw/select"
        params = {
            "q": "*:*",
            "rows": 0,
            "wt": "json"
        }
        
        if fq_parts:
            params["fq"] = fq_parts
        
        response = requests.get(solr_url, params=params, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        count = result.get("response", {}).get("numFound", 0)
        
        return jsonify({
            "count": count,
            "can_analyze": count <= 100000 and count > 0
        })
        
    except Exception as e:
        logger.exception("Fehler beim Zählen")
        return jsonify({"count": 0, "error": str(e)}), 500


@app.route('/api/top-routes', methods=['POST'])
def top_routes():
    """
    Berechnet die Top 5 lukrativsten Routen basierend auf Filtern.
    Nutzt nodelokales Laden via /export Handler für maximale Performance.
    
    Request Body:
    {
        "filters": ["pickup_hour:18", "pickup_dayofweek:6"],
        "limit": 5
    }
    
    Response:
    {
        "routes": [...],
        "total_trips": 50000,
        "spark_time_ms": 2500,
        "load_strategy": "parallel_shards"
    }
    """
    import time
    start_time = time.time()
    
    try:
        data = request.get_json() or {}
        filters = data.get('filters', [])
        limit = data.get('limit', 5)
        
        # Solr Query bauen
        solr_query = build_solr_query(filters)
        logger.info(f"Solr Query: {solr_query}")
        
        # Shard-Info holen
        shard_info = get_shard_info()
        
        # Spark Session holen (resilient)
        spark, spark_error = get_spark()
        if spark is None:
            return jsonify({
                "routes": [],
                "total_trips": 0,
                "spark_time_ms": 0,
                "error": spark_error,
                "message": "Spark-Cluster nicht verfügbar. Bitte später erneut versuchen."
            }), 503
        
        # Felder für Export
        fields = "PULocationID,DOLocationID,total_amount,trip_distance,tpep_pickup_datetime,tpep_dropoff_datetime"
        
        # Broadcast: Query und Fields an alle Worker
        query_bc = spark.sparkContext.broadcast(solr_query)
        fields_bc = spark.sparkContext.broadcast(fields)
        
        # RDD mit Shard-Infos erstellen (1 Partition pro Shard)
        shard_rdd = spark.sparkContext.parallelize(shard_info, len(shard_info))
        
        def load_shard_via_export(shard):
            """
            Läuft auf jedem Worker - lädt Shard-Daten via /export Handler.
            Der /export Handler ist optimiert für vollständige Ergebnis-Streams.
            """
            import requests
            import json
            
            node = shard["node"]
            core = shard["core"]
            query = query_bc.value
            fl = fields_bc.value
            
            # /export URL für diesen spezifischen Core (Shard)
            export_url = f"http://{node}:8983/solr/{core}/export"
            
            params = {
                "q": query,
                "fl": fl,
                "sort": "PULocationID asc, DOLocationID asc",  # /export braucht sort
                "wt": "json"
            }
            
            docs = []
            try:
                response = requests.get(export_url, params=params, timeout=60, stream=True)
                response.raise_for_status()
                
                # Streaming JSON Response parsen
                result = response.json()
                docs = result.get("response", {}).get("docs", [])
                
            except Exception as e:
                # Bei Fehler: leere Liste zurückgeben, nicht abbrechen
                print(f"Fehler beim Laden von {node}/{core}: {e}")
            
            return docs
        
        # Parallel von allen Shards laden
        docs_rdd = shard_rdd.flatMap(load_shard_via_export)
        
        # Zu DataFrame konvertieren
        # Schema definieren für bessere Performance
        schema = StructType([
            StructField("PULocationID", IntegerType(), True),
            StructField("DOLocationID", IntegerType(), True),
            StructField("total_amount", DoubleType(), True),
            StructField("trip_distance", DoubleType(), True),
            StructField("tpep_pickup_datetime", StringType(), True),
            StructField("tpep_dropoff_datetime", StringType(), True)
        ])
        
        df = spark.createDataFrame(docs_rdd, schema)
        
        # Cache für mehrfache Nutzung
        df.cache()
        total_trips = df.count()
        
        load_time = int((time.time() - start_time) * 1000)
        logger.info(f"Parallel geladen: {total_trips} Dokumente von {len(shard_info)} Shards in {load_time}ms")
        
        if total_trips == 0:
            return jsonify({
                "routes": [],
                "total_trips": 0,
                "spark_time_ms": load_time,
                "load_strategy": "parallel_shards",
                "message": "Keine Daten für diese Filter gefunden"
            })
        
        # Fahrtdauer berechnen (in Minuten)
        df_with_duration = df.withColumn(
            "duration_min",
            (F.unix_timestamp("tpep_dropoff_datetime") - F.unix_timestamp("tpep_pickup_datetime")) / 60.0
        )
        
        # Nur gültige Fahrten (Dauer > 1 Min und < 120 Min, Fare > 0)
        df_valid = df_with_duration.filter(
            (F.col("duration_min") > 1) & 
            (F.col("duration_min") < 120) &
            (F.col("total_amount") > 0)
        )
        
        # Nach Route gruppieren und aggregieren
        route_stats = df_valid.groupBy("PULocationID", "DOLocationID").agg(
            F.count("*").alias("trip_count"),
            F.avg("total_amount").alias("avg_fare"),
            F.avg("duration_min").alias("avg_duration_min"),
            F.avg("trip_distance").alias("avg_distance"),
            F.sum("total_amount").alias("total_revenue")
        )
        
        # Lukrativitäts-Score berechnen
        # Score = (trip_count * avg_fare) / avg_duration_min
        # Hohe Frequenz + hoher Preis + kurze Dauer = lukrativ
        route_stats = route_stats.withColumn(
            "score",
            (F.col("trip_count") * F.col("avg_fare")) / F.col("avg_duration_min")
        )
        
        # Fare per minute berechnen
        route_stats = route_stats.withColumn(
            "fare_per_minute",
            F.col("avg_fare") / F.col("avg_duration_min")
        )
        
        # Top N nach Score sortieren
        top_routes = route_stats.orderBy(F.desc("score")).limit(limit)
        
        # In Python Liste umwandeln
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
        
        return jsonify({
            "routes": routes_list,
            "total_trips": total_trips,
            "spark_time_ms": elapsed_ms,
            "load_strategy": "parallel_shards",
            "shards_used": len(shard_info),
            "query": solr_query
        })
        
    except Exception as e:
        logger.exception("Fehler bei Top-Routes Berechnung")
        return jsonify({
            "error": str(e),
            "routes": [],
            "total_trips": 0
        }), 500


@app.route('/api/zone-names', methods=['GET'])
def zone_names():
    """
    Gibt die NYC Taxi Zone Namen zurück (optional für bessere Anzeige)
    """
    # Die wichtigsten Manhattan Zonen
    zones = {
        132: "JFK Airport",
        138: "LaGuardia Airport",
        265: "Newark Airport",
        237: "Upper East Side South",
        236: "Upper East Side North",
        161: "Midtown Center",
        162: "Midtown East",
        163: "Midtown North",
        164: "Midtown South",
        170: "Murray Hill",
        186: "Penn Station/Madison Sq West",
        230: "Times Sq/Theatre District",
        234: "Union Sq",
        48: "Clinton East",
        79: "East Village",
        107: "Gramercy",
        113: "Greenwich Village North",
        114: "Greenwich Village South",
        125: "Hudson Sq",
        137: "Kips Bay",
        140: "Lenox Hill East",
        141: "Lenox Hill West",
        142: "Lincoln Square East",
        143: "Lincoln Square West",
        148: "Lower East Side",
        151: "Manhattan Valley",
        158: "Meatpacking/West Village West",
        166: "Morningside Heights",
        209: "Soho",
        211: "Stuy Town/PCV",
        224: "Sutton Place/Turtle Bay North",
        229: "Sutton Place/Turtle Bay South",
        231: "TriBeCa/Civic Center",
        239: "Upper West Side North",
        238: "Upper West Side South",
        246: "West Chelsea/Hudson Yards",
        249: "West Village",
        261: "World Trade Center",
        262: "Yorkville East",
        263: "Yorkville West"
    }
    return jsonify(zones)


if __name__ == '__main__':
    logger.info("Starte Top-Routes API Server...")
    # use_reloader=False wichtig für Spark! Reloader würde SparkContext zerstören
    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)
