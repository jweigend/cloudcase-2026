#!/bin/bash
#
# Cluster-weite Smoke Tests
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

echo "=== Cloudkoffer Smoke Tests ==="
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

echo "ZooKeeper:"
for node in node1 node2 node3; do
    check "$node ruok" "echo ruok | nc -w 2 ${NODES[$node]} 2181 | grep -q imok"
done
echo ""

echo "Solr Cloud:"
for node in node1 node2 node3 node4; do
    check "$node Solr" "curl -s --max-time 5 http://${NODES[$node]}:8983/solr/admin/info/system | grep -q solr"
done
echo ""

echo "Spark:"
check "node1 Master" "curl -s --max-time 5 http://${NODES[node1]}:8081 | grep -q Spark"
for node in node2 node3 node4; do
    check "$node Worker" "curl -s --max-time 5 http://${NODES[$node]}:8081 | grep -q Spark"
done
echo ""

echo "Monitoring:"
check "Prometheus" "curl -s --max-time 5 http://${NODES[node0]}:9090/-/ready"
check "Grafana" "curl -s --max-time 5 http://${NODES[node0]}:3000/api/health | grep -q ok"
for node in node0 node1 node2 node3 node4; do
    check "$node Node Exporter" "curl -s --max-time 5 http://${NODES[$node]}:9100/metrics | grep -q node_cpu"
done
echo ""

echo "========================================="
echo -e "Ergebnis: ${GREEN}$PASS bestanden${NC}, ${RED}$FAIL fehlgeschlagen${NC}"
echo "========================================="

[[ $FAIL -eq 0 ]]
