#!/usr/bin/env python3
"""
Top Routes Service - Spark-basierte Routen-Analyse mit In-Memory Cache

ARCHITEKTUR:
┌─────────────────────────────────────────────────────────────────────────────┐
│  WARMUP (einmalig beim ersten Request)                                      │
│                                                                             │
│  Solr Shards ──► Worker laden parallel ──► RDD mit Tupeln ──► persist()    │
│                                                                             │
│  Die Daten bleiben im verteilten RAM der Spark Worker!                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  ALLE WEITEREN QUERIES (<2s)                                                │
│                                                                             │
│  Cached RDD ──► .filter() ──► .map/reduceByKey() ──► Top N                 │
│                                                                             │
│  Alles im Cluster-RAM, KEIN createDataFrame, KEIN Collect zum Driver!       │
└─────────────────────────────────────────────────────────────────────────────┘

Datenstruktur im RDD (kompakte Tupel):
    (PULocationID, DOLocationID, fare, distance, duration_min, pickup_hour, pickup_dow)
"""

import os
import time
import logging
import requests
from pyspark.sql import SparkSession
from pyspark import StorageLevel

logger = logging.getLogger(__name__)

# ============================================================
# Konfiguration
# ============================================================
SPARK_MASTER = os.getenv("SPARK_MASTER", "spark://node0.cloud.local:7077")
SPARK_HOME = os.getenv("SPARK_HOME", "/opt/spark")
SOLR_PORT = int(os.getenv("SOLR_PORT", "8983"))

SOLR_NODES = ["node1.cloud.local", "node2.cloud.local", "node3.cloud.local", "node4.cloud.local"]
COLLECTION = "nyc-taxi-raw"

# Felder für Export
EXPORT_FIELDS = "PULocationID,DOLocationID,total_amount,trip_distance,tpep_pickup_datetime,tpep_dropoff_datetime"

# Singletons
_spark = None
_spark_error = None
_cached_trips_rdd = None
_cache_info = None


def get_spark():
    """Lazy Spark Session Initialisierung."""
    global _spark, _spark_error, _cached_trips_rdd, _cache_info
    
    if _spark is not None:
        try:
            _ = _spark.sparkContext.applicationId
            _spark_error = None
            return _spark, None
        except Exception as e:
            logger.warning(f"Spark Session war gestoppt: {e}")
            _spark = None
            _cached_trips_rdd = None
            _cache_info = None
    
    try:
        logger.info(f"Initialisiere Spark Session mit Master: {SPARK_MASTER}")
        os.environ["SPARK_HOME"] = SPARK_HOME
        
        _spark = SparkSession.builder \
            .appName("TopRoutes-API") \
            .master(SPARK_MASTER) \
            .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
            .config("spark.network.timeout", "300s") \
            .config("spark.executor.heartbeatInterval", "60s") \
            .getOrCreate()
        
        logger.info("Spark Session bereit")
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
        "error": error,
        "cache_loaded": _cached_trips_rdd is not None,
        "cache_info": _cache_info
    }


def get_shard_info():
    """Holt Shard-zu-Node Mapping von Solr Cluster Status."""
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
                        "core": replica_data["core"]
                    })
        
        return shard_info
        
    except Exception as e:
        logger.error(f"Fehler beim Holen der Shard-Info: {e}")
        return [{"shard": f"shard{i+1}", "node": node, "core": f"{COLLECTION}_shard{i+1}"} 
                for i, node in enumerate(SOLR_NODES)]


