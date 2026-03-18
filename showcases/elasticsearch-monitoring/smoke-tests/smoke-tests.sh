#!/bin/bash
#
# Smoke Tests fuer Elasticsearch-Monitoring Showcase
#

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0

check() {
    local name="$1"
    local cmd="$2"

    if eval "$cmd" &>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $name"
        ((PASS++))
    else
        echo -e "  ${RED}✗${NC} $name"
        ((FAIL++))
    fi
}

echo "=== Cloudkoffer Smoke Tests (Elasticsearch-Monitoring) ==="
echo ""

# Node IPs
declare -A NODES=(
    [node0]="192.168.1.100"
    [node1]="192.168.1.101"
    [node2]="192.168.1.102"
    [node3]="192.168.1.103"
    [node4]="192.168.1.104"
)

echo "Netzwerk:"
for node in node0 node1 node2 node3 node4; do
    check "$node erreichbar" "ping -c 1 -W 2 ${NODES[$node]}"
done
echo ""

echo "Elasticsearch Cluster:"
for node in node1 node2 node3 node4; do
    check "$node HTTP" "curl -sf --max-time 5 http://${NODES[$node]}:9200 | grep -q cluster_name"
done
echo ""

echo "Elasticsearch Cluster Health:"
check "Cluster Status green/yellow" \
    "curl -sf --max-time 5 'http://${NODES[node1]}:9200/_cluster/health' | grep -qE '\"status\":\"(green|yellow)\"'"
check "4 Nodes im Cluster" \
    "curl -sf --max-time 5 'http://${NODES[node1]}:9200/_cluster/health' | grep -q '\"number_of_nodes\":4'"
echo ""

echo "elasticsearch_exporter:"
check "node1 Exporter" "curl -sf --max-time 5 http://${NODES[node1]}:9114/metrics | grep -q elasticsearch"
echo ""

echo "JupyterLab:"
check "node0 JupyterLab" "curl -sf --max-time 5 http://${NODES[node0]}:8888/api/status | grep -q started"
echo ""

echo "Webapp:"
check "node0 Backend Health" "curl -sf --max-time 5 http://${NODES[node0]}:5001/api/health | grep -q ok"
check "node0 Frontend (nginx)" "curl -sf --max-time 5 http://${NODES[node0]}:80/health"
echo ""

echo "Monitoring:"
check "Prometheus" "curl -sf --max-time 5 http://${NODES[node0]}:9090/-/ready"
check "Grafana" "curl -sf --max-time 5 http://${NODES[node0]}:3000/api/health | grep -q ok"
for node in node0 node1 node2 node3 node4; do
    check "$node Node Exporter" "curl -sf --max-time 5 http://${NODES[$node]}:9100/metrics | grep -q node_cpu"
done
echo ""

echo "========================================="
echo -e "Ergebnis: ${GREEN}$PASS bestanden${NC}, ${RED}$FAIL fehlgeschlagen${NC}"
echo "========================================="

[[ $FAIL -eq 0 ]]
