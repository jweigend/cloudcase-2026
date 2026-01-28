# Cloudkoffer 2026 - Big Data Cluster Setup

## Übersicht

Dieses Projekt beschreibt das Setup eines portablen Big Data Clusters auf 5 Intel NUCs ("Cloudkoffer"). Das System kombiniert Apache Solr Cloud für Volltextsuche, Apache Spark für verteilte Datenverarbeitung, ZooKeeper für Cluster-Koordination sowie Prometheus und Grafana für Monitoring.

---

## Hardware-Spezifikation

| Komponente | Spezifikation |
|------------|---------------|
| **RAM** | 32 GB pro Node |
| **CPU** | 4 echte Cores pro Node |
| **Storage** | SSD oder NVMe |
| **Netzwerk** | Gigabit Ethernet |

---

## Netzwerk & Rollenverteilung

| Node | Hostname | IP-Adresse | Rollen |
|------|----------|------------|--------|
| NUC1 | nuc1 | 192.168.0.100 | ZooKeeper, Solr, Prometheus, Grafana |
| NUC2 | nuc2 | 192.168.0.101 | ZooKeeper, Solr, Spark Master |
| NUC3 | nuc3 | 192.168.0.102 | ZooKeeper, Solr, Spark Worker |
| NUC4 | nuc4 | 192.168.0.103 | Solr, Spark Worker |
| NUC5 | nuc5 | 192.168.0.104 | Solr, Spark Worker |

> **Hinweis:** ZooKeeper Leader wird automatisch per Election gewählt (kein fixer Leader-Node).  
> **Hinweis:** Spark Worker laufen **nur** auf NUC3, NUC4, NUC5 – keine Worker auf NUC1/NUC2.

### Netzwerk-Empfehlung

- DHCP auf OS-Seite verwenden
- Feste IPs nur im Router vergeben (MAC-Bindung)
- `/etc/hosts` auf allen Nodes identisch pflegen

---

## Architektur-Konzept

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CLOUDKOFFER CLUSTER                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                          │
│  │ ZooKeeper 1 │  │ ZooKeeper 2 │  │ ZooKeeper 3 │     ZK Ensemble (3 Node) │
│  │   (NUC1)    │◄─►│   (NUC2)    │◄─►│   (NUC3)    │                          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                          │
│         │                │                │                                  │
│  ═══════╪════════════════╪════════════════╪═════════════════════════════    │
│         │                │                │                                  │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐  ┌─────────────┐  ┌─────────────┐
│  │   Solr 1    │  │   Solr 2    │  │   Solr 3    │  │   Solr 4    │  │   Solr 5    │
│  │   (NUC1)    │  │   (NUC2)    │  │   (NUC3)    │  │   (NUC4)    │  │   (NUC5)    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════    │
│                                                                              │
│                   ┌─────────────┐                                            │
│                   │Spark Master │                                            │
│                   │   (NUC2)    │                                            │
│                   └──────┬──────┘                                            │
│         ┌────────────────┼────────────────┐                                  │
│         ▼                ▼                ▼                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                          │
│  │Spark Worker │  │Spark Worker │  │Spark Worker │                          │
│  │   (NUC3)    │  │   (NUC4)    │  │   (NUC5)    │                          │
│  └─────────────┘  └─────────────┘  └─────────────┘                          │
│                                                                              │
│  ═══════════════════════════════════════════════════════════════════════    │
│                                                                              │
│  ┌─────────────┐       ┌─────────────┐                                      │
│  │ Prometheus  │──────►│   Grafana   │     Monitoring (NUC1)                │
│  │   (NUC1)    │       │   (NUC1)    │                                      │
│  └─────────────┘       └─────────────┘                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Komponenten-Details

### 1. ZooKeeper Ensemble (3 Nodes)

**Nodes:** NUC1, NUC2, NUC3

