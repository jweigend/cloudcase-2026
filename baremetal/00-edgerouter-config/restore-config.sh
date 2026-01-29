#!/bin/bash
#
# Stellt die EdgeRouter-Konfiguration wieder her
#
# Verwendung: ./restore-config.sh [ROUTER_IP]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROUTER_IP="${1:-192.168.1.1}"
ROUTER_USER="ubnt"
CONFIG_FILE="${SCRIPT_DIR}/config.boot.current"

echo "=== EdgeRouter Restore ==="
echo ""

if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "FEHLER: Konfigurationsdatei nicht gefunden: $CONFIG_FILE"
    exit 1
fi

echo "Konfiguration: $CONFIG_FILE"
echo "Router:        ${ROUTER_USER}@${ROUTER_IP}"
echo ""
echo "WARNUNG: Dies überschreibt die aktuelle Router-Konfiguration!"
echo ""
read -p "Fortfahren? (j/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Jj]$ ]]; then
    echo "Abgebrochen."
    exit 0
fi

echo ""
echo "[1/3] Konfiguration auf Router kopieren..."
scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$CONFIG_FILE" "${ROUTER_USER}@${ROUTER_IP}:/tmp/config.boot.restore"

echo "[2/3] Konfiguration anwenden..."
ssh -t -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${ROUTER_USER}@${ROUTER_IP}" << 'EOF'
# Backup der aktuellen Konfiguration
sudo cp /config/config.boot /config/config.boot.backup.$(date +%Y%m%d_%H%M%S)

# Neue Konfiguration kopieren
sudo cp /tmp/config.boot.restore /config/config.boot
rm /tmp/config.boot.restore

echo ""
echo "Konfiguration wurde kopiert."
echo "Backup erstellt unter: /config/config.boot.backup.*"
EOF

echo ""
echo "[3/3] Router neu starten..."
read -p "Router jetzt neustarten? (j/N) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Jj]$ ]]; then
    ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        "${ROUTER_USER}@${ROUTER_IP}" "sudo reboot" || true
    echo ""
    echo "Router startet neu. Warte ca. 60 Sekunden..."
else
    echo ""
    echo "Konfiguration gespeichert. Router manuell neustarten mit:"
    echo "  ssh ${ROUTER_USER}@${ROUTER_IP} 'sudo reboot'"
fi

echo ""
echo "=== Fertig ==="
