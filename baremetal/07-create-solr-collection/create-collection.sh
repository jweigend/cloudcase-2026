#!/bin/bash
#
# Erstellt eine Solr Collection
#
# Verwendung: ./create-collection.sh [COLLECTION_NAME]
#

set -e

COLLECTION="${1:-demo}"
SOLR_HOST="nuc1:8983"

echo "=== Solr Collection: $COLLECTION ==="
echo ""

# Prüfen ob Solr erreichbar
if ! curl -s --max-time 5 "http://$SOLR_HOST/solr/admin/info/system" | grep -q solr; then
    echo "FEHLER: Solr nicht erreichbar"
    exit 1
fi

echo "Collection erstellen..."
curl -s "http://$SOLR_HOST/solr/admin/collections?action=CREATE&name=$COLLECTION&numShards=4&replicationFactor=2&autoAddReplicas=true&collection.configName=_default"

echo ""
echo "Test-Dokument indexieren..."
curl -s -X POST "http://$SOLR_HOST/solr/$COLLECTION/update?commit=true" \
    -H "Content-Type: application/json" \
    -d '[{"id":"test-1","title":"Cloudkoffer Test"}]'

echo ""
echo "=== Fertig! ==="
echo "URL: http://$SOLR_HOST/solr/#/$COLLECTION/query"
