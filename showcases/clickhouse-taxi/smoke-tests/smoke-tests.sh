#!/bin/bash
#
# Smoke Tests fuer ClickHouse-Taxi Showcase
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

echo "=== Cloudkoffer Smoke Tests (ClickHouse-Taxi) ==="
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

echo "ClickHouse Keeper:"
for node in node1 node2 node3; do
    check "$node ruok" "echo ruok | nc -w 2 ${NODES[$node]} 9181 | grep -q imok"
done
echo ""

echo "ClickHouse Server:"
for node in node1 node2 node3 node4; do
    check "$node HTTP" "curl -sf --max-time 5 http://${NODES[$node]}:8123/ping | grep -q Ok"
done
echo ""

echo "ClickHouse Cluster:"
check "Cluster-Konnektivitaet (4 Replicas)" \
    "curl -sf --max-time 5 'http://${NODES[node1]}:8123/?query=SELECT+count()+FROM+system.clusters+WHERE+cluster=%27cloudkoffer%27' | grep -q 4"
echo ""

echo "ClickHouse Metriken:"
for node in node1 node2 node3 node4; do
    check "$node Prometheus" "curl -sf --max-time 5 http://${NODES[$node]}:9363/metrics | grep -q clickhouse"
done
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
