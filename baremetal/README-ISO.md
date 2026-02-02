# Cloudkoffer ISO - Ein Image für alle Nodes

## Übersicht

Das Cloudkoffer-Projekt verwendet **ein einziges ISO-Image** für alle 5 NUCs. Die Unterscheidung der Nodes erfolgt über die MAC-Adresse → IP-Zuweisung → Rollenauswahl.

## Architektur

```
┌─────────────────────────────────────────────────────────────────┐
│                     CLOUDKOFFER.ISO                             │
│              (ein USB-Stick für alle NUCs)                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │            AUTOINSTALL                   │
        │  • Ubuntu 24.04 LTS                     │
        │  • User: cloudadmin (SSH-Key Auth)      │
        │  • NOPASSWD sudo                        │
        │  • Generischer Hostname: "node"         │
        │  • DHCP für Netzwerk                    │
        └─────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
    ┌──────────┐        ┌──────────┐        ┌──────────┐
    │  NUC 1   │        │  NUC 2   │        │  NUC 3   │
    │ MAC: ... │        │ MAC: ... │        │ MAC: ... │
    └──────────┘        └──────────┘        └──────────┘
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                      EDGEROUTER X                               │
│                   (Statisches DHCP)                             │
│                                                                 │
│   MAC 94:c6:91:a7:a1:fb  →  192.168.1.100  (node0)             │
│   MAC xx:xx:xx:xx:xx:xx  →  192.168.1.101  (node1)             │
│   MAC xx:xx:xx:xx:xx:xx  →  192.168.1.102  (node2)             │
│   MAC xx:xx:xx:xx:xx:xx  →  192.168.1.103  (node3)             │
│   MAC xx:xx:xx:xx:xx:xx  →  192.168.1.104  (node4)             │
└─────────────────────────────────────────────────────────────────┘
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                    POST-INSTALL                                 │
│              ./apply-cloud-init.sh <IP>                         │
│                                                                 │
│   IP → Hostname → Rolle → Cloud-Init Dateien                   │
│                                                                 │
│   192.168.1.100 → node0 → Spark-Master, Prometheus, Grafana, DNS  │
│   192.168.1.101 → node1 → ZooKeeper, Solr, Spark-Worker, DNS      │
│   192.168.1.102 → node2 → ZooKeeper, Solr, Spark-Worker, DNS      │
│   192.168.1.103 → node3 → ZooKeeper, Solr, Spark-Worker, DNS      │
│   192.168.1.104 → node4 → Solr, Spark-Worker, DNS                 │
└─────────────────────────────────────────────────────────────────┘
```

## Warum ein ISO für alle?

| Aspekt | Vorteil |
|--------|---------|
| **Einfachheit** | Nur ein USB-Stick nötig |
| **Konsistenz** | Alle Nodes haben identische Basis |
| **Wartbarkeit** | Änderungen nur an einer Stelle |
| **Flexibilität** | Rollen werden erst im Post-Install zugewiesen |

## Ablauf: Node installieren

### 1. Vorbereitung (einmalig)

```bash
# EdgeRouter konfigurieren (MAC → IP Mapping)
cd baremetal/00-edgerouter-config
./configure-edgerouter.sh

# Autoinstall generieren
cd baremetal/01-generate-configs
./generate-all.sh

# ISO erstellen
cd baremetal/02-create-iso
./create-iso.sh

# USB-Stick schreiben
cd baremetal/03-write-usb
./write-usb.sh /dev/sdX
```

### 2. Installation (pro Node)

```bash
# 1. NUC von USB booten
#    → Installation läuft vollautomatisch (~10 Minuten)
#    → NUC startet neu

# 2. Post-Install ausführen (von deinem Rechner)
cd baremetal/04-post-install
./apply-cloud-init.sh 192.168.1.10X   # X = 0-4
```

### 3. Alle Nodes installieren

```bash
# Sequentiell (ein USB-Stick)
for ip in 100 101 102 103 104; do
  echo "Warte auf Node mit IP 192.168.1.$ip..."
  until ping -c 1 192.168.1.$ip &>/dev/null; do sleep 5; done
  ./apply-cloud-init.sh 192.168.1.$ip
done

# Parallel (wenn 5 USB-Sticks vorhanden)
# Alle NUCs gleichzeitig booten, dann Post-Install
```

## Wie die Identifikation funktioniert

### Schritt 1: MAC-Adresse → IP (EdgeRouter)

Der EdgeRouter hat statische DHCP-Mappings:

```
set service dhcp-server shared-network-name LAN subnet 192.168.1.0/24 static-mapping node0 ip-address 192.168.1.100
set service dhcp-server shared-network-name LAN subnet 192.168.1.0/24 static-mapping node0 mac-address 94:c6:91:a7:a1:fb
```

**Vorteil:** Die MAC-Adresse ist fest in der Hardware. Egal wie oft neu installiert wird, der Node bekommt immer dieselbe IP.

### Schritt 2: IP → Hostname (Post-Install)

