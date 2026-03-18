#!/usr/bin/env python3
"""
Backend Services - REST API fuer Elasticsearch Monitoring Data Explorer

Alle Queries laufen ueber diesen Flask-Service an Elasticsearch.

Endpunkte:
  /api/health             - Health Check mit Elasticsearch-Status
  /api/count              - Events zaehlen
  /api/facets             - Facetten mit Exclude-Logik
  /api/stats              - Stunden-Statistiken
  /api/search             - Volltext-Suche
  /api/top-alerts         - Top N haeufigste Alerts
  /api/response-distribution - Response-Time-Verteilung

Konfiguration via Umgebungsvariablen:
  ES_HOST        - Elasticsearch Host (default: node1.cloud.local)
  ES_PORT        - Elasticsearch HTTP Port (default: 9200)
  BACKEND_PORT   - API Port (default: 5001)
  DEBUG          - Debug Modus (default: false)
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from elasticsearch import Elasticsearch
import logging
import os

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
ES_HOST = os.getenv("ES_HOST", "node1.cloud.local")
ES_PORT = int(os.getenv("ES_PORT", "9200"))
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "5001"))
DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

INDEX = "monitoring-events"

# Whitelist erlaubter Felder (gegen Injection)
ALLOWED_FIELDS = {
    'host', 'service', 'event_type', 'severity',
    'cpu_percent', 'memory_percent', 'disk_percent',
    'response_time_ms', 'status_code', 'bytes_sent',
    'event_hour'
}


def get_es():
    """Erstellt einen Elasticsearch-Client pro Request."""
    return Elasticsearch(
        [f"http://{ES_HOST}:{ES_PORT}"],
        request_timeout=30
    )


# ============================================================
# Filter-Hilfsfunktionen
# ============================================================

def build_filter_clauses(filters, exclude_field=None):
    """
    Baut Elasticsearch-Filter aus Filter-Dict.

    Filter-Format: { field: [val1, val2, ...] }
    Range-Werte:   "[10 TO 50]" -> range query

    exclude_field: Dieses Feld wird uebersprungen (fuer Facet-Exclude-Logik)
    """
    clauses = []
    if not filters:
        return clauses

    for field, values in filters.items():
        if field == exclude_field:
            continue
        if field not in ALLOWED_FIELDS:
            continue

        # Berechnete Felder
        es_field = field
        if field == 'event_hour':
            # Script-basierter Filter fuer Stunde
            hours = [int(v) for v in values if not isinstance(v, str) or not v.startswith('[')]
            if hours:
                clauses.append({
                    'script': {
                        'script': {
                            'source': "doc['timestamp'].value.getHour() == params.hour",
                            'params': {'hour': hours[0]} if len(hours) == 1 else None
                        }
                    }
                })
                if len(hours) > 1:
                    clauses.append({
                        'script': {
                            'script': {
                                'source': "params.hours.contains(doc['timestamp'].value.getHour())",
                                'params': {'hours': hours}
                            }
                        }
                    })
            continue

        range_clauses = []
        term_values = []

        for value in values:
            if isinstance(value, str) and value.startswith('[') and ' TO ' in value:
                inner = value.strip('[]')
                parts = inner.split(' TO ')
                if len(parts) == 2:
                    try:
                        lo = float(parts[0])
                        hi = float(parts[1])
                        range_clauses.append({'range': {es_field: {'gte': lo, 'lte': hi}}})
                    except ValueError:
                        pass
            else:
                term_values.append(value)

        if term_values:
            if len(term_values) == 1:
                clauses.append({'term': {es_field: term_values[0]}})
            else:
                clauses.append({'terms': {es_field: term_values}})

        clauses.extend(range_clauses)

    return clauses


def build_query(filters, exclude_field=None):
    """Baut eine Elasticsearch-Query aus Filtern."""
    clauses = build_filter_clauses(filters, exclude_field)
    if not clauses:
        return {'match_all': {}}
    return {'bool': {'filter': clauses}}


# ============================================================
# API Endpoints
# ============================================================

@app.route('/api/health', methods=['GET'])
def health():
    """Health Check mit Elasticsearch-Status."""
    try:
        es = get_es()
        cluster = es.cluster.health()
        return jsonify({
            "status": "ok",
            "service": "backend-services",
            "es_host": ES_HOST,
            "es_port": ES_PORT,
            "cluster_name": cluster['cluster_name'],
            "cluster_status": cluster['status'],
            "cluster_nodes": cluster['number_of_nodes']
        })
    except Exception as e:
        return jsonify({
            "status": "degraded",
            "service": "backend-services",
            "error": str(e)
        }), 503


@app.route('/api/count', methods=['POST'])
def count_events():
    """
    Zaehlt Events basierend auf Filtern.

    Request: { "filters": { "severity": ["error", "critical"], ... } }
    Response: { "count": 12345, "can_analyze": true }
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        filters = data.get('filters', {})

        es = get_es()
        result = es.count(index=INDEX, body={'query': build_query(filters)})
        count = result['count']

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

    Request: { "filters": {...}, "facet_fields": ["severity", ...] }
    Response: { "numFound": 12345, "facets": { "severity": [...] } }
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        filters = data.get('filters', {})
        facet_fields = data.get('facet_fields', [])

        es = get_es()

        # Gesamtanzahl mit allen Filtern
        count_result = es.count(index=INDEX, body={'query': build_query(filters)})
        num_found = count_result['count']

        # Facetten pro Feld (mit Exclude-Logik)
        facets_result = {}
        for field in facet_fields:
            if field not in ALLOWED_FIELDS:
                continue

            query = build_query(filters, exclude_field=field)

            if field == 'event_hour':
                # Spezielle Aggregation fuer Stunden aus Timestamp
                agg_body = {
                    'size': 0,
                    'query': query,
                    'aggs': {
                        'facet': {
                            'date_histogram': {
                                'field': 'timestamp',
                                'calendar_interval': 'hour'
                            }
                        }
                    }
                }
                result = es.search(index=INDEX, body=agg_body)
                # Stunden aggregieren ueber alle Tage
                hour_counts = {}
                for bucket in result['aggregations']['facet']['buckets']:
                    # Stunde aus key_as_string extrahieren
                    hour = bucket.get('key_as_string', '')
                    if 'T' in hour:
                        h = int(hour.split('T')[1][:2])
                        hour_counts[h] = hour_counts.get(h, 0) + bucket['doc_count']
                facets_result[field] = [
                    {'value': str(h), 'count': c}
                    for h, c in sorted(hour_counts.items())
                ]
            else:
                agg_body = {
                    'size': 0,
                    'query': query,
                    'aggs': {
                        'facet': {
                            'terms': {'field': field, 'size': 30}
                        }
                    }
                }
                result = es.search(index=INDEX, body=agg_body)
                facets_result[field] = [
                    {'value': bucket['key'], 'count': bucket['doc_count']}
                    for bucket in result['aggregations']['facet']['buckets']
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

    Request: { "filters": {...}, "group_by": "event_hour" }
    Response: [{ "event_hour": 0, "count(*)": 100, ... }, ...]
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        filters = data.get('filters', {})
        group_by = data.get('group_by', 'event_hour')

        if group_by not in ALLOWED_FIELDS:
            return jsonify({"error": f"Invalid group_by field: {group_by}"}), 400

        es = get_es()
        query = build_query(filters)

        if group_by == 'event_hour':
            body = {
                'size': 0,
                'query': query,
                'aggs': {
                    'by_hour': {
                        'date_histogram': {
                            'field': 'timestamp',
                            'calendar_interval': 'hour'
                        },
                        'aggs': {
                            'avg_response': {'avg': {'field': 'response_time_ms'}},
                            'total_bytes': {'sum': {'field': 'bytes_sent'}}
                        }
                    }
                }
            }
            result = es.search(index=INDEX, body=body)
            # Stunden aggregieren
            hour_data = {}
            for bucket in result['aggregations']['by_hour']['buckets']:
                hour_str = bucket.get('key_as_string', '')
                if 'T' in hour_str:
                    h = int(hour_str.split('T')[1][:2])
                    if h not in hour_data:
                        hour_data[h] = {'count': 0, 'avg_resp_sum': 0, 'avg_resp_count': 0, 'total_bytes': 0}
                    hour_data[h]['count'] += bucket['doc_count']
                    if bucket['avg_response']['value'] is not None:
                        hour_data[h]['avg_resp_sum'] += bucket['avg_response']['value'] * bucket['doc_count']
                        hour_data[h]['avg_resp_count'] += bucket['doc_count']
                    hour_data[h]['total_bytes'] += bucket['total_bytes']['value'] or 0

            stats_list = []
            for h in sorted(hour_data.keys()):
                d = hour_data[h]
                avg_resp = d['avg_resp_sum'] / d['avg_resp_count'] if d['avg_resp_count'] > 0 else 0
                stats_list.append({
                    'event_hour': h,
                    'count(*)': d['count'],
                    'avg(response_time_ms)': round(avg_resp, 1),
                    'sum(bytes_sent)': round(d['total_bytes'], 0)
                })
            return jsonify(stats_list)
        else:
            body = {
                'size': 0,
                'query': query,
                'aggs': {
                    'grouped': {
                        'terms': {'field': group_by, 'size': 50},
                        'aggs': {
                            'avg_response': {'avg': {'field': 'response_time_ms'}},
                            'total_bytes': {'sum': {'field': 'bytes_sent'}}
                        }
                    }
                }
            }
            result = es.search(index=INDEX, body=body)
            return jsonify([
                {
                    group_by: bucket['key'],
                    'count(*)': bucket['doc_count'],
                    'avg(response_time_ms)': round(bucket['avg_response']['value'] or 0, 1),
                    'sum(bytes_sent)': round(bucket['total_bytes']['value'] or 0, 0)
                }
                for bucket in result['aggregations']['grouped']['buckets']
            ])
    except Exception as e:
        logger.exception("Fehler bei Stats")
        return jsonify([])


@app.route('/api/search', methods=['POST'])
def search():
    """
    Volltext-Suche ueber Log-Messages.

    Request: { "filters": {...}, "query": "connection timeout", "size": 20 }
    Response: { "hits": [...], "total": 1234 }
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        filters = data.get('filters', {})
        search_query = data.get('query', '')
        size = min(data.get('size', 20), 100)

        es = get_es()
        filter_clauses = build_filter_clauses(filters)

        if search_query:
            must_clause = {'match': {'message': search_query}}
        else:
            must_clause = {'match_all': {}}

        body = {
            'size': size,
            'query': {
                'bool': {
                    'must': [must_clause],
                    'filter': filter_clauses
                }
            },
            'sort': [{'timestamp': 'desc'}],
            '_source': ['timestamp', 'host', 'service', 'severity', 'event_type',
                        'message', 'cpu_percent', 'memory_percent', 'response_time_ms', 'status_code']
        }

        result = es.search(index=INDEX, body=body)
        hits = [hit['_source'] for hit in result['hits']['hits']]
        total = result['hits']['total']['value']

        return jsonify({
            "hits": hits,
            "total": total
        })
    except Exception as e:
        logger.exception("Fehler bei Suche")
        return jsonify({"hits": [], "total": 0, "error": str(e)}), 500


@app.route('/api/top-alerts', methods=['POST'])
def top_alerts():
    """
    Top N haeufigste Alert-Messages.

    Request: { "filters": {...}, "limit": 5 }
    Response: { "alerts": [...], "total_events": 50000 }
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        filters = data.get('filters', {})
        limit = min(data.get('limit', 5), 20)

        es = get_es()
        query = build_query(filters)

        # Nur Errors und Critical
        body = {
            'size': 0,
            'query': {
                'bool': {
                    'must': [query] if query != {'match_all': {}} else [],
                    'filter': [{'terms': {'severity': ['error', 'critical']}}]
                }
            },
            'aggs': {
                'by_host_service': {
                    'multi_terms': {
                        'terms': [
                            {'field': 'host'},
                            {'field': 'service'}
                        ],
                        'size': limit
                    },
                    'aggs': {
                        'avg_cpu': {'avg': {'field': 'cpu_percent'}},
                        'avg_memory': {'avg': {'field': 'memory_percent'}},
                        'avg_response': {'avg': {'field': 'response_time_ms'}},
                        'latest': {
                            'top_hits': {
                                'size': 1,
                                'sort': [{'timestamp': 'desc'}],
                                '_source': ['message', 'timestamp', 'severity']
                            }
                        }
                    }
                }
            }
        }

        result = es.search(index=INDEX, body=body)

        # Gesamtanzahl gefilterter Events
        count_result = es.count(index=INDEX, body={'query': build_query(filters)})
        total_events = count_result['count']

        alerts = []
        for bucket in result['aggregations']['by_host_service']['buckets']:
            latest = bucket['latest']['hits']['hits'][0]['_source']
            alerts.append({
                'host': bucket['key'][0],
                'service': bucket['key'][1],
                'error_count': bucket['doc_count'],
                'avg_cpu': round(bucket['avg_cpu']['value'] or 0, 1),
                'avg_memory': round(bucket['avg_memory']['value'] or 0, 1),
                'avg_response_ms': round(bucket['avg_response']['value'] or 0, 0),
                'latest_message': latest.get('message', ''),
                'latest_timestamp': latest.get('timestamp', ''),
                'latest_severity': latest.get('severity', '')
            })

        return jsonify({
            "alerts": alerts,
            "total_events": total_events
        })
    except Exception as e:
        logger.exception("Fehler bei Top Alerts")
        return jsonify({"alerts": [], "total_events": 0, "error": str(e)}), 503


@app.route('/api/response-distribution', methods=['POST'])
def response_distribution():
    """
    Response-Time-Verteilung in Buckets.

    Request: { "filters": {...} }
    Response: [{ "label": "0-100ms", "count": 100, "val": 0 }, ...]
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        filters = data.get('filters', {})

        es = get_es()
        query = build_query(filters)

        body = {
            'size': 0,
            'query': query,
            'aggs': {
                'rt_histogram': {
                    'histogram': {
                        'field': 'response_time_ms',
                        'interval': 200,
                        'min_doc_count': 1
                    }
                }
            }
        }

        result = es.search(index=INDEX, body=body)
        buckets = result['aggregations']['rt_histogram']['buckets']

        return jsonify([
            {
                'label': f"{int(b['key'])}-{int(b['key']) + 200}ms",
                'count': b['doc_count'],
                'val': int(b['key'])
            }
            for b in buckets
        ])
    except Exception as e:
        logger.exception("Fehler bei Response Distribution")
        return jsonify([])


# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    logger.info(f"Starte Backend Services auf Port {BACKEND_PORT}...")
    logger.info(f"  Elasticsearch: {ES_HOST}:{ES_PORT}")
    logger.info(f"  Index: {INDEX}")

    app.run(host='0.0.0.0', port=BACKEND_PORT, debug=DEBUG)
