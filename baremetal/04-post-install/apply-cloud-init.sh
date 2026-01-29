#!/bin/bash
#
# Setzt Hostname und wendet Cloud-Init Konfiguration an
#
# Verwendung: ./apply-cloud-init.sh <IP_ODER_HOSTNAME>
# Beispiel:   ./apply-cloud-init.sh 192.168.0.100
#            ./apply-cloud-init.sh cloudkoffer-node
#
# Das Skript ermittelt den Node-Namen basierend auf der IP und
# wendet die passenden Cloud-Init Dateien an.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(dirname "$SCRIPT_DIR")"
USERNAME="cloudadmin"

TARGET="${1:-}"

if [[ -z "$TARGET" ]]; then
    echo "Verwendung: $0 <IP_ODER_HOSTNAME>"
    echo ""
    echo "Beispiele:"
    echo "  $0 192.168.1.100"
    echo "  $0 node   (wenn per DHCP erreichbar)"
    echo ""
    echo "IP-Mapping:"
    echo "  192.168.1.100 → node0 (DNS-Server)"
    echo "  192.168.1.101 → node1"
    echo "  192.168.1.102 → node2"
    echo "  192.168.1.103 → node3"
    echo "  192.168.1.104 → node4"
    exit 1
fi

echo "=== Cloud-Init Post-Install ==="
echo ""

# Prüfen ob erreichbar
if ! ping -c 1 -W 2 "$TARGET" &>/dev/null; then
    echo "FEHLER: $TARGET nicht erreichbar"
    exit 1
fi

# IP ermitteln
IP=$(ssh -o StrictHostKeyChecking=accept-new "${USERNAME}@${TARGET}" \
    "ip -4 addr show | grep 'inet 192.168.1' | awk '{print \$2}' | cut -d/ -f1" 2>/dev/null)

echo "Ermittelte IP: $IP"

# Node-Name basierend auf IP
case "$IP" in
    192.168.1.100) NODE_NAME="node0" ;;
    192.168.1.101) NODE_NAME="node1" ;;
    192.168.1.102) NODE_NAME="node2" ;;
    192.168.1.103) NODE_NAME="node3" ;;
    192.168.1.104) NODE_NAME="node4" ;;
    *)
        echo "FEHLER: Unbekannte IP $IP"
        echo "Erwartet: 192.168.1.100 - 192.168.1.104"
        exit 1
        ;;
esac

echo "Node-Name: $NODE_NAME"
echo ""

# Hostname setzen
echo "[1/3] Hostname setzen..."
ssh "${USERNAME}@${TARGET}" "sudo hostnamectl set-hostname $NODE_NAME"

# Cloud-Init Dateien ermitteln
CLOUD_INIT_FILES=()

# Basis für alle
CLOUD_INIT_FILES+=("$SCRIPT_DIR/cloud-init/base.yaml")

# ZooKeeper (node1-3)
if [[ "$NODE_NAME" =~ ^node[1-3]$ ]]; then
    CLOUD_INIT_FILES+=("$BASE_DIR/05-install-zookeeper/cloud-init.yaml")
fi

# Solr (node1-4)
if [[ "$NODE_NAME" =~ ^node[1-4]$ ]]; then
    CLOUD_INIT_FILES+=("$BASE_DIR/06-install-solr/cloud-init.yaml")
fi

# Spark Master (node1)
if [[ "$NODE_NAME" == "node1" ]]; then
    CLOUD_INIT_FILES+=("$BASE_DIR/07-install-spark/cloud-init-master.yaml")
fi

# Spark Worker (node2-4)
if [[ "$NODE_NAME" =~ ^node[2-4]$ ]]; then
    CLOUD_INIT_FILES+=("$BASE_DIR/07-install-spark/cloud-init-worker.yaml")
fi

# Monitoring (node0)
if [[ "$NODE_NAME" == "node0" ]]; then
    CLOUD_INIT_FILES+=("$BASE_DIR/08-install-monitoring/cloud-init-prometheus.yaml")
fi

# Node Exporter (NUC2-5)
if [[ "$NODE_NAME" != "nuc1" ]]; then
    CLOUD_INIT_FILES+=("$BASE_DIR/08-install-monitoring/cloud-init-exporter.yaml")
fi

echo "[2/3] Cloud-Init Dateien für $NODE_NAME:"
for f in "${CLOUD_INIT_FILES[@]}"; do
    echo "      - $(basename "$f")"
done
echo ""

# Dateien kopieren
ssh "${USERNAME}@${TARGET}" "sudo mkdir -p /etc/cloud/cloud.cfg.d"

for f in "${CLOUD_INIT_FILES[@]}"; do
    if [[ -f "$f" ]]; then
        BASENAME=$(basename "$f")
        scp -q "$f" "${USERNAME}@${TARGET}:/tmp/${BASENAME}"
        ssh "${USERNAME}@${TARGET}" "sudo mv /tmp/${BASENAME} /etc/cloud/cloud.cfg.d/"
    fi
done

# Cloud-Init ausführen
echo "[3/3] Cloud-Init ausführen..."
ssh "${USERNAME}@${TARGET}" "sudo cloud-init clean && sudo cloud-init init && sudo cloud-init modules --mode=config && sudo cloud-init modules --mode=final"

echo ""
echo "=== Fertig: $NODE_NAME ($IP) ==="
echo ""
echo "Services aktiviert (starten mit systemctl start):"
[[ "$NODE_NAME" =~ ^nuc[1-3]$ ]] && echo "  - zookeeper"
echo "  - solr"
[[ "$NODE_NAME" == "nuc2" ]] && echo "  - spark-master"
[[ "$NODE_NAME" =~ ^nuc[3-5]$ ]] && echo "  - spark-worker"
[[ "$NODE_NAME" == "nuc1" ]] && echo "  - prometheus, grafana-server"
echo "  - node_exporter"