ZooKeeper bildet das Rückgrat des Clusters und koordiniert:
- Solr Cloud Leader Election
- Cluster State Management
- Configuration Management

**Konfiguration:**
- 3-Node Ensemble für Quorum (toleriert 1 Node-Ausfall)
- Port 2181 (Client), 2888 (Follower), 3888 (Election)
- **Heap: 1 GB**
- **Data Dir: `/data/zookeeper`**
- Leader wird automatisch per Election gewählt

**ZK IDs:**
| Node | myid |
|------|------|
| NUC1 | 1 |
| NUC2 | 2 |
| NUC3 | 3 |

### 2. Apache Solr Cloud (5 Nodes)

**Nodes:** NUC1 - NUC5 (alle Nodes)

Solr Cloud läuft verteilt auf allen 5 NUCs für maximale Suchleistung.

**Konfiguration:**
- Port: 8983
- **Heap: 8 GB pro Node**
- **Data Dir: `/data/solr`**

**Empfohlene Default Collection:**
```bash
bin/solr create_collection -c default \
  -shards 4 \
  -replicationFactor 2 \
  -maxShardsPerNode 2
```

| Parameter | Wert |
|-----------|------|
| numShards | 4 |
| replicationFactor | 2 |
| maxShardsPerNode | 2 |

### 3. Apache Spark (1 Master + 3 Worker)

**Master:** NUC2  
**Workers:** NUC3, NUC4, NUC5

> **Wichtig:** Keine Spark Worker auf NUC1 (Monitoring) und NUC2 (Master).

**Spark Master (NUC2):**
- Port: 7077, Web UI: 8080
- **Heap: 2 GB**

**Spark Worker (NUC3-NUC5):**
- **Executor Memory: 8 GB**
- **Executors pro Node: 2**
- **Cores pro Executor: 2**
- **Data Dir: `/data/spark`** (Shuffle/Spill)

**spark-defaults.conf:**
```properties
spark.executor.memory=8g
spark.executor.cores=2
spark.executor.instances=2
spark.driver.memory=2g
```

### 4. Prometheus + Grafana (Monitoring)

**Node:** NUC1

**Prometheus:**
- Port: 9090
- Scrape-Intervall: 15s
- Retention: 15 Tage
- **Data Dir: `/data/prometheus`**

**Prometheus Scrape Targets (via JMX Exporter):**

| Service | Exporter | Port | Nodes |
|---------|----------|------|-------|
| Node Metrics | node_exporter | 9100 | Alle |
| Solr | JMX Exporter | 9404 | Alle |
| Spark | JMX Exporter | 9405 | NUC2-NUC5 |
| ZooKeeper | JMX Exporter | 9406 | NUC1-NUC3 |

**prometheus.yml Scrape Config:**
```yaml
scrape_configs:
  - job_name: 'node'
    static_configs:
      - targets:
        - 'nuc1:9100'
        - 'nuc2:9100'
        - 'nuc3:9100'
        - 'nuc4:9100'
        - 'nuc5:9100'

  - job_name: 'solr'
    static_configs:
      - targets:
        - 'nuc1:9404'
        - 'nuc2:9404'
        - 'nuc3:9404'
        - 'nuc4:9404'
        - 'nuc5:9404'

  - job_name: 'spark'
    static_configs:
      - targets:
        - 'nuc2:9405'
        - 'nuc3:9405'
        - 'nuc4:9405'
        - 'nuc5:9405'

  - job_name: 'zookeeper'
    static_configs:
      - targets:
        - 'nuc1:9406'
        - 'nuc2:9406'
        - 'nuc3:9406'
```

**Grafana:**
- Port: 3000
- Dashboards für: Cluster Overview, Solr, Spark, ZooKeeper

---

## Ressourcen-Aufteilung (32 GB RAM pro Node)

