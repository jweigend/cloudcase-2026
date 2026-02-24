#!/bin/bash
# EdgeRouter X Konfiguration für Cloudkoffer
# eth0-eth3: LAN (192.168.1.x) mit DHCP
# eth4: WAN (DHCP vom ISP)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EDGEROUTER_IP="192.168.1.1"
EDGEROUTER_USER="ubnt"
CONFIG_SCRIPT="${SCRIPT_DIR}/edgerouter-config.script"

echo "=== EdgeRouter X Konfiguration ==="
echo ""
echo "Zielkonfiguration:"
echo "  - LAN (eth0-eth3): 192.168.1.1/24 (Switch)"
echo "  - DHCP-Bereich:    192.168.1.110 - 192.168.1.254"
echo "  - WAN (eth4):      DHCP vom ISP"
echo "  - DNS:             8.8.8.8, 8.8.4.4, 1.1.1.1"
echo ""
echo "Verbinde mit ${EDGEROUTER_USER}@${EDGEROUTER_IP}..."
echo "Standard-Passwort ist: ubnt"
echo ""

# Skript auf EdgeRouter kopieren
scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${CONFIG_SCRIPT}" "${EDGEROUTER_USER}@${EDGEROUTER_IP}:/tmp/config.script"

# Skript ausführen
ssh -t -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "${EDGEROUTER_USER}@${EDGEROUTER_IP}" \
    "chmod +x /tmp/config.script && /bin/vbash /tmp/config.script && rm /tmp/config.script"

echo ""
echo "=== Konfiguration abgeschlossen ==="
echo ""
echo "Der EdgeRouter ist jetzt wie folgt konfiguriert:"
echo "  - LAN (eth0-eth3): 192.168.1.1/24"
echo "  - DHCP-Bereich:    192.168.1.110 - 192.168.1.254"
echo "  - WAN (eth4):      DHCP vom ISP"
echo "  - DNS:             8.8.8.8, 8.8.4.4, 1.1.1.1"
echo ""
echo "WICHTIG: Deine Workstation wird beim nächsten DHCP-Request"
echo "eine neue IP im Bereich 192.168.1.110+ erhalten."