def get_or_load_trips_rdd(spark):
    """
    Lädt alle Trips einmalig von Solr und cached sie im Spark Cluster.
    
    WICHTIG: Die Daten werden als kompakte Tupel gespeichert, nicht als Dicts!
    Das spart RAM und macht Operationen schneller.
    
    Tupel-Format: (PU, DO, fare, distance, duration_min, hour, dow)
    
    Returns:
        (rdd, was_warmup, error)
    """
    global _cached_trips_rdd, _cache_info
    
    # Bereits gecached?
    if _cached_trips_rdd is not None:
        try:
            _ = _cached_trips_rdd.getNumPartitions()
            return _cached_trips_rdd, False, None
        except Exception as e:
            logger.warning(f"Cached RDD ungültig: {e}")
            _cached_trips_rdd = None
            _cache_info = None
    
    logger.info("=== WARMUP START: Lade alle Trips von Solr ===")
    load_start = time.time()
    
    try:
        shard_info = get_shard_info()
        logger.info(f"Lade von {len(shard_info)} Shards")
        
        # Broadcasts für Worker
        fields_bc = spark.sparkContext.broadcast(EXPORT_FIELDS)
        port_bc = spark.sparkContext.broadcast(SOLR_PORT)
        
        shard_rdd = spark.sparkContext.parallelize(shard_info, len(shard_info))
        
        def load_shard_to_tuples(shard):
            """
            Lädt Shard und konvertiert SOFORT zu Tupeln.
            Kein Dict-Zwischenschritt, direkt kompakte Tupel.
            """
            import requests
            from datetime import datetime
            
            node = shard["node"]
            core = shard["core"]
            port = port_bc.value
            fields = fields_bc.value
            
            export_url = f"http://{node}:{port}/solr/{core}/export"
            params = {
                "q": "*:*",
                "fl": fields,
                "sort": "PULocationID asc, DOLocationID asc",
                "wt": "json"
            }
            
            trips = []
            doc_count = 0
            valid_count = 0
            
            try:
                response = requests.get(export_url, params=params, timeout=180)
                response.raise_for_status()
                result = response.json()
                docs = result.get("response", {}).get("docs", [])
                
                for doc in docs:
                    doc_count += 1
                    
                    try:
                        # Parse timestamps
                        pickup_str = doc.get("tpep_pickup_datetime", "")
                        dropoff_str = doc.get("tpep_dropoff_datetime", "")
                        
                        pickup = datetime.strptime(pickup_str, "%Y-%m-%dT%H:%M:%SZ")
                        dropoff = datetime.strptime(dropoff_str, "%Y-%m-%dT%H:%M:%SZ")
                        duration_min = (dropoff - pickup).total_seconds() / 60.0
                        
                        # Validierung
                        if duration_min <= 1 or duration_min >= 120:
                            continue
                        
                        fare = doc.get("total_amount", 0)
                        if fare <= 0:
                            continue
                        
                        pu = doc.get("PULocationID")
                        do = doc.get("DOLocationID")
                        if pu is None or do is None:
                            continue
                        
                        distance = doc.get("trip_distance", 0)
                        
                        # Kompaktes Tupel: (PU, DO, fare, distance, duration, hour, dow)
                        trips.append((
                            int(pu),
                            int(do),
                            float(fare),
                            float(distance),
                            duration_min,
                            pickup.hour,
                            pickup.weekday()
                        ))
                        valid_count += 1
                        
                    except (ValueError, TypeError):
                        continue
                
                print(f"Worker {node}/{core}: {doc_count} docs → {valid_count} valid trips")
                
            except Exception as e:
                print(f"FEHLER {node}/{core}: {e}")
            
            return trips
        
        # Parallel laden - jeder Worker holt seinen Shard
        trips_rdd = shard_rdd.flatMap(load_shard_to_tuples)
        
        # WICHTIG: Repartition für bessere Verteilung bei Queries
        trips_rdd = trips_rdd.repartition(16)
        
        # Cache im Cluster-Speicher
        trips_rdd.persist(StorageLevel.MEMORY_AND_DISK)
        
        # Materialisiere (Trigger der Berechnung)
        total_trips = trips_rdd.count()
        
        load_time = time.time() - load_start
        
        _cached_trips_rdd = trips_rdd
        _cache_info = {
            "total_trips": total_trips,
            "load_time_s": round(load_time, 1),
            "shards": len(shard_info),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        logger.info(f"=== WARMUP COMPLETE: {total_trips:,} Trips in {load_time:.1f}s ===")
        
        return trips_rdd, True, None
        
    except Exception as e:
        logger.exception("Fehler beim Laden")
        return None, False, str(e)


def build_filter_function(filters):
    """
    Erstellt Filter-Funktion für das Trips-RDD.
    
    Tupel: (PU, DO, fare, distance, duration, hour, dow)
            0    1    2      3         4       5     6
    """
    if not filters:
        return None
    
    hour_filter = set(filters.get("pickup_hour", []))
    dow_filter = set(filters.get("pickup_dayofweek", []))
    
    # Range-Filter
    fare_min, fare_max = None, None
    if "total_amount" in filters:
        for v in filters["total_amount"]:
            if isinstance(v, str) and v.startswith("["):
                v = v.strip("[]")
                parts = v.split(" TO ")
                if len(parts) == 2:
                    try:
                        fare_min = float(parts[0]) if parts[0] != "*" else None
                        fare_max = float(parts[1]) if parts[1] != "*" else None
                    except ValueError:
                        pass
    
    def filter_trip(trip):
        pu, do, fare, distance, duration, hour, dow = trip
        
        if hour_filter and hour not in hour_filter:
            return False
        if dow_filter and dow not in dow_filter:
            return False
        if fare_min is not None and fare < fare_min:
            return False
        if fare_max is not None and fare > fare_max:
            return False
        
        return True
    
    return filter_trip


def calculate_top_routes(filters=None, limit=5):
    """
    Berechnet die Top N lukrativsten Routen.
    
    Erster Aufruf: WARMUP (~90s) - lädt alle Trips von Solr
    Danach: Blitzschnell (~2s) - nur noch RDD-Operationen im RAM
    """
    start_time = time.time()
    
    spark, spark_error = get_spark()
    if spark is None:
        return {
            "routes": [],
            "total_trips": 0,
            "spark_time_ms": 0,
            "error": spark_error,
            "message": "Spark-Cluster nicht verfügbar."
        }
    
    try:
        # Cached RDD holen oder laden
        trips_rdd, was_warmup, load_error = get_or_load_trips_rdd(spark)
        
        if trips_rdd is None:
            return {
                "routes": [],
                "total_trips": 0,
                "spark_time_ms": 0,
                "error": load_error,
                "message": "Fehler beim Laden der Daten."
            }
        
        warmup_time = time.time() - start_time if was_warmup else 0
        query_start = time.time()
        
        # Filter anwenden
        filter_fn = build_filter_function(filters)
        if filter_fn:
            filtered_rdd = trips_rdd.filter(filter_fn)
        else:
            filtered_rdd = trips_rdd
        
        # Aggregation: Route → Statistiken
        # Tupel: (PU, DO, fare, distance, duration, hour, dow)
        def to_route_stats(trip):
            pu, do, fare, distance, duration, hour, dow = trip
            return ((pu, do), (1, fare, duration, distance))
        
        def merge_stats(a, b):
            return (a[0] + b[0], a[1] + b[1], a[2] + b[2], a[3] + b[3])
        
        route_stats_rdd = filtered_rdd \
            .map(to_route_stats) \
            .reduceByKey(merge_stats)
        
        # Score berechnen
        def calc_score(item):
            (pu, do), (count, sum_fare, sum_duration, sum_distance) = item
            avg_fare = sum_fare / count
            avg_duration = sum_duration / count
            avg_distance = sum_distance / count
            fare_per_min = avg_fare / avg_duration if avg_duration > 0 else 0
            score = (count * avg_fare) / avg_duration if avg_duration > 0 else 0
            return ((pu, do), count, avg_fare, avg_duration, avg_distance, fare_per_min, sum_fare, score)
        
        scored_rdd = route_stats_rdd.map(calc_score)
        
        # Top N
        top_routes = scored_rdd.takeOrdered(limit, key=lambda x: -x[7])
        
        # Total Trips zählen
        total_filtered = filtered_rdd.count()
        
        # Formatieren
        routes_list = []
        for (pu, do), count, avg_fare, avg_dur, avg_dist, fare_per_min, total_rev, score in top_routes:
            routes_list.append({
                "PULocationID": pu,
                "DOLocationID": do,
                "trip_count": int(count),
                "avg_fare": round(avg_fare, 2),
                "avg_duration_min": round(avg_dur, 1),
                "avg_distance": round(avg_dist, 2),
                "fare_per_minute": round(fare_per_min, 2),
                "total_revenue": round(total_rev, 2),
                "score": round(score, 1)
            })
        
        query_time = time.time() - query_start
        total_time = time.time() - start_time
        
        logger.info(f"Top Routes: {total_filtered:,} Trips in {query_time*1000:.0f}ms (warmup={was_warmup})")
        
        return {
            "routes": routes_list,
            "total_trips": total_filtered,
            "spark_time_ms": int(total_time * 1000),
            "query_time_ms": int(query_time * 1000),
            "was_warmup": was_warmup,
            "warmup_time_s": round(warmup_time, 1) if was_warmup else None,
            "cache_info": _cache_info,
            "filters_applied": filters is not None
        }
        
    except Exception as e:
        logger.exception("Fehler bei Top-Routes Berechnung")
        return {
            "error": str(e),
            "routes": [],
            "total_trips": 0
        }


def invalidate_cache():
    """Invalidiert den Cache."""
    global _cached_trips_rdd, _cache_info
    
    if _cached_trips_rdd is not None:
        try:
            _cached_trips_rdd.unpersist()
        except:
            pass
    
    _cached_trips_rdd = None
    _cache_info = None
    logger.info("Cache invalidiert")
    return {"status": "ok"}
