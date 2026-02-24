#!/usr/bin/env python3
"""
Backend Services - REST API fuer ClickHouse NYC-Taxi Explorer

Alle Queries laufen ueber diesen Flask-Service an ClickHouse.
Kein direkter DB-Zugriff vom Frontend, kein Spark, kein PySpark.

Endpunkte:
  /api/health             - Health Check mit ClickHouse-Status
  /api/zone-names         - NYC Taxi Zone Mappings
  /api/count              - Fahrten zaehlen
  /api/top-routes         - Top N lukrativste Routen
  /api/facets             - Facetten mit Exclude-Logik
  /api/stats              - Stunden-/Wochentag-Statistiken
  /api/fare-distribution  - Fahrpreis-Verteilung in Buckets

Konfiguration via Umgebungsvariablen:
  CLICKHOUSE_HOST  - ClickHouse Host (default: node1.cloud.local)
  CLICKHOUSE_PORT  - ClickHouse HTTP Port (default: 8123)
  BACKEND_PORT     - API Port (default: 5001)
  DEBUG            - Debug Modus (default: false)
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import clickhouse_connect
import logging
import os
import json
from pathlib import Path

app = Flask(__name__)
CORS(app)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# Konfiguration
# ============================================================
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "node1.cloud.local")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "5001"))
DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

TABLE = "nyc_taxi"

# Whitelist erlaubter Felder (gegen SQL-Injection)
ALLOWED_FIELDS = {
    'pickup_hour', 'pickup_dayofweek', 'payment_type',
    'PULocationID', 'DOLocationID', 'total_amount',
    'trip_distance', 'fare_amount', 'tip_amount',
    'passenger_count', 'VendorID', 'RatecodeID'
}

# Berechnete Felder: Frontend-Name -> ClickHouse SQL-Ausdruck
# Diese Spalten existieren nicht physisch in der Tabelle
FIELD_EXPRESSIONS = {
    'pickup_hour': 'toHour(tpep_pickup_datetime)',
    'pickup_dayofweek': 'toDayOfWeek(tpep_pickup_datetime)',
}


def resolve_field(field):
    """Gibt den SQL-Ausdruck fuer ein Feld zurueck (direkt oder berechnet)."""
    return FIELD_EXPRESSIONS.get(field, field)

# ============================================================
# NYC Taxi Zones
# ============================================================
DATA_DIR = Path(__file__).parent / "data"
TAXI_ZONES_FILE = DATA_DIR / "taxi-zones.json"


def load_taxi_zones():
    try:
        with open(TAXI_ZONES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Fehler beim Laden der Taxi Zones: {e}")
        return {}


TAXI_ZONES = load_taxi_zones()
logger.info(f"Loaded {len(TAXI_ZONES)} taxi zones from {TAXI_ZONES_FILE}")

# ============================================================
# ClickHouse Client (pro Request)
# ============================================================
# clickhouse-connect erlaubt keine parallelen Queries pro Client.
# Da das Frontend mehrere API-Calls parallel abfeuert (Promise.all),
# erstellen wir pro Request einen eigenen Client.


def get_client():
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        connect_timeout=10,
        send_receive_timeout=30
    )


# ============================================================
# SQL-Hilfsfunktionen
# ============================================================

def build_where_clause(filters, exclude_field=None):
    """
    Baut WHERE-Klausel aus Filter-Dict.

    Filter-Format: { field: [val1, val2, ...] }
    Range-Werte:   "[10 TO 50]" -> BETWEEN 10 AND 50

    exclude_field: Dieses Feld wird uebersprungen (fuer Facet-Exclude-Logik)
    """
    if not filters:
        return "1=1"

    conditions = []
    for field, values in filters.items():
        if field == exclude_field:
            continue
        if field not in ALLOWED_FIELDS:
            continue

        sql_field = resolve_field(field)
        range_conditions = []
        normal_values = []

        for value in values:
            if isinstance(value, str) and value.startswith('[') and ' TO ' in value:
                # Range: "[10 TO 50]" -> BETWEEN 10 AND 50
                inner = value.strip('[]')
                parts = inner.split(' TO ')
                if len(parts) == 2:
                    try:
                        lo = float(parts[0])
                        hi = float(parts[1])
                        range_conditions.append(f"{sql_field} BETWEEN {lo} AND {hi}")
                    except ValueError:
                        pass
            else:
                if isinstance(value, (int, float)):
                    normal_values.append(str(value))
                else:
                    # String-Werte quoten
                    safe_val = str(value).replace("'", "''")
                    normal_values.append(f"'{safe_val}'")

        field_conditions = []
        if normal_values:
            if len(normal_values) == 1:
                field_conditions.append(f"{sql_field} = {normal_values[0]}")
            else:
                vals = ', '.join(normal_values)
                field_conditions.append(f"{sql_field} IN ({vals})")

        field_conditions.extend(range_conditions)

        if len(field_conditions) == 1:
            conditions.append(field_conditions[0])
        elif len(field_conditions) > 1:
            conditions.append(f"({' OR '.join(field_conditions)})")

    return " AND ".join(conditions) if conditions else "1=1"


# ============================================================
# API Endpoints
# ============================================================

@app.route('/api/health', methods=['GET'])
def health():
    """Health Check mit ClickHouse-Status."""
    try:
        client = get_client()
        result = client.query("SELECT count() FROM system.clusters WHERE cluster = 'cloudkoffer'")
        replica_count = result.first_row[0] if result.result_rows else 0

        return jsonify({
            "status": "ok",
            "service": "backend-services",
            "clickhouse_host": CLICKHOUSE_HOST,
            "clickhouse_port": CLICKHOUSE_PORT,
            "cluster_replicas": replica_count
        })
    except Exception as e:
        return jsonify({
            "status": "degraded",
            "service": "backend-services",
            "error": str(e)
        }), 503


@app.route('/api/zone-names', methods=['GET'])
def zone_names():
    """NYC Taxi Zone Namen."""
    return jsonify(TAXI_ZONES)


@app.route('/api/count', methods=['POST'])
def count_trips():
    """
    Zaehlt Fahrten basierend auf Filtern.

    Request: { "filters": { "pickup_hour": [18, 19], ... } }
    Response: { "count": 12345, "can_analyze": true }
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        filters = data.get('filters', {})

        where = build_where_clause(filters)
        sql = f"SELECT count() FROM {TABLE} WHERE {where}"

        client = get_client()
        result = client.query(sql)
        count = result.first_row[0]

        return jsonify({
            "count": count,
            "can_analyze": count > 0
        })
    except Exception as e:
        logger.exception("Fehler beim Zaehlen")
        return jsonify({"count": 0, "error": str(e)}), 500


