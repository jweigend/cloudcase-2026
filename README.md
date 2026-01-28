# Cloudkoffer 2026 - Big Data Cluster Setup

## Übersicht

Dieses Projekt beschreibt das Setup eines portablen Big Data Clusters auf 5 Intel NUCs ("Cloudkoffer"). Das System kombiniert Apache Solr Cloud für Volltextsuche, Apache Spark für verteilte Datenverarbeitung, ZooKeeper für Cluster-Koordination sowie Prometheus und Grafana für Monitoring.

---

## Hardware & Netzwerk

| Node | Hostname | IP-Adresse | Rolle |
|------|----------|------------|-------|
| NUC1 | nuc1 | 192.168.0.100 | ZooKeeper Leader, Solr, Prometheus, Grafana |
| NUC2 | nuc2 | 192.168.0.101 | ZooKeeper, Solr, Spark Master |
| NUC3 | nuc3 | 192.168.0.102 | ZooKeeper, Solr, Spark Worker |
| NUC4 | nuc4 | 192.168.0.103 | Solr, Spark Worker |
| NUC5 | nuc5 | 192.168.0.104 | Solr, Spark Worker |

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
- Heap: 512 MB (leichtgewichtig)

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
- Heap: 2-4 GB pro Node (abhängig von RAM)
- Replikationsfaktor: 2 (Ausfallsicherheit)
- Shards: Abhängig von Collection-Größe

**Ressourcen-Isolation:**
- Solr erhält Priorität auf NUC1 (kein Spark Worker)
- CPU/Memory Limits via cgroups oder systemd

### 3. Apache Spark (1 Master + 3 Worker)

**Master:** NUC2  
**Workers:** NUC3, NUC4, NUC5

Spark Master läuft auf NUC2, um Last von NUC1 (Monitoring) fernzuhalten.

**Konfiguration:**
- Master Port: 7077, Web UI: 8080
- Worker Memory: 4-6 GB pro Worker
- Worker Cores: 2-4 pro Worker (abhängig von NUC-Spezifikation)

**Ressourcen-Isolation gegenüber Solr:**
```
┌────────────────────────────────────────────────────────────────┐
│                     RESSOURCEN-AUFTEILUNG                       │
├────────────────────────────────────────────────────────────────┤
│ Node  │ Solr Heap │ Spark Memory │ ZK Heap │ System Reserved  │
├────────────────────────────────────────────────────────────────┤
│ NUC1  │   4 GB    │     -        │ 512 MB  │    1.5 GB        │
│ NUC2  │   3 GB    │   1 GB (M)   │ 512 MB  │    1.5 GB        │
│ NUC3  │   2 GB    │   4 GB (W)   │ 512 MB  │    1.5 GB        │
│ NUC4  │   2 GB    │   5 GB (W)   │   -     │    1 GB          │
│ NUC5  │   2 GB    │   5 GB (W)   │   -     │    1 GB          │
└────────────────────────────────────────────────────────────────┘
(Annahme: 8 GB RAM pro NUC - anpassen an tatsächliche Hardware!)
```

### 4. Prometheus + Grafana (Monitoring)

**Node:** NUC1

**Prometheus:**
- Port: 9090
- Scrape-Intervall: 15s
- Retention: 15 Tage

**Zu überwachende Endpoints:**
| Service | Exporter/Endpoint |
|---------|-------------------|
| Node Metrics | node_exporter:9100 (alle Nodes) |
| Solr | :8983/solr/admin/metrics |
| Spark | :8080/metrics/json |
| ZooKeeper | :7000 (Prometheus Metrics) |

**Grafana:**
- Port: 3000
- Dashboards für: Cluster Overview, Solr, Spark, ZooKeeper

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

# /etc/systemd/system/spark-worker.service.d/override.conf
[Service]
MemoryMax=5G
CPUQuota=200%
```

### Strategie 3: Dedizierte Nodes
- NUC1: Nur Solr + Monitoring (kein Spark Worker)
- NUC4, NUC5: Primär Spark, Solr mit reduziertem Heap

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

---

## Nächste Schritte

1. [ ] Hardware-Spezifikationen der NUCs klären (RAM, CPU, Storage)
2. [ ] Autoinstall ISO erstellen und testen
3. [ ] Cloud-Init Konfigurationen finalisieren
4. [ ] ZooKeeper Ensemble aufsetzen und testen
5. [ ] Solr Cloud deployen und Collection erstellen
6. [ ] Spark Cluster deployen und Test-Job ausführen
7. [ ] Prometheus + Grafana einrichten
8. [ ] End-to-End Tests durchführen

---

## Offene Fragen

- **RAM pro NUC?** (Beeinflusst Heap-Sizing massiv)
- **Storage-Typ?** (SSD/NVMe empfohlen für Solr)
- **Netzwerk-Switch vorhanden?** (Gigabit empfohlen)
- **Soll ein Node als "Router" dienen?** (NAT für Internet-Zugang)
- **Backup-Strategie?** (Solr Snapshots, ZK Snapshots)

---

*Erstellt: Januar 2026*
