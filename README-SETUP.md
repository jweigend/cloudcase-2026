# Cloudkoffer 2026 - Big Data Cluster Setup

Portabler Big Data Cluster auf 5 Intel NUCs mit Solr Cloud, Spark, ZooKeeper und Prometheus/Grafana Monitoring.

---

## Installations-Reihenfolge

```
  ┌───────────────────┐
  │  1. BAREMETAL     │  Ubuntu Autoinstall + Cloud-Init
  └─────────┬─────────┘
            ▼
  ┌───────────────────┐
  │  2. SOLR-SPARK    │  ZooKeeper → Solr Cloud → Spark
  └─────────┬─────────┘
            ▼
  ┌───────────────────┐
  │  3. MONITORING    │  Prometheus + Grafana + JMX Exporter
  └─────────┬─────────┘
            ▼
  ┌───────────────────┐
  │  4. SMOKE TESTS   │  Cluster-Validierung
  └───────────────────┘
```

| Schritt | Dokument | Beschreibung |
|---------|----------|--------------|
| **1** | [BAREMETAL-SETUP.md](BAREMETAL-SETUP.md) | Ubuntu auf allen NUCs installieren |
| **2** | [SOLR-SPARK-SETUP.md](SOLR-SPARK-SETUP.md) | ZooKeeper, Solr Cloud, Spark Cluster |
| **3** | [MONITORING-SETUP.md](MONITORING-SETUP.md) | Prometheus, Grafana, Exporter |

---

## Hardware

| Komponente | Spezifikation |
|------------|---------------|
| RAM | 32 GB pro Node |
| CPU | 4 Cores pro Node |
| Storage | SSD/NVMe |
| Netzwerk | Gigabit Ethernet |

---

## Netzwerk & Rollen

| Node | IP | Rollen |
|------|----|--------|
| nuc1 | 192.168.0.100 | ZooKeeper, Solr, Prometheus, Grafana |
| nuc2 | 192.168.0.101 | ZooKeeper, Solr, Spark Master |
| nuc3 | 192.168.0.102 | ZooKeeper, Solr, Spark Worker |
| nuc4 | 192.168.0.103 | Solr, Spark Worker |
| nuc5 | 192.168.0.104 | Solr, Spark Worker |

> ZK Leader per Election • Spark Worker nur auf NUC3-5

---

## Storage

| Verzeichnis | Zweck | Nodes |
|-------------|-------|-------|
| `/data/solr` | Solr Index | Alle |
| `/data/spark` | Shuffle/Spill | NUC2-5 |
| `/data/zookeeper` | ZK Data | NUC1-3 |
| `/data/prometheus` | TSDB | NUC1 |

---

## Ports

| Service | Port | Nodes |
|---------|------|-------|
| ZooKeeper | 2181 | NUC1-3 |
| Solr | 8983 | Alle |
| Spark Master | 7077/8080 | NUC2 |
| Spark Worker | 8081 | NUC3-5 |
| Prometheus | 9090 | NUC1 |
| Grafana | 3000 | NUC1 |
| Node Exporter | 9100 | Alle |
| JMX (Solr/Spark/ZK) | 9404-9406 | Alle |

---

## Smoke Tests

```bash
# ZooKeeper
echo ruok | nc nuc1 2181

# Solr
curl http://nuc1:8983/solr/admin/info/system

# Spark
curl http://nuc2:8080

# Prometheus
curl http://nuc1:9090/-/ready

# Grafana
curl http://nuc1:3000/api/health
```

---

*Januar 2026*