@app.route('/api/facets', methods=['POST'])
def facets():
    """
    Facetten mit Exclude-Logik fuer Mehrfachauswahl.

    Fuer jedes Facetten-Feld werden die Counts OHNE den eigenen Filter berechnet,
    damit der Nutzer sehen kann, welche anderen Optionen verfuegbar sind.

    Request: { "filters": {...}, "facet_fields": ["pickup_hour", ...] }
    Response: { "numFound": 12345, "facets": { "pickup_hour": [{"value": "0", "count": 100}, ...] } }
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        filters = data.get('filters', {})
        facet_fields = data.get('facet_fields', [])

        client = get_client()

        # Gesamtanzahl mit allen Filtern
        where_all = build_where_clause(filters)
        count_result = client.query(f"SELECT count() FROM {TABLE} WHERE {where_all}")
        num_found = count_result.first_row[0]

        # Facetten pro Feld (mit Exclude-Logik)
        facets_result = {}
        for field in facet_fields:
            if field not in ALLOWED_FIELDS:
                continue

            # WHERE ohne den eigenen Filter
            sql_field = resolve_field(field)
            where_excluded = build_where_clause(filters, exclude_field=field)
            sql = f"""
                SELECT toString({sql_field}) AS val, count() AS cnt
                FROM {TABLE}
                WHERE {where_excluded}
                GROUP BY val
                ORDER BY cnt DESC
                LIMIT 30
            """

            result = client.query(sql)
            facets_result[field] = [
                {"value": row[0], "count": row[1]}
                for row in result.result_rows
            ]

        return jsonify({
            "numFound": num_found,
            "facets": facets_result
        })
    except Exception as e:
        logger.exception("Fehler bei Facetten")
        return jsonify({"numFound": 0, "facets": {}, "error": str(e)}), 500


@app.route('/api/stats', methods=['POST'])
def stats():
    """
    Statistiken fuer Balkendiagramme (gruppiert nach Feld).

    Request: { "filters": {...}, "group_by": "pickup_hour" }
    Response: [{ "pickup_hour": 0, "sum(total_amount)": 123.45, "avg(total_amount)": 12.3, "count(*)": 10 }, ...]
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        filters = data.get('filters', {})
        group_by = data.get('group_by', 'pickup_hour')

        if group_by not in ALLOWED_FIELDS:
            return jsonify({"error": f"Invalid group_by field: {group_by}"}), 400

        sql_field = resolve_field(group_by)
        where = build_where_clause(filters)
        sql = f"""
            SELECT
                {sql_field} AS field_val,
                count() AS `count(*)`,
                sum(total_amount) AS `sum(total_amount)`,
                avg(total_amount) AS `avg(total_amount)`
            FROM {TABLE}
            WHERE {where}
            GROUP BY field_val
            ORDER BY field_val ASC
        """

        client = get_client()
        result = client.query(sql)

        return jsonify([
            {
                group_by: int(row[0]) if isinstance(row[0], (int, float)) else row[0],
                "count(*)": row[1],
                "sum(total_amount)": round(float(row[2]), 2),
                "avg(total_amount)": round(float(row[3]), 2)
            }
            for row in result.result_rows
        ])
    except Exception as e:
        logger.exception("Fehler bei Stats")
        return jsonify([])


