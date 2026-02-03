#!/bin/bash
# Start the Top-Routes API Backend
# Muss auf einem Node des Clusters laufen (z.B. node1)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Python Virtual Environment aktivieren falls vorhanden
if [ -d "$SCRIPT_DIR/venv" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
fi

# Spark Home setzen (falls nicht gesetzt)
export SPARK_HOME="${SPARK_HOME:-/opt/spark}"
export PYSPARK_PYTHON=python3

# Flask App starten
cd "$SCRIPT_DIR"
python3 app.py
