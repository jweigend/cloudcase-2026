#!/bin/bash
# Start the Top-Routes API Backend
# Lokales Startskript für Entwicklung - Umgebungsvariablen werden hier gesetzt
# Auf dem Cluster werden diese via systemd Service gesetzt (siehe Ansible)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Python Virtual Environment aktivieren falls vorhanden
if [ -d "$SCRIPT_DIR/venv" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
fi

# ============================================================
# Lokale Entwicklungs-Konfiguration
# Auf dem Cluster werden diese Werte via Ansible/systemd gesetzt
# ============================================================
export SPARK_MASTER="${SPARK_MASTER:-spark://node0.cloud.local:7077}"
export SPARK_HOME="${SPARK_HOME:-/opt/spark}"
export SOLR_HOST="${SOLR_HOST:-node1.cloud.local}"
export SOLR_PORT="${SOLR_PORT:-8983}"
export BACKEND_PORT="${BACKEND_PORT:-5001}"
export DEBUG="${DEBUG:-true}"

export PYSPARK_PYTHON=python3

echo "Starting Backend with:"
echo "  SPARK_MASTER: $SPARK_MASTER"
echo "  SOLR_HOST:    $SOLR_HOST:$SOLR_PORT"
echo "  BACKEND_PORT: $BACKEND_PORT"
echo "  DEBUG:        $DEBUG"
echo ""

# Flask App starten
cd "$SCRIPT_DIR"
python3 backend_services.py
