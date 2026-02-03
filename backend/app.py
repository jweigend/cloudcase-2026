#!/usr/bin/env python3
"""
Flask Backend für Taxi-Routen-Analyse
Nutzt PySpark für komplexe Berechnungen auf gefilterten Daten
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, avg, count, sum as spark_sum,
    unix_timestamp, round as spark_round
)
import logging

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Spark Session (lazy initialization)
_spark = None

def get_spark():
    """Lazy Spark Session - wird beim ersten Aufruf erstellt"""
    global _spark
    if _spark is None:
        logger.info("Initializing Spark Session...")
        _spark = (SparkSession.builder
            .appName("TaxiRoutesAnalysis")
            .master("spark://node1.cloud.local:7077")
            .config("spark.jars.packages", "org.rdf4j:rdf4j-rio-jsonld:4.3.7")
            .config("spark.executor.memory", "2g")
            .config("spark.executor.cores", "2")
            .config("spark.sql.shuffle.partitions", "8")
            .getOrCreate())
        logger.info("Spark Session ready")
    return _spark


def build_solr_query(filters: dict) -> str:
    """Baut Solr-Query aus den Filtern"""
    conditions = []
    
    # Wochentag (1=Sonntag, 2=Montag, ..., 7=Samstag)
    if filters.get('pickup_dayofweek'):
        days = filters['pickup_dayofweek']
        if isinstance(days, list) and len(days) > 0:
            day_query = ' OR '.join([f'pickup_dayofweek:{d}' for d in days])
            conditions.append(f'({day_query})')
    
    # Stunde
    if filters.get('pickup_hour'):
        hours = filters['pickup_hour']
        if isinstance(hours, list) and len(hours) > 0:
            hour_query = ' OR '.join([f'pickup_hour:{h}' for h in hours])
            conditions.append(f'({hour_query})')
    
    # Bezahlart
    if filters.get('payment_type'):
        types = filters['payment_type']
        if isinstance(types, list) and len(types) > 0:
            type_query = ' OR '.join([f'payment_type:{t}' for t in types])
            conditions.append(f'({type_query})')
    
    # Passagierzahl
    if filters.get('passenger_count'):
        counts = filters['passenger_count']
        if isinstance(counts, list) and len(counts) > 0:
            count_query = ' OR '.join([f'passenger_count:{c}' for c in counts])
            conditions.append(f'({count_query})')
    
    # Pickup Zone
    if filters.get('PULocationID'):
        zones = filters['PULocationID']
        if isinstance(zones, list) and len(zones) > 0:
            zone_query = ' OR '.join([f'PULocationID:{z}' for z in zones])
            conditions.append(f'({zone_query})')
    
    # Dropoff Zone
    if filters.get('DOLocationID'):
        zones = filters['DOLocationID']
        if isinstance(zones, list) and len(zones) > 0:
            zone_query = ' OR '.join([f'DOLocationID:{z}' for z in zones])
            conditions.append(f'({zone_query})')
    
    if conditions:
        return ' AND '.join(conditions)
    return '*:*'


@app.route('/api/health', methods=['GET'])
def health():
    """Health Check Endpoint"""
    return jsonify({'status': 'ok', 'service': 'taxi-routes-backend'})


@app.route('/api/top-routes', methods=['POST'])
def top_routes():
    """
    Berechnet die Top 5 lukrativsten Routen basierend auf Filtern
    
    Request Body:
    {
        "filters": {
            "pickup_dayofweek": [6, 7],  // Samstag, Sonntag
            "pickup_hour": [18, 19, 20, 21],
            "payment_type": [1, 2]
        },
        "limit": 5
    }
    
    Response:
    {
        "routes": [
            {
                "PULocationID": 132,
                "DOLocationID": 265,
                "trip_count": 1234,
                "avg_fare": 45.50,
                "avg_duration_min": 22.5,
                "avg_distance": 12.3,
                "score": 2486.67,
                "fare_per_minute": 2.02
            },
            ...
        ],
        "total_trips": 50000,
        "query": "pickup_dayofweek:(6 OR 7) AND ..."
    }
    """
    try:
        data = request.get_json() or {}
        filters = data.get('filters', {})
        limit = min(data.get('limit', 5), 20)  # Max 20 Routen
        
        solr_query = build_solr_query(filters)
        logger.info(f"Solr Query: {solr_query}")
        
        spark = get_spark()
        
        # Daten von Solr laden mit Filter
        # Nutze das solr-spark Paket (muss installiert sein)
        df = (spark.read
            .format("solr")
            .option("zkhost", "node1.cloud.local:2181,node2.cloud.local:2181,node3.cloud.local:2181")
            .option("collection", "nyc-taxi-raw")
            .option("query", solr_query)
            .option("fields", "PULocationID,DOLocationID,total_amount,trip_distance,tpep_pickup_datetime,tpep_dropoff_datetime")
            .option("max_rows", "100000")  # Limit für Performance
            .load())
        
        total_trips = df.count()
        logger.info(f"Loaded {total_trips} trips from Solr")
        
        if total_trips == 0:
            return jsonify({
                'routes': [],
                'total_trips': 0,
                'query': solr_query,
                'message': 'Keine Fahrten für diese Filter gefunden'
            })
        
        # Fahrtdauer berechnen (in Minuten)
        df_with_duration = df.withColumn(
            "duration_min",
            (unix_timestamp(col("tpep_dropoff_datetime")) - 
             unix_timestamp(col("tpep_pickup_datetime"))) / 60.0
        )
        
        # Ungültige Fahrten filtern (Dauer > 1 min und < 180 min, Fare > 0)
        df_valid = df_with_duration.filter(
            (col("duration_min") > 1) & 
            (col("duration_min") < 180) &
            (col("total_amount") > 0) &
            (col("trip_distance") > 0)
        )
        
        # Nach Route gruppieren und aggregieren
        routes_df = (df_valid
            .groupBy("PULocationID", "DOLocationID")
            .agg(
                count("*").alias("trip_count"),
                spark_round(avg("total_amount"), 2).alias("avg_fare"),
                spark_round(avg("duration_min"), 1).alias("avg_duration_min"),
                spark_round(avg("trip_distance"), 2).alias("avg_distance")
            ))
        
        # Lukrativitäts-Score berechnen
        # Score = (trip_count * avg_fare) / avg_duration_min
        # Hohe Frequenz + Hoher Preis + Kurze Dauer = Lukrativ
        routes_scored = routes_df.withColumn(
            "score",
            spark_round(
                (col("trip_count") * col("avg_fare")) / col("avg_duration_min"), 
                2
            )
        ).withColumn(
            "fare_per_minute",
            spark_round(col("avg_fare") / col("avg_duration_min"), 2)
        )
        
        # Top N nach Score sortieren
        top_routes = (routes_scored
            .orderBy(col("score").desc())
            .limit(limit)
            .collect())
        
        # In JSON-Format konvertieren
        result = []
        for row in top_routes:
            result.append({
                'PULocationID': int(row['PULocationID']),
                'DOLocationID': int(row['DOLocationID']),
                'trip_count': int(row['trip_count']),
                'avg_fare': float(row['avg_fare']),
                'avg_duration_min': float(row['avg_duration_min']),
                'avg_distance': float(row['avg_distance']),
                'score': float(row['score']),
                'fare_per_minute': float(row['fare_per_minute'])
            })
        
        return jsonify({
            'routes': result,
            'total_trips': total_trips,
            'valid_trips': df_valid.count(),
            'query': solr_query
        })
        
    except Exception as e:
        logger.exception("Error calculating top routes")
        return jsonify({
            'error': str(e),
            'routes': []
        }), 500


@app.route('/api/count', methods=['POST'])
def count_trips():
    """
    Zählt Fahrten für gegebene Filter (Vorschau bevor Spark-Job gestartet wird)
    Nutzt direkt Solr statt Spark für schnelle Antwort
    """
    import urllib.request
    import urllib.parse
    import json
    
    try:
        data = request.get_json() or {}
        filters = data.get('filters', {})
        solr_query = build_solr_query(filters)
        
        # Direkte Solr-Abfrage für Count
        solr_url = f"http://node1.cloud.local:8983/solr/nyc-taxi-raw/select"
        params = urllib.parse.urlencode({
            'q': solr_query,
            'rows': 0,
            'wt': 'json'
        })
        
        with urllib.request.urlopen(f"{solr_url}?{params}", timeout=10) as response:
            result = json.loads(response.read().decode())
            count = result['response']['numFound']
        
        return jsonify({
            'count': count,
            'query': solr_query,
            'can_analyze': count <= 100000
        })
        
    except Exception as e:
        logger.exception("Error counting trips")
        return jsonify({'error': str(e), 'count': -1}), 500


if __name__ == '__main__':
    # Development Server
    app.run(host='0.0.0.0', port=5001, debug=True)
