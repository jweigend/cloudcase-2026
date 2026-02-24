# Cloudkoffer Referenz

Single Source of Truth für Netzwerk, Ports, Versionen und Credentials.

---

## Cluster-Architektur

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CLOUDKOFFER 2026                                │
│                                                                         │
│   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│   │  node0  │ │  node1  │ │  node2  │ │  node3  │ │  node4  │           │
│   │ Spark   │ │  ZK     │ │  ZK     │ │  ZK     │ │  Solr   │           │
│   │ Master  │ │  Solr   │ │  Solr   │ │  Solr   │ │  Spark  │           │
│   │Jupyter  │ │  Spark  │ │  Spark  │ │  Spark  │ │  Worker │           │
│   │Grafana  │ │  Worker │ │  Worker │ │  Worker │ │         │           │
│   │Promethe.│ │         │ │         │ │         │ │         │           │
│   │nginx    │ │         │ │         │ │         │ │         │           │
│   │Backend  │ │         │ │         │ │         │ │         │           │
│   └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘           │
│        │           │           │           │           │                │
│        └───────────┴───────────┴───────────┴───────────┘                │
│                          Gigabit Switch                                 │
│                               │                                         │
│                     ┌─────────┴─────────┐                               │
│                     │    EdgeRouter X   │──── Internet                  │
│                     │  DHCP + DNS Fwd   │                               │
│                     └───────────────────┘                               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Netzwerk

| Node | IP | Hostname | Rollen |
|------|-----|----------|--------|
| node0 | 192.168.1.100 | node0.cloud.local | Spark Master, Prometheus, Grafana, JupyterLab, nginx, Backend |
| node1 | 192.168.1.101 | node1.cloud.local | ZooKeeper, Solr, Spark Worker |
| node2 | 192.168.1.102 | node2.cloud.local | ZooKeeper, Solr, Spark Worker |
| node3 | 192.168.1.103 | node3.cloud.local | ZooKeeper, Solr, Spark Worker |
| node4 | 192.168.1.104 | node4.cloud.local | Solr, Spark Worker |

- **Router**: 192.168.1.1 (EdgeRouter X)
- **Domain**: cloud.local
- **DNS**: Jeder Node hat lokalen dnsmasq-Cache → EdgeRouter → Internet

---

## Software-Versionen

| Komponente | Version |
|------------|---------|
| Ubuntu | 24.04 LTS |
| OpenJDK | 17 |
| ZooKeeper | 3.9.4 |
| Solr | 9.10.1 |
| Spark | 3.5.8 |
| Prometheus | 2.54.1 |
| Grafana | 11.4.0 |
| Node Exporter | 1.8.2 |

---

## Ports

### Kern-Services

| Service | Port | Nodes |
|---------|------|-------|
| SSH | 22 | Alle |
| ZooKeeper Client | 2181 | node1-3 |
| ZooKeeper Peer | 2888 | node1-3 |
| ZooKeeper Election | 3888 | node1-3 |
| Solr | 8983 | node1-4 |
| Spark Master | 7077 | node0 |
| Spark Master UI | 8081 | node0 |
| Spark Worker UI | 8081 | node1-4 |

### Monitoring

| Service | Port | Nodes |
|---------|------|-------|
| Prometheus | 9090 | node0 |
| Grafana | 3000 | node0 |
| Node Exporter | 9100 | Alle |
| ZooKeeper Metrics | 7070 | node1-3 |
| Solr JMX | 9404 | node1-4 |
| Spark JMX | 9405 | node0-4 |

### Anwendungen

| Service | Port | Node |
|---------|------|------|
| JupyterLab | 8888 | node0 |
| NYC Taxi Explorer (nginx) | 80 | node0 |
| Backend API | 5001 | node0 (intern) |

---

## Web UIs

| Service | URL | Zugangsdaten |
|---------|-----|--------------|
| **NYC Taxi Explorer** | http://node0.cloud.local/ | - |
| **Grafana** | http://node0.cloud.local:3000/ | admin / admin |
| **Prometheus** | http://node0.cloud.local:9090/ | - |
| **Spark Master** | http://node0.cloud.local:8081/ | - |
| **JupyterLab** | http://node0.cloud.local:8888/ | - |
| **Solr Admin** | http://node1.cloud.local:8983/solr/ | - |

---

## Verbindungsstrings

```bash
# ZooKeeper
node1.cloud.local:2181,node2.cloud.local:2181,node3.cloud.local:2181

# Solr Cloud (mit ZooKeeper)
node1.cloud.local:2181,node2.cloud.local:2181,node3.cloud.local:2181/solr

# Spark Master
spark://node0.cloud.local:7077
```

---

## Credentials

| Service | User | Passwort |
|---------|------|----------|
| SSH | cloudadmin | (nur SSH-Key) |
| Grafana | admin | admin (beim ersten Login ändern) |

---

## Hardware

| Komponente | Spezifikation |
|------------|---------------|
| Nodes | 5× Intel NUC |
| RAM | 32 GB pro Node |
| CPU | 4 Cores pro Node |
| Storage | NVMe SSD |
| Netzwerk | Gigabit Ethernet |
| Router | EdgeRouter X |

---

## Storage-Verzeichnisse

| Verzeichnis | Zweck | Nodes |
|-------------|-------|-------|
| `/data/solr` | Solr Index | node1-4 |
| `/data/spark` | Shuffle/Spill | node0-4 |
| `/data/zookeeper` | ZK Data | node1-3 |
| `/data/prometheus` | TSDB | node0 |
| `/data/jupyter` | Notebooks | node0 |

---

## Ressourcen-Verteilung (pro Node: 32 GB RAM, 4 Cores)

| Node | Solr | Spark | ZooKeeper | Sonstiges |
|------|------|-------|-----------|-----------|
| node0 | - | Master 2 GB | - | Prometheus, Grafana, Jupyter |
| node1 | 8 GB | Worker 6 GB | 512 MB | - |
| node2 | 8 GB | Worker 6 GB | 512 MB | - |
| node3 | 8 GB | Worker 6 GB | 512 MB | - |
| node4 | 8 GB | Worker 6 GB | - | - |

---

## Quick Status Check

```bash
# ZooKeeper Status
for n in 1 2 3; do echo -n "node$n: "; ssh cloudadmin@node$n "echo ruok | nc localhost 2181"; done

# Solr Status
curl -s http://node1:8983/solr/admin/info/system | jq .lucene.lucene-spec-version

# Spark Workers
curl -s http://node0:8081/json/ | jq '.aliveworkers'

# Prometheus
curl -s http://node0:9090/-/ready

# Grafana
curl -s http://node0:3000/api/health
```

---

*Stand: Februar 2026*
