# Cloudkoffer 2026

Ein portabler Big Data Cluster auf 5 Intel NUCs für Demos, Workshops und Entwicklung.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CLOUDKOFFER 2026                                │
│                                                                         │
│   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│   │  node0  │ │  node1  │ │  node2  │ │  node3  │ │  node4  │          │
│   │   DNS   │ │  Master │ │  Worker │ │  Worker │ │  Worker │          │
│   │Grafana  │ │   ZK    │ │   ZK    │ │   ZK    │ │  Solr   │          │
│   │Promethe.│ │  Solr   │ │  Solr   │ │  Solr   │ │  Spark  │          │
│   └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘          │
│        │           │           │           │           │                │
│        └───────────┴───────────┴───────────┴───────────┘                │
│                          Gigabit Switch                                 │
│                               │                                         │
│                        ┌──────┴──────┐                                  │
│                        │ EdgeRouter X │──── Internet                    │
│                        └─────────────┘                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Was ist das?

Der **Cloudkoffer** ist ein kompletter Big Data Stack in einem transportablen Koffer:

- **5 Intel NUCs** mit je 32 GB RAM, 4 Cores, NVMe SSD
- **EdgeRouter X** für Netzwerk und DHCP
- **Gigabit Switch** für interne Kommunikation
- Alles in einem Koffer verstaut

### Einsatzzwecke

- 📊 **Demos** - Big Data Technologien live zeigen
- 🎓 **Workshops** - Hands-on Training ohne Cloud-Abhängigkeit
- 🧪 **Entwicklung** - Lokaler Cluster für Tests
- 🏢 **Offline-Umgebungen** - Funktioniert ohne Internet

---

## Technologie-Stack

### Datenverarbeitung

| Komponente | Beschreibung | Nodes |
|------------|--------------|-------|
| [Apache Solr](https://solr.apache.org/) | Volltextsuche & Analytics | node1-4 |
| [Apache Spark](https://spark.apache.org/) | Verteilte Datenverarbeitung | node1-4 |
| [Apache ZooKeeper](https://zookeeper.apache.org/) | Cluster-Koordination | node1-3 |

### Monitoring

| Komponente | Beschreibung | Node |
|------------|--------------|------|
| [Prometheus](https://prometheus.io/) | Metriken-Sammlung | node0 |
| [Grafana](https://grafana.com/) | Dashboards & Visualisierung | node0 |
| Node Exporter | System-Metriken | alle |

### Infrastruktur

| Komponente | Beschreibung |
|------------|--------------|
| Ubuntu 24.04 LTS | Betriebssystem |
| Cloud-Init | Automatische Konfiguration |
| dnsmasq | DNS für `cloud.local` Domain |
| OpenJDK 17 | Java Runtime |

---

## Architektur-Konzepte

### Warum ZooKeeper?

ZooKeeper ist das "Gehirn" des Clusters:
- **Leader Election** - Wer ist der aktive Solr-Leader?
- **Konfiguration** - Cluster-weite Einstellungen zentral
- **Koordination** - Verteilte Locks und Synchronisation

> 3 Nodes = Quorum möglich, toleriert 1 Ausfall

### Warum Solr Cloud?

Verteilte Suche mit:
- **Sharding** - Daten auf mehrere Nodes verteilen
- **Replikation** - Ausfallsicherheit durch Kopien
- **Near Real-Time** - Dokumente sofort durchsuchbar

### Warum Spark?

Verteilte Datenverarbeitung:
- **In-Memory** - Schneller als Hadoop MapReduce
- **SQL** - Spark SQL für Analytics
- **Streaming** - Echtzeit-Verarbeitung möglich
- **Solr-Integration** - Daten direkt in Solr indexieren

---

## Netzwerk

| Node | IP | Hostname | Rolle |
|------|-----|----------|-------|
| node0 | 192.168.1.100 | node0.cloud.local | DNS, Monitoring |
| node1 | 192.168.1.101 | node1.cloud.local | ZK, Solr, Spark Master |
| node2 | 192.168.1.102 | node2.cloud.local | ZK, Solr, Spark Worker |
| node3 | 192.168.1.103 | node3.cloud.local | ZK, Solr, Spark Worker |
| node4 | 192.168.1.104 | node4.cloud.local | Solr, Spark Worker |

- **Router**: 192.168.1.1 (EdgeRouter X)
- **Domain**: cloud.local
- **DHCP**: Statische Zuweisung per MAC-Adresse

---

## Quick Start

### 1. Cluster aufsetzen

```bash
cd baremetal

# Konfiguration generieren
./01-generate-configs/generate-all.sh

# Bootbares ISO erstellen
./02-create-iso/create-iso.sh

# Auf USB-Stick schreiben
./03-write-usb/write-usb.sh /dev/sdX

# Jeden NUC vom USB booten (F10)
# Nach Installation: Post-Install pro Node
./04-post-install/apply-cloud-init.sh 192.168.1.100
./04-post-install/apply-cloud-init.sh 192.168.1.101
# ... usw.
```

### 2. Cluster validieren

```bash
./baremetal/09-smoke-tests/smoke-tests.sh
```

### 3. Zugriff auf Services

| Service | URL |
|---------|-----|
| Solr Admin | http://node1.cloud.local:8983/solr/ |
| Spark Master | http://node1.cloud.local:8080/ |
| Grafana | http://node0.cloud.local:3000/ |
| Prometheus | http://node0.cloud.local:9090/ |

---

## Dokumentation

| Dokument | Inhalt |
|----------|--------|
| [BAREMETAL-SETUP.md](BAREMETAL-SETUP.md) | Ubuntu Installation, Cloud-Init |
| [SOLR-SPARK-SETUP.md](SOLR-SPARK-SETUP.md) | ZooKeeper, Solr, Spark Konfiguration |
| [MONITORING-SETUP.md](MONITORING-SETUP.md) | Prometheus, Grafana, Exporter |
| [baremetal/README.md](baremetal/README.md) | Schritt-für-Schritt Anleitung |

---

## Verzeichnisstruktur

```
Cloudkoffer-2026/
├── README.md                    ← Du bist hier
├── BAREMETAL-SETUP.md           # OS-Installation Doku
├── SOLR-SPARK-SETUP.md          # Big Data Stack Doku
├── MONITORING-SETUP.md          # Monitoring Doku
│
└── baremetal/                   # Installations-Scripts
    ├── 00-edgerouter-config/    # Router Backup & Restore
    ├── 01-generate-configs/     # Autoinstall generieren
    ├── 02-create-iso/           # Bootbares ISO erstellen
    ├── 03-write-usb/            # ISO auf USB schreiben
    ├── 04-post-install/         # Node-spezifische Konfig
    ├── 05-install-zookeeper/    # ZooKeeper Cloud-Init
    ├── 06-install-solr/         # Solr Cloud-Init
    ├── 07-install-spark/        # Spark Cloud-Init
    ├── 08-install-monitoring/   # Prometheus/Grafana Cloud-Init
    ├── 09-smoke-tests/          # Cluster-Validierung
    └── 10-create-solr-collection/ # Solr Collection anlegen
```

---

## Credentials

| Service | User | Passwort |
|---------|------|----------|
| SSH | cloudadmin | (nur SSH-Key) |
| Grafana | admin | admin (beim ersten Login ändern) |

---

## Lizenz

Internes Projekt - nicht zur Veröffentlichung bestimmt.