### RAM-Aufteilung

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        RAM-AUFTEILUNG PRO NODE (32 GB)                        │
├──────────────────────────────────────────────────────────────────────────────┤
│ Node  │ Solr    │ ZooKeeper │ Spark      │ Monitoring │ OS/Cache │ Reserve  │
├──────────────────────────────────────────────────────────────────────────────┤
│ NUC1  │  8 GB   │   1 GB    │     -      │    2 GB    │   6 GB   │  15 GB   │
│ NUC2  │  8 GB   │   1 GB    │  2 GB (M)  │     -      │   6 GB   │  15 GB   │
│ NUC3  │  8 GB   │   1 GB    │ 16 GB (W)  │     -      │   6 GB   │   1 GB   │
│ NUC4  │  8 GB   │    -      │ 16 GB (W)  │     -      │   6 GB   │   2 GB   │
│ NUC5  │  8 GB   │    -      │ 16 GB (W)  │     -      │   6 GB   │   2 GB   │
└──────────────────────────────────────────────────────────────────────────────┘
(M) = Master, (W) = Worker (2 Executors × 8 GB)
```

### CPU-Aufteilung (4 Cores pro Node)

**Systemd Resource Control:**

```ini
# /etc/systemd/system/solr.service.d/override.conf
[Service]
MemoryMax=8G
CPUQuota=200%

# /etc/systemd/system/spark-worker.service.d/override.conf
[Service]
MemoryMax=16G
CPUQuota=200%
```

---

## Storage-Layout

| Verzeichnis | Zweck | Nodes |
|-------------|-------|-------|
| `/data/solr` | Solr Index | Alle |
| `/data/spark` | Spark Shuffle/Spill | NUC2-NUC5 |
| `/data/zookeeper` | ZK Data + Snapshots | NUC1-NUC3 |
| `/data/prometheus` | Prometheus TSDB | NUC1 |

---

## Provisioning mit Ubuntu Autoinstall & Cloud-Init

### Strategie

```
┌─────────────────────────────────────────────────────────────────┐
│                    PROVISIONING WORKFLOW                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. USB Boot mit Ubuntu Server ISO + Autoinstall                │
│     └─► user-data & meta-data auf USB/HTTP-Server               │
│                                                                  │
│  2. Ubuntu Autoinstall                                          │
│     └─► Partitionierung, Basis-Pakete, Netzwerk                 │
│                                                                  │
│  3. Cloud-Init (First Boot)                                     │
│     └─► Hostname, SSH Keys, Basis-Konfiguration                 │
│                                                                  │
│  4. Ansible/Shell Scripts (Post-Install)                        │
│     └─► Java, ZooKeeper, Solr, Spark, Monitoring                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Verzeichnisstruktur

```
cloudkoffer-2026/
├── autoinstall/
│   ├── user-data.yaml          # Autoinstall Konfiguration
│   └── meta-data               # Leere Datei oder Metadaten
├── cloud-init/
│   ├── common/
│   │   └── cloud-config.yaml   # Gemeinsame Config für alle Nodes
│   └── nodes/
│       ├── nuc1.yaml
│       ├── nuc2.yaml
│       ├── nuc3.yaml
│       ├── nuc4.yaml
│       └── nuc5.yaml
├── ansible/                    # Optional: Ansible Playbooks
│   ├── inventory.ini
│   ├── playbook-base.yaml
│   ├── playbook-zookeeper.yaml
│   ├── playbook-solr.yaml
│   ├── playbook-spark.yaml
│   └── playbook-monitoring.yaml
├── configs/
│   ├── zookeeper/
│   ├── solr/
│   ├── spark/
│   ├── prometheus/
│   └── grafana/
└── README.md
```

### Ubuntu Autoinstall user-data (Beispiel)

