# Baremetal Setup - Cloudkoffer

Automatisierte Installation für 5 Intel NUCs mit Ubuntu, ZooKeeper, Solr Cloud, Spark und Monitoring.

## Übersicht

```
┌─────────────────┐     ┌─────────────────┐
│  Ein ISO für    │────▶│  Alle 5 NUCs    │
│  alle Nodes     │     │  booten davon   │
└─────────────────┘     └─────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────┐
│ Post-Install (per SSH von Workstation):     │
│                                             │
│  1. IP ermitteln (DHCP mit MAC-Binding)     │
│  2. Hostname setzen (nuc1-nuc5)             │
│  3. Cloud-Init Configs anwenden             │
└─────────────────────────────────────────────┘
```

## IP-Zuweisung

Die IPs werden per DHCP über MAC-Binding im Router vergeben:

| Node | IP | Services |
|------|-----|----------|
| node0 | 192.168.1.100 | DNS (dnsmasq), Prometheus, Grafana |
| node1 | 192.168.1.101 | ZooKeeper, Solr, Spark Master |
| node2 | 192.168.1.102 | ZooKeeper, Solr, Spark Worker |
| node3 | 192.168.1.103 | ZooKeeper, Solr, Spark Worker |
| node4 | 192.168.1.104 | Solr, Spark Worker |

## Quick Start

### 1. Konfiguration generieren

```bash
cd 01-generate-configs
./generate-all.sh
```

### 2. ISO erstellen

```bash
cd 02-create-iso
./create-iso.sh
# Erzeugt: output/cloudkoffer.iso
```

### 3. USB-Stick schreiben

```bash
cd 03-write-usb
./write-usb.sh /dev/sdX
# USB-Stick funktioniert für alle 5 NUCs
```

### 4. NUCs installieren

1. USB-Stick einstecken
2. Von USB booten
3. Automatische Installation läuft (~10 min)
4. Nach Reboot per SSH erreichbar
5. **Gleichen USB-Stick für nächsten NUC verwenden**

### 5. Post-Install (pro Node)

```bash
cd 04-post-install

# Mit der vom DHCP vergebenen IP:
./apply-cloud-init.sh 192.168.1.100
./apply-cloud-init.sh 192.168.1.101
./apply-cloud-init.sh 192.168.1.102
./apply-cloud-init.sh 192.168.1.103
./apply-cloud-init.sh 192.168.1.104

# Oder mit temporärem Hostnamen:
./apply-cloud-init.sh node
```

Das Skript:
- Ermittelt die IP automatisch
- Setzt den Hostnamen (node0-node4)
- Wendet die passenden Cloud-Init Configs an

### 6. Smoke Tests

```bash
cd 09-smoke-tests
./smoke-tests.sh
```

### 7. Solr Collection erstellen

```bash
cd 10-create-solr-collection
./create-collection.sh documents
```

## Verzeichnisstruktur

```
baremetal/
├── 00-edgerouter-config/ # EdgeRouter X Konfiguration
├── 01-generate-configs/  # Generiert Autoinstall user-data
├── 02-create-iso/        # Erstellt bootbares Ubuntu ISO
├── 03-write-usb/         # Schreibt ISO auf USB-Stick
├── 04-post-install/      # Setzt Hostname, wendet Cloud-Init an
│   └── cloud-init/       # Basis-Konfiguration (alle Nodes)
├── 05-install-zookeeper/ # ZooKeeper Cloud-Init
├── 06-install-solr/      # Solr Cloud-Init
├── 07-install-spark/     # Spark Master/Worker Cloud-Init
├── 08-install-monitoring/# Prometheus/Grafana/Exporter Cloud-Init
├── 09-smoke-tests/       # Funktionalitätstests
└── 10-create-solr-collection/ # Solr Collection anlegen
```

## Voraussetzungen

- Ubuntu Base-ISO (ubuntu-24.04-live-server-amd64.iso)
- 8GB+ USB-Stick
- Router mit MAC-Binding konfiguriert

## Credentials

- **SSH User:** `cloudadmin`
- **Grafana:** admin / admin (Änderung beim ersten Login)
