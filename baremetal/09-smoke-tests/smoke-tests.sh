#!/bin/bash
#
# Cluster-weite Smoke Tests
#

set -e

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

echo "Netzwerk:"
for node in node0 node1 node2 node3 node4; do
    check "$node erreichbar" "ping -c 1 -W 2 $node.cloud.local"
done
echo ""

echo "ZooKeeper:"
for node in node1 node2 node3; do
    check "$node ruok" "echo ruok | nc -w 2 $node.cloud.local 2181 | grep -q imok"
done
echo ""

echo "Solr Cloud:"
for node in node1 node2 node3 node4; do
    check "$node Solr" "curl -s --max-time 5 http://$node.cloud.local:8983/solr/admin/info/system | grep -q solr"
done
echo ""

echo "Spark:"
check "node1 Master" "curl -s --max-time 5 http://node1.cloud.local:8080 | grep -q Spark"
for node in node2 node3 node4; do
    check "$node Worker" "curl -s --max-time 5 http://$node.cloud.local:8081 | grep -q Spark"
done
echo ""

echo "Monitoring:"
check "Prometheus" "curl -s --max-time 5 http://node0.cloud.local:9090/-/ready"
check "Grafana" "curl -s --max-time 5 http://node0.cloud.local:3000/api/health | grep -q ok"
for node in node0 node1 node2 node3 node4; do
    check "$node Node Exporter" "curl -s --max-time 5 http://$node.cloud.local:9100/metrics | grep -q node_cpu"
done
echo ""

echo "========================================="
echo -e "Ergebnis: ${GREEN}$PASS bestanden${NC}, ${RED}$FAIL fehlgeschlagen${NC}"
echo "========================================="

[[ $FAIL -eq 0 ]]
