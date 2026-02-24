#!/usr/bin/env python3
"""
Backend Services - Lokale REST API Endpoints

Dieser Service stellt lokale API Endpoints bereit:
  - /api/health      - Health Check mit Spark-Status
  - /api/zone-names  - NYC Taxi Zone Mappings
  - /api/count       - Fahrten zählen (via Solr)
  - /api/top-routes  - Top Routes berechnen (via Spark Cluster)

Konfiguration via Umgebungsvariablen:
  SPARK_MASTER   - Spark Master URL (für Health Check)
  SOLR_HOST      - Solr Host (default: node1.cloud.local)
  SOLR_PORT      - Solr Port (default: 8983)
  BACKEND_PORT   - API Port (default: 5001)
  DEBUG          - Debug Modus (default: false)

Der Top-Routes Service läuft im Spark Cluster, siehe:
  top_routes_solr_spark_service.py
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import logging
import os
import json
from pathlib import Path

# Spark-basierter Top Routes Service (läuft im Cluster)
from top_routes_solr_spark_service import (
    calculate_top_routes,
    get_spark_status
)

app = Flask(__name__)
CORS(app)

# Logging einrichten
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# Konfiguration via Umgebungsvariablen
# ============================================================
SOLR_HOST = os.getenv("SOLR_HOST", "node1.cloud.local")
SOLR_PORT = int(os.getenv("SOLR_PORT", "8983"))
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "5001"))
DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

# Abgeleitete Konfiguration
COLLECTION = "nyc-taxi-raw"
SOLR_URL = f"http://{SOLR_HOST}:{SOLR_PORT}/solr/{COLLECTION}"

# ============================================================
# NYC Taxi Zones - Single Source of Truth
# ============================================================
DATA_DIR = Path(__file__).parent / "data"
TAXI_ZONES_FILE = DATA_DIR / "taxi-zones.json"


def load_taxi_zones():
    """Lädt NYC Taxi Zone Mappings aus JSON Datei."""
    try:
        with open(TAXI_ZONES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Fehler beim Laden der Taxi Zones: {e}")
        return {}


# Beim Start laden (cached)
TAXI_ZONES = load_taxi_zones()
logger.info(f"Loaded {len(TAXI_ZONES)} taxi zones from {TAXI_ZONES_FILE}")


# ============================================================
# API Endpoints - Lokale Services
# ============================================================

@app.route('/api/health', methods=['GET'])
def health():
    """
    Health Check Endpoint mit Spark-Status.
    
    Response:
    {
        "status": "ok" | "degraded",
        "service": "backend-services",
        "spark_status": "connected" | "unavailable",
        "spark_master": "spark://node0.cloud.local:7077",
        "solr_url": "http://node1.cloud.local:8983/solr/nyc-taxi-raw"
    }
    """
    spark_status = get_spark_status()
    
    response = {
        "status": "ok" if spark_status["connected"] else "degraded",
        "service": "backend-services",
        "spark_status": "connected" if spark_status["connected"] else "unavailable",
        "spark_master": spark_status["master"],
        "solr_url": SOLR_URL
    }
    
    if spark_status["error"]:
        response["spark_error"] = spark_status["error"]
    
    return jsonify(response)


@app.route('/api/zone-names', methods=['GET'])
def zone_names():
    """
    Gibt die NYC Taxi Zone Namen zurück.
    
    Response Format:
    {
        "1": {"name": "Newark Airport", "borough": "EWR", "short": "EWR"},
        "2": {"name": "Jamaica Bay", "borough": "Queens", "short": "QN"},
        ...
        "265": {"name": "Outside of NYC", "borough": "N/A", "short": "N/A"}
    }
    """
    return jsonify(TAXI_ZONES)


@app.route('/api/count', methods=['POST'])
def count_trips():
    """
    Zählt Fahrten basierend auf Filtern (schnell via Solr).
    
    Request Body:
    {
        "filters": {
            "pickup_hour": [18, 19],
            "payment_type": [1],
            "total_amount": ["[10 TO 50]"]
        }
    }
    
    Response:
    {
        "count": 12345,
        "can_analyze": true
    }
    """
    try:
        data = request.get_json() or {}
        filters = data.get('filters', {})
        
        # Filter zu Solr fq Parametern konvertieren
        fq_parts = []
        for field, values in filters.items():
            if isinstance(values, list):
                # Range-Filter erkennen (beginnt mit '[')
                range_values = [v for v in values if isinstance(v, str) and v.startswith('[')]
                normal_values = [v for v in values if not (isinstance(v, str) and v.startswith('['))]
                
                # Range-Filter direkt anhängen
                for rv in range_values:
                    fq_parts.append(f"{field}:{rv}")
                
                # Normale Werte mit OR gruppieren
                if normal_values:
                    value_str = " OR ".join([str(v) for v in normal_values])
                    fq_parts.append(f"{field}:({value_str})")
            else:
                fq_parts.append(f"{field}:{values}")
        
        params = {
            "q": "*:*",
            "rows": 0,
            "wt": "json"
        }
        
        if fq_parts:
            params["fq"] = fq_parts
        
        response = requests.get(f"{SOLR_URL}/select", params=params, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        count = result.get("response", {}).get("numFound", 0)
        
        return jsonify({
            "count": count,
            "can_analyze": count <= 1000000 and count > 0
        })
        
    except Exception as e:
        logger.exception("Fehler beim Zählen")
        return jsonify({"count": 0, "error": str(e)}), 500


# ============================================================
# API Endpoint - Spark Cluster Service
# ============================================================

@app.route('/api/top-routes', methods=['POST'])
def top_routes():
    """
    Berechnet die Top N lukrativsten Routen via Spark Cluster.
    
    Dieser Endpoint delegiert an den Spark-basierten Service in
    top-routes-solr-spark-service.py, der die verteilte Berechnung
    im Cluster durchführt.
    
    Request Body:
    {
        "filters": {"pickup_hour": [18, 19], "payment_type": [1]},
        "limit": 5
    }
    
    Response:
    {
        "routes": [
            {
                "PULocationID": 132,
                "DOLocationID": 161,
                "trip_count": 1234,
                "avg_fare": 52.50,
                "avg_duration_min": 28.5,
                "avg_distance": 12.3,
                "fare_per_minute": 1.84,
                "total_revenue": 64785.00,
                "score": 2267.4
            },
            ...
        ],
        "total_trips": 50000,
        "spark_time_ms": 2500,
        "load_strategy": "parallel_shards",
        "shards_used": 4,
        "query": "pickup_hour:(18 OR 19) AND payment_type:1"
    }
    """
    data = request.get_json() or {}
    filters = data.get('filters', [])
    limit = data.get('limit', 5)
    
    # Delegiere an Spark Service
    result = calculate_top_routes(filters=filters, limit=limit)
    
    # Fehlerfall mit HTTP 503
    if "error" in result and not result.get("routes"):
        return jsonify(result), 503
    
    return jsonify(result)


# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    logger.info(f"Starte Backend Services auf Port {BACKEND_PORT}...")
    logger.info(f"  SOLR_URL: {SOLR_URL}")
    logger.info(f"  DEBUG: {DEBUG}")
    logger.info(f"  Taxi Zones: {len(TAXI_ZONES)} geladen")
    
    # use_reloader=False wichtig für Spark! Reloader würde SparkContext zerstören
    app.run(host='0.0.0.0', port=BACKEND_PORT, debug=DEBUG, use_reloader=False)