```yaml
#cloud-config
autoinstall:
  version: 1
  locale: de_DE.UTF-8
  keyboard:
    layout: de
  identity:
    hostname: nucX  # Wird per Node angepasst
    username: cloudadmin
    password: <hashed-password>
  ssh:
    install-server: true
    allow-pw: false
    authorized-keys:
      - ssh-rsa AAAA... # Dein SSH Public Key
  network:
    version: 2
    ethernets:
      enp0s31f6:  # NIC-Name prüfen!
        addresses:
          - 192.168.0.10X/24
        gateway4: 192.168.0.1
        nameservers:
          addresses: [8.8.8.8, 8.8.4.4]
  packages:
    - openssh-server
    - htop
    - net-tools
    - openjdk-17-jdk
  late-commands:
    - curtin in-target -- systemctl enable ssh
```

### Cloud-Init Node-spezifisch (Beispiel NUC1)

```yaml
#cloud-config
hostname: nuc1
fqdn: nuc1.cloudkoffer.local
manage_etc_hosts: true

write_files:
  - path: /etc/hosts
    append: true
    content: |
      192.168.0.100 nuc1 nuc1.cloudkoffer.local
      192.168.0.101 nuc2 nuc2.cloudkoffer.local
      192.168.0.102 nuc3 nuc3.cloudkoffer.local
      192.168.0.103 nuc4 nuc4.cloudkoffer.local
      192.168.0.104 nuc5 nuc5.cloudkoffer.local

runcmd:
  - echo "NUC1 initialized" >> /var/log/cloud-init-custom.log
```

---

## Ressourcen-Isolation: Solr vs. Spark

### Strategie 1: Zeitliche Trennung (Empfohlen für Demos)
- Spark-Jobs nur außerhalb von Solr-Lastspitzen
- Scheduling über Cron/Airflow

### Strategie 2: Systemd Resource Control

```ini
# /etc/systemd/system/solr.service.d/override.conf
[Service]
MemoryMax=4G
CPUQuota=150%

---

## Port-Übersicht

| Service | Port | Nodes |
|---------|------|-------|
| ZooKeeper Client | 2181 | NUC1, NUC2, NUC3 |
| ZooKeeper Follower | 2888 | NUC1, NUC2, NUC3 |
| ZooKeeper Election | 3888 | NUC1, NUC2, NUC3 |
| Solr | 8983 | Alle |
| Spark Master | 7077 | NUC2 |
| Spark Master UI | 8080 | NUC2 |
| Spark Worker UI | 8081 | NUC3, NUC4, NUC5 |
| Prometheus | 9090 | NUC1 |
| Grafana | 3000 | NUC1 |
| Node Exporter | 9100 | Alle |
| Solr JMX Exporter | 9404 | Alle |
| Spark JMX Exporter | 9405 | NUC2-NUC5 |
| ZooKeeper JMX Exporter | 9406 | NUC1-NUC3 |

---

## Smoke Tests

Nach dem Setup können folgende Tests zur Validierung ausgeführt werden:

```bash
# ZooKeeper Health Check
echo ruok | nc nuc1 2181
echo ruok | nc nuc2 2181
echo ruok | nc nuc3 2181

# Solr System Info
curl http://nuc1:8983/solr/admin/info/system

# Spark Master UI
curl http://nuc2:8080

# Prometheus Ready Check
curl http://nuc1:9090/-/ready

# Grafana Health
curl http://nuc1:3000/api/health
```

---

## Nächste Schritte

1. [x] ~~Hardware-Spezifikationen der NUCs klären (RAM, CPU, Storage)~~
2. [ ] Autoinstall ISO erstellen und testen
3. [ ] Cloud-Init Konfigurationen finalisieren
4. [ ] ZooKeeper Ensemble aufsetzen und testen
5. [ ] Solr Cloud deployen und Collection erstellen
6. [ ] Spark Cluster deployen und Test-Job ausführen
7. [ ] Prometheus + Grafana + JMX Exporter einrichten
8. [ ] Smoke Tests durchführen
9. [ ] End-to-End Tests durchführen

---

*Erstellt: Januar 2026*
