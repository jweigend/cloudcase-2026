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

| Node  | IP            | Rollen                                             |
|-------|---------------|----------------------------------------------------|
| node0 | 192.168.1.100 | Spark Master, Prometheus, Grafana, JupyterLab, DNS |
| node1 | 192.168.1.101 | ZooKeeper, Solr, Spark Worker, DNS                 |
| node2 | 192.168.1.102 | ZooKeeper, Solr, Spark Worker, DNS                 |
| node3 | 192.168.1.103 | ZooKeeper, Solr, Spark Worker, DNS                 |
| node4 | 192.168.1.104 | Solr, Spark Worker, DNS                            |

> ZK Leader per Election • Spark Master auf node0 • 4 Workers auf node1-4 • DNS auf allen Nodes

---

## Storage

| Verzeichnis | Zweck | Nodes |
|-------------|-------|-------|
| `/data/solr` | Solr Index | node1-4 |
| `/data/spark` | Shuffle/Spill | node0-4 |
| `/data/zookeeper` | ZK Data | node1-3 |
| `/data/prometheus` | TSDB | node0 |
| `/data/jupyter` | Notebooks | node0 |

---

## Ports

| Service | Port | Nodes |
|---------|------|-------|
| ZooKeeper | 2181 | node1-3 |
| Solr | 8983 | node1-4 |
| Spark Master | 7077/8081 | node0 |
| Spark Worker | 8081 | node1-4 |
| Prometheus | 9090 | node0 |
| Grafana | 3000 | node0 |
| JupyterLab | 8888 | node0 |
| Node Exporter | 9100 | Alle |
| DNS (dnsmasq) | 53 | Alle |
| JMX (Solr/Spark/ZK) | 9404-9406 | node1-4 |

---

## Smoke Tests

```bash
# ZooKeeper
echo ruok | nc node1 2181

# Solr
curl http://node1:8983/solr/admin/info/system

# Spark
curl http://node0:8081

# Prometheus
curl http://node0:9090/-/ready

# Grafana
curl http://node0:3000/api/health
```

---

*Januar 2026*

---

## Lizenz

MIT License - siehe [LICENSE](../LICENSE) | © 2026 Johannes Weigend, Weigend AM
