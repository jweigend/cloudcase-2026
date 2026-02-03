#!/usr/bin/env python3
"""
Flask Backend für Top-Routen-Berechnung mit PySpark
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType
import logging

app = Flask(__name__)
CORS(app)

# Logging einrichten
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Spark Session (lazy init)
_spark = None

def get_spark():
    """Lazy Spark Session Initialisierung mit Wiederherstellung"""
    global _spark
    
    # Prüfen ob Session existiert und noch aktiv ist
    if _spark is not None:
        try:
            # Test ob SparkContext noch läuft
            _ = _spark.sparkContext.applicationId
            return _spark
        except Exception:
            logger.warning("Spark Session war gestoppt, erstelle neue...")
            _spark = None
    
    logger.info("Initialisiere Spark Session...")
    _spark = SparkSession.builder \
        .appName("TopRoutes-API") \
        .master("local[*]") \
        .config("spark.driver.memory", "4g") \
        .getOrCreate()
    logger.info("Spark Session bereit")
    return _spark


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
    """Health Check Endpoint"""
    return jsonify({"status": "ok", "service": "top-routes-api"})


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
    
    Request Body:
    {
        "filters": ["pickup_hour:18", "pickup_dayofweek:6"],
        "limit": 5
    }
    
    Response:
    {
        "routes": [
            {
                "pickup_zone": 132,
                "dropoff_zone": 265,
                "trip_count": 1234,
                "avg_fare": 45.50,
                "avg_duration_min": 25.3,
                "score": 178.5
            }
        ],
        "total_trips": 50000,
        "spark_time_ms": 2500
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
        
        # Spark Session holen
        spark = get_spark()
        
        # Daten von Solr per HTTP/Cursor laden (ohne spark-solr Connector)
        solr_url = "http://node1.cloud.local:8983/solr/nyc-taxi-raw/select"
        fields = "PULocationID,DOLocationID,total_amount,trip_distance,tpep_pickup_datetime,tpep_dropoff_datetime"
        
        all_docs = []
        cursor_mark = "*"
        batch_size = 10000
        max_docs = 100000
        
        while len(all_docs) < max_docs:
            params = {
                "q": solr_query,
                "fl": fields,
                "rows": batch_size,
                "sort": "id asc",
                "cursorMark": cursor_mark,
                "wt": "json"
            }
            
            response = requests.get(solr_url, params=params, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            docs = result.get("response", {}).get("docs", [])
            all_docs.extend(docs)
            
            next_cursor = result.get("nextCursorMark")
            if next_cursor == cursor_mark or not docs:
                break  # Keine weiteren Daten
            cursor_mark = next_cursor
            
            if len(all_docs) >= max_docs:
                all_docs = all_docs[:max_docs]
                break
        
        logger.info(f"Geladen: {len(all_docs)} Dokumente von Solr")
        
        if not all_docs:
            return jsonify({
                "routes": [],
                "total_trips": 0,
                "spark_time_ms": int((time.time() - start_time) * 1000),
                "message": "Keine Daten für diese Filter gefunden"
            })
        
        # In Spark DataFrame konvertieren
        df = spark.createDataFrame(all_docs)
        
        # Cache für mehrfache Nutzung
        df.cache()
        total_trips = len(all_docs)
        
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