Das `apply-cloud-init.sh` Skript ermittelt die IP und setzt den Hostname:

```bash
IP=$(ssh cloudadmin@$TARGET "ip -4 addr show | grep 'inet 192.168.1' | awk '{print \$2}' | cut -d/ -f1")

case "$IP" in
    192.168.1.100) NODE_NAME="node0" ;;
    192.168.1.101) NODE_NAME="node1" ;;
    ...
esac

ssh cloudadmin@$TARGET "sudo hostnamectl set-hostname $NODE_NAME"
```

### Schritt 3: Hostname → Rolle (Cloud-Init Auswahl)

Basierend auf dem Node-Namen werden unterschiedliche Cloud-Init Dateien angewendet:

```bash
# node0 → DNS + Monitoring
if [[ "$NODE_NAME" == "node0" ]]; then
    CLOUD_INIT_FILES+=("cloud-init/dns-server.yaml")
    CLOUD_INIT_FILES+=("cloud-init-prometheus.yaml")
fi

# node1-3 → ZooKeeper
if [[ "$NODE_NAME" =~ ^node[1-3]$ ]]; then
    CLOUD_INIT_FILES+=("cloud-init-zookeeper.yaml")
fi

# node1-4 → Solr
if [[ "$NODE_NAME" =~ ^node[1-4]$ ]]; then
    CLOUD_INIT_FILES+=("cloud-init-solr.yaml")
fi
```

## ISO-Inhalt

Das ISO enthält:

```
cloudkoffer.iso
├── Ubuntu 24.04 LTS Server
├── autoinstall/
│   ├── user-data          # Autoinstall Konfiguration
│   └── meta-data          # Cloud-Init Metadaten
└── boot/grub/grub.cfg     # Autoinstall aktiviert
```

### user-data (Autoinstall)

```yaml
#cloud-config
autoinstall:
  version: 1
  locale: en_US.UTF-8
  keyboard:
    layout: us
  timezone: UTC
  
  identity:
    hostname: node                    # Generisch!
    username: cloudadmin
    password: '<hash>'
  
  ssh:
    install-server: true
    allow-pw: false
    authorized-keys:
      - ssh-rsa AAAA...               # Dein SSH-Key
  
  network:
    version: 2
    ethernets:
      eno1:
        dhcp4: true                   # IP vom Router
  
  late-commands:
    # NOPASSWD für automatisiertes Post-Install
    - echo 'cloudadmin ALL=(ALL) NOPASSWD:ALL' > /target/etc/sudoers.d/cloudadmin
    
    # DNS auf node0 setzen
    - echo 'nameserver 192.168.1.100' > /target/etc/resolv.conf
    
    # /etc/hosts vorbereiten
    - |
      cat >> /target/etc/hosts << EOF
      192.168.1.100 node0 node0.cloud.local
      192.168.1.101 node1 node1.cloud.local
      ...
      EOF
```

## Idempotenz

Das Post-Install ist idempotent - es kann mehrfach ausgeführt werden:

```bash
# Erstes Mal: Installiert alles
./apply-cloud-init.sh 192.168.1.100

# Zweites Mal: Erkennt "already installed", nur Config-Updates
./apply-cloud-init.sh 192.168.1.100
```

**So funktioniert's:**

| Modul | Verhalten |
|-------|-----------|
| `write_files` | Überschreibt → Config-Änderungen möglich |
| `packages` | Installiert nur wenn fehlt |
| `runcmd` | Mit `if [ ! -f ... ]` Guards |

## Troubleshooting

### Node bekommt falsche IP

**Problem:** NUC bekommt nicht die erwartete IP

**Lösung:**
1. MAC-Adresse prüfen: `ip link show eno1`
2. EdgeRouter Mapping prüfen/aktualisieren
3. DHCP-Lease erneuern: `sudo dhclient -r && sudo dhclient`

### Post-Install schlägt fehl

**Problem:** SSH-Verbindung nicht möglich

**Lösung:**
1. Node erreichbar? `ping 192.168.1.10X`
2. SSH-Key vorhanden? `ssh-add -l`
3. Host-Key geändert? `ssh-keygen -R 192.168.1.10X`

### Node hat falschen Hostname

**Problem:** Hostname ist noch "node" statt "node0"

**Lösung:** Post-Install erneut ausführen:
```bash
./apply-cloud-init.sh 192.168.1.100
```

## Dateien

```
baremetal/
├── 00-edgerouter-config/     # Router Konfiguration
├── 01-generate-configs/      # Autoinstall Generator
│   ├── generate-all.sh
│   └── autoinstall/
│       ├── user-data
│       └── meta-data
├── 02-create-iso/            # ISO Builder
│   ├── create-iso.sh
│   └── output/
│       └── cloudkoffer.iso   # Das fertige ISO
├── 03-write-usb/             # USB Schreiber
│   └── write-usb.sh
└── 04-post-install/          # Rollen-Zuweisung
    ├── apply-cloud-init.sh
    └── cloud-init/
        ├── base.yaml
        └── dns-server.yaml
```
