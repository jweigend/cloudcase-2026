#!/bin/bash
#
# Wendet Cloud-Init Konfiguration per SSH an (idempotent)
#
# Verwendung: ./apply-cloud-init.sh <IP_ODER_HOSTNAME>
# Beispiel:   ./apply-cloud-init.sh 192.168.1.100
#
# Nutzt "cloud-init single" für idempotente Ausführung einzelner Module.
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
    echo "  $0 node0"
    echo ""
    echo "IP-Mapping:"
    echo "  192.168.1.100 → node0 (DNS/Monitoring)"
    echo "  192.168.1.101 → node1 (ZK, Solr, Spark-Master)"
    echo "  192.168.1.102 → node2 (ZK, Solr, Spark-Worker)"
    echo "  192.168.1.103 → node3 (ZK, Solr, Spark-Worker)"
    echo "  192.168.1.104 → node4 (Solr, Spark-Worker)"
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
echo "[1/5] Hostname setzen..."
ssh "${USERNAME}@${TARGET}" "sudo hostnamectl set-hostname $NODE_NAME"

# DNS prüfen und ggf. temporär fixen
echo "[2/5] DNS prüfen..."
ssh "${USERNAME}@${TARGET}" '
    # Teste ob DNS funktioniert
    if ! host archive.ubuntu.com >/dev/null 2>&1; then
        echo "      DNS nicht erreichbar - setze temporär 8.8.8.8"
        # Backup original resolv.conf
        sudo cp /etc/resolv.conf /etc/resolv.conf.backup 2>/dev/null || true
        # Temporär Google DNS setzen
        echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf > /dev/null
    else
        echo "      DNS funktioniert"
    fi
'

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

# DNS-Server (node0)
if [[ "$NODE_NAME" == "node0" ]]; then
    CLOUD_INIT_FILES+=("$SCRIPT_DIR/cloud-init/dns-server.yaml")
fi

# Prometheus + Grafana (node0)
if [[ "$NODE_NAME" == "node0" ]]; then
    CLOUD_INIT_FILES+=("$BASE_DIR/08-install-monitoring/cloud-init-prometheus.yaml")
fi

# Node Exporter (alle Nodes)
CLOUD_INIT_FILES+=("$BASE_DIR/08-install-monitoring/cloud-init-exporter.yaml")

echo "[3/5] Cloud-Init Dateien für $NODE_NAME:"
for f in "${CLOUD_INIT_FILES[@]}"; do
    if [[ -f "$f" ]]; then
        echo "      ✓ $(basename "$f")"
    else
        echo "      ✗ $(basename "$f") (FEHLT!)"
    fi
done
echo ""

# Dateien einzeln kopieren und ausführen
echo "[4/5] Cloud-Init Module ausführen..."

# Erst NoCloud Datasource setzen (einmalig)
ssh "${USERNAME}@${TARGET}" "
    sudo mkdir -p /etc/cloud/cloud.cfg.d
    echo 'datasource_list: [ NoCloud, None ]' | sudo tee /etc/cloud/cloud.cfg.d/99-datasource.cfg > /dev/null
"

# Jede Datei einzeln verarbeiten
for f in "${CLOUD_INIT_FILES[@]}"; do
    if [[ ! -f "$f" ]]; then
        echo "  SKIP: $(basename "$f") (nicht gefunden)"
        continue
    fi
    
    BASENAME=$(basename "$f")
    echo "  → $BASENAME"
    
    # Datei kopieren
    scp -q "$f" "${USERNAME}@${TARGET}:/tmp/cloud-config.yaml"
    
    # Cloud-Init single Module ausführen
    ssh "${USERNAME}@${TARGET}" "
        # Config als aktive Datei setzen
        sudo cp /tmp/cloud-config.yaml /etc/cloud/cloud.cfg.d/99-current.cfg
        
        # Module einzeln ausführen (idempotent mit --frequency=always)
        sudo cloud-init single --name write_files --frequency always 2>/dev/null || true
        sudo cloud-init single --name package_update_upgrade_install --frequency always 2>/dev/null || true
        sudo cloud-init single --name runcmd --frequency always 2>/dev/null || true
        
        # Aufräumen
        sudo rm -f /etc/cloud/cloud.cfg.d/99-current.cfg
    "
done

# Aufräumen auf Remote
ssh "${USERNAME}@${TARGET}" "rm -f /tmp/cloud-config.yaml"

echo ""
echo "[5/5] Services prüfen..."

# Für node0: DNS auf dnsmasq umstellen (jetzt wo es installiert ist)
if [[ "$NODE_NAME" == "node0" ]]; then
    ssh "${USERNAME}@${TARGET}" '
        # Warte bis dnsmasq läuft
        if systemctl is-active dnsmasq >/dev/null 2>&1; then
            echo "      DNS auf dnsmasq umstellen..."
            echo -e "nameserver 127.0.0.1\nnameserver 8.8.8.8\nsearch cloud.local" | sudo tee /etc/resolv.conf > /dev/null
        fi
    '
fi

# Services Status ausgeben
ssh "${USERNAME}@${TARGET}" '
    echo ""
    echo "=== Service Status ==="
    
    for svc in dnsmasq prometheus grafana-server zookeeper solr spark-master spark-worker node_exporter; do
        if systemctl is-enabled "$svc" 2>/dev/null | grep -q enabled; then
            printf "  %-16s %s\n" "$svc:" "$(systemctl is-active $svc)"
        fi
    done
'

echo ""
echo "=== Fertig: $NODE_NAME ($IP) ==="