@app.route('/api/fare-distribution', methods=['POST'])
def fare_distribution():
    """
    Fahrpreis-Verteilung in 10er-Buckets ($0-10, $10-20, ..., $90-100).

    Request: { "filters": {...} }
    Response: [{ "label": "$0-10", "count": 100, "val": 0 }, ...]
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        filters = data.get('filters', {})

        where = build_where_clause(filters)

        # Range-Buckets per SQL: floor(total_amount / 10) * 10
        sql = f"""
            SELECT
                toInt32(floor(total_amount / 10)) * 10 AS bucket,
                count() AS cnt
            FROM {TABLE}
            WHERE {where} AND total_amount >= 0 AND total_amount < 100
            GROUP BY bucket
            ORDER BY bucket ASC
        """

        client = get_client()
        result = client.query(sql)

        return jsonify([
            {
                "label": f"${row[0]}-{row[0] + 10}",
                "count": row[1],
                "val": row[0]
            }
            for row in result.result_rows
        ])
    except Exception as e:
        logger.exception("Fehler bei Fare Distribution")
        return jsonify([])


@app.route('/api/top-routes', methods=['POST'])
def top_routes():
    """
    Top N lukrativste Routen per SQL (kein Spark noetig).

    Score = (trip_count * avg_fare) / avg_duration

    Request: { "filters": {...}, "limit": 5 }
    Response: { "routes": [...], "total_trips": 50000, "spark_time_ms": 250, "query": "..." }
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        filters = data.get('filters', {})
        limit = min(data.get('limit', 5), 20)

        where = build_where_clause(filters)

        # Duration: Differenz in Minuten, mit Validierung
        sql = f"""
            SELECT
                PULocationID,
                DOLocationID,
                count() AS trip_count,
                round(avg(total_amount), 2) AS avg_fare,
                round(avg(dateDiff('minute', tpep_pickup_datetime, tpep_dropoff_datetime)), 1) AS avg_duration_min,
                round(avg(trip_distance), 2) AS avg_distance,
                round(sum(total_amount), 2) AS total_revenue
            FROM {TABLE}
            WHERE {where}
              AND total_amount > 0
              AND dateDiff('minute', tpep_pickup_datetime, tpep_dropoff_datetime) BETWEEN 1 AND 120
            GROUP BY PULocationID, DOLocationID
            HAVING trip_count >= 10
            ORDER BY (trip_count * avg_fare) / avg_duration_min DESC
            LIMIT {limit}
        """

        # Gesamtzahl gefilterter Fahrten
        count_sql = f"SELECT count() FROM {TABLE} WHERE {where}"

        client = get_client()

        import time
        start = time.time()

        routes_result = client.query(sql)
        count_result = client.query(count_sql)

        elapsed_ms = int((time.time() - start) * 1000)
        total_trips = count_result.first_row[0]

        routes_list = []
        for row in routes_result.result_rows:
            pu, do, count, avg_fare, avg_dur, avg_dist, total_rev = row
            fare_per_min = round(avg_fare / avg_dur, 2) if avg_dur > 0 else 0
            score = round((count * avg_fare) / avg_dur, 1) if avg_dur > 0 else 0

            routes_list.append({
                "PULocationID": pu,
                "DOLocationID": do,
                "trip_count": count,
                "avg_fare": float(avg_fare),
                "avg_duration_min": float(avg_dur),
                "avg_distance": float(avg_dist),
                "fare_per_minute": fare_per_min,
                "total_revenue": float(total_rev),
                "score": score
            })

        return jsonify({
            "routes": routes_list,
            "total_trips": total_trips,
            "spark_time_ms": elapsed_ms,
            "query": where
        })
    except Exception as e:
        logger.exception("Fehler bei Top Routes")
        return jsonify({
            "routes": [],
            "total_trips": 0,
            "spark_time_ms": 0,
            "error": str(e)
        }), 503


# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    logger.info(f"Starte Backend Services auf Port {BACKEND_PORT}...")
    logger.info(f"  ClickHouse: {CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}")
    logger.info(f"  Tabelle: {TABLE}")
    logger.info(f"  Taxi Zones: {len(TAXI_ZONES)} geladen")

    app.run(host='0.0.0.0', port=BACKEND_PORT, debug=DEBUG)
