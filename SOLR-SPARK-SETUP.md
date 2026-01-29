# Solr Cloud, Spark & ZooKeeper Setup

Konfiguration über Cloud-Init.

> **Cloud-Init Dateien:** [`baremetal/05-install-zookeeper/`](baremetal/05-install-zookeeper/), [`baremetal/06-install-solr/`](baremetal/06-install-solr/), [`baremetal/07-install-spark/`](baremetal/07-install-spark/)

---

## Architektur

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                          │
│  │ ZooKeeper 1 │  │ ZooKeeper 2 │  │ ZooKeeper 3 │     ZK Ensemble          │
│  │   (NUC1)    │◄─►│   (NUC2)    │◄─►│   (NUC3)    │                          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                          │
│         │                │                │                                  │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐  ┌───────────┐  ┌───────────┐
│  │   Solr 1    │  │   Solr 2    │  │   Solr 3    │  │  Solr 4   │  │  Solr 5   │
│  │   (NUC1)    │  │   (NUC2)    │  │   (NUC3)    │  │  (NUC4)   │  │  (NUC5)   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘  └───────────┘
│                                                                              │
│                   ┌─────────────┐                                            │
│                   │Spark Master │                                            │
│                   │   (NUC2)    │                                            │
│                   └──────┬──────┘                                            │
│         ┌────────────────┼────────────────┐                                  │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐                          │
│  │Spark Worker │  │Spark Worker │  │Spark Worker │                          │
│  │   (NUC3)    │  │   (NUC4)    │  │   (NUC5)    │                          │
│  └─────────────┘  └─────────────┘  └─────────────┘                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. ZooKeeper

**Cloud-Init:** `baremetal/05-install-zookeeper/cloud-init.yaml`

| Parameter | Wert |
|-----------|------|
| Nodes | NUC1, NUC2, NUC3 |
| Port | 2181 |
| Heap | 1 GB |
| Data Dir | `/data/zookeeper` |

### zoo.cfg (via Cloud-Init)

```properties
tickTime=2000
initLimit=10
syncLimit=5
dataDir=/data/zookeeper
clientPort=2181

server.1=nuc1:2888:3888
server.2=nuc2:2888:3888
server.3=nuc3:2888:3888
```

### Services starten

```bash
# Alle 3 gleichzeitig starten!
for node in nuc1 nuc2 nuc3; do
    ssh cloudadmin@$node 'sudo systemctl start zookeeper'
done
```

---

## 2. Solr Cloud

**Cloud-Init:** `baremetal/06-install-solr/cloud-init.yaml`

| Parameter | Wert |
|-----------|------|
| Nodes | Alle (NUC1-5) |
| Port | 8983 |
| Heap | 8 GB |
| JMX | 9404 |

### solr.in.sh (via Cloud-Init)

```bash
SOLR_HEAP="8g"
SOLR_HOME="/data/solr"
ZK_HOST="nuc1:2181,nuc2:2181,nuc3:2181"
ENABLE_REMOTE_JMX_OPTS="true"
RMI_PORT="9404"
```

### Systemd Resource Limits

```ini
MemoryMax=10G
CPUQuota=200%     # 2 von 4 Cores
```

### Collection erstellen

```bash
cd baremetal/10-create-solr-collection
./create-collection.sh demo
```

---

## 3. Spark

**Cloud-Init:** 
- Master: `baremetal/07-install-spark/cloud-init-master.yaml`
- Worker: `baremetal/07-install-spark/cloud-init-worker.yaml`

| Komponente | Node | Heap |
|------------|------|------|
| Master | NUC2 | 2 GB |
| Worker | NUC3-5 | 16 GB |

### spark-defaults.conf (via Cloud-Init)

```properties
spark.master                     spark://nuc2:7077
spark.local.dir                  /data/spark
spark.executor.memory            8g
spark.executor.cores             2
spark.driver.memory              2g
spark.sql.shuffle.partitions     12
```

---

## Ressourcen-Verteilung (32 GB RAM / 4 Cores)

| Node | Solr | Spark | ZooKeeper | Monitoring |
|------|------|-------|-----------|------------|
| NUC1 | 8 GB | - | 1 GB | 2 GB |
| NUC2 | 8 GB | 2 GB (Master) | 1 GB | - |
| NUC3 | 8 GB | 16 GB (Worker) | 1 GB | - |
| NUC4 | 8 GB | 16 GB (Worker) | - | - |
| NUC5 | 8 GB | 16 GB (Worker) | - | - |

---

## Ports

| Service | Port |
|---------|------|
| ZooKeeper | 2181, 2888, 3888 |
| Solr | 8983 |
| Solr JMX | 9404 |
| Spark Master | 7077, 8080 |
| Spark Worker | 8081 |
| Spark JMX | 9405 |

---

*Weiter mit [MONITORING-SETUP.md](MONITORING-SETUP.md)*
