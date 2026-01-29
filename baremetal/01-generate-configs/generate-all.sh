#!/bin/bash
#
# Generiert die Autoinstall Konfiguration (ein ISO für alle Nodes)
#
# Verwendung: ./generate-all.sh [SSH_PUBKEY_FILE]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSH_PUBKEY_FILE="${1:-$HOME/.ssh/id_rsa.pub}"

echo "=== Cloudkoffer Config Generator ==="
echo ""

# SSH Key prüfen
if [[ ! -f "$SSH_PUBKEY_FILE" ]]; then
    echo "FEHLER: SSH Public Key nicht gefunden: $SSH_PUBKEY_FILE"
    echo "Erstelle einen mit: ssh-keygen -t rsa -b 4096"
    exit 1
fi

SSH_PUBKEY=$(cat "$SSH_PUBKEY_FILE")
echo "SSH Key: ${SSH_PUBKEY:0:50}..."

# Passwort
echo ""
echo "Passwort für cloudadmin eingeben:"
read -s PASSWORD
PASSWORD_HASH=$(echo "$PASSWORD" | mkpasswd --method=SHA-512 --stdin)

# Verzeichnis erstellen
mkdir -p "$SCRIPT_DIR/autoinstall"

echo ""
echo "Generiere Autoinstall Konfiguration..."

# Generische user-data (Hostname wird später gesetzt)
cat > "$SCRIPT_DIR/autoinstall/user-data" << EOF
#cloud-config
autoinstall:
  version: 1
  locale: en_US.UTF-8
  keyboard:
    layout: us
  timezone: UTC
  
  identity:
    hostname: node
    username: cloudadmin
    password: '${PASSWORD_HASH}'
  
  ssh:
    install-server: true
    allow-pw: false
    authorized-keys:
      - ${SSH_PUBKEY}
  
  network:
    version: 2
    ethernets:
      enp0s31f6:
        dhcp4: true
      eno1:
        dhcp4: true
  
  storage:
    layout:
      name: direct
  
  # Nur minimale Pakete - Rest wird im Post-Install installiert
  packages:
    - openssh-server
  
  late-commands:
    - curtin in-target -- systemctl enable ssh
    # Data-Verzeichnisse
    - curtin in-target -- mkdir -p /data/solr /data/spark /data/zookeeper /data/prometheus
    - curtin in-target -- chown -R cloudadmin:cloudadmin /data
    # /etc/hosts mit cloud.local Domain
    - |
      cat >> /target/etc/hosts << HOSTS
      
      # Cloudkoffer Cluster (cloud.local)
      192.168.1.100 node0 node0.cloud.local
      192.168.1.101 node1 node1.cloud.local
      192.168.1.102 node2 node2.cloud.local
      192.168.1.103 node3 node3.cloud.local
      192.168.1.104 node4 node4.cloud.local
      HOSTS
    # DNS-Forwarding Konfiguration fuer node0
    - |
      cat > /target/etc/dnsmasq.d/cloud-local.conf << DNSCONF
      # Cloudkoffer DNS Forwarding
      domain=cloud.local
      local=/cloud.local/
      expand-hosts
      # Upstream DNS
      server=8.8.8.8
      server=8.8.4.4
      # Listen on all interfaces
      interface=*
      bind-interfaces
      DNSCONF
    # DNS auf node0 aktivieren (wird im Post-Install basierend auf IP aktiviert)
    - |
      cat > /target/etc/systemd/system/dnsmasq-setup.service << SVCFILE
      [Unit]
      Description=Setup dnsmasq on node0
      After=network-online.target
      Wants=network-online.target
      
      [Service]
      Type=oneshot
      ExecStart=/bin/bash -c 'IP=\$(hostname -I | awk "{print \\$1}"); if [ "\$IP" = "192.168.1.100" ]; then systemctl enable --now dnsmasq; else systemctl disable dnsmasq; fi'
      RemainAfterExit=yes
      
      [Install]
      WantedBy=multi-user.target
      SVCFILE
    - curtin in-target -- systemctl enable dnsmasq-setup.service
EOF

# meta-data
cat > "$SCRIPT_DIR/autoinstall/meta-data" << EOF
instance-id: cloud-local
EOF

echo ""
echo "=== Fertig! ==="
echo "Dateien in: $SCRIPT_DIR/autoinstall/"
echo ""
echo "Nodes: node0 (DNS-Server), node1-node4 (Worker)"
echo "Domain: cloud.local"
echo "Hinweis: Hostname wird im Post-Install basierend auf IP gesetzt."
