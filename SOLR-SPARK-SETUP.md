# Solr Cloud, Spark & ZooKeeper Setup

Konfiguration über Cloud-Init.

> **Cloud-Init Dateien:** [`baremetal/05-install-zookeeper/`](baremetal/05-install-zookeeper/), [`baremetal/06-install-solr/`](baremetal/06-install-solr/), [`baremetal/07-install-spark/`](baremetal/07-install-spark/)

---

## Architektur

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                    │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                               │
│  │ ZooKeeper 1 │   │ ZooKeeper 2 │   │ ZooKeeper 3 │     ZK Ensemble               │
│  │   (node1)   │◄─►│   (node2)   │◄─►│   (node3)   │                               │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘                               │
│         │                 │                 │                                      │
│  ┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼──────┐   ┌─────────────┐             │
│  │   Solr 1    │   │   Solr 2    │   │   Solr 3    │   │   Solr 4    │             │
│  │   (node1)   │   │   (node2)   │   │   (node3)   │   │   (node4)   │             │
│  └─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘             │
│                                                                                    │
│                          ┌─────────────┐                                           │
│                          │Spark Master │                                           │
│                          │   (node0)   │                                           │
│                          └──────┬──────┘                                           │
│         ┌────────────────┬──────┴──────┬────────────────┐                          │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐                │
│  │Spark Worker │  │Spark Worker │  │Spark Worker │  │Spark Worker │                │
│  │   (node1)   │  │   (node2)   │  │   (node3)   │  │   (node4)   │                │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘                │
│                                                                                    │
│  DNS (dnsmasq) läuft auf allen Nodes → EdgeRouter → Internet                      │
│                                                                                    │
└────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. ZooKeeper

**Ansible Playbook:** `baremetal/05-ansible/zookeeper.yml`

| Parameter | Wert |
|-----------|------|
| Nodes | node1, node2, node3 |
| Port | 2181 |
| Heap | 512 MB |
| Data Dir | `/data/zookeeper` |

### zoo.cfg (via Ansible)

```properties
tickTime=2000
initLimit=10
syncLimit=5
dataDir=/data/zookeeper
clientPort=2181

server.1=node1.cloud.local:2888:3888
server.2=node2.cloud.local:2888:3888
server.3=node3.cloud.local:2888:3888

4lw.commands.whitelist=mntr,conf,ruok,stat,srvr
```

### Services starten

```bash
# Via Ansible
cd baremetal/05-ansible
ansible-playbook -i inventory.yml zookeeper.yml
```

---

## 2. Solr Cloud

**Ansible Playbook:** `baremetal/05-ansible/solr.yml`

| Parameter | Wert |
|-----------|------|
| Nodes | node1, node2, node3, node4 |
| Port | 8983 |
| Heap | 8 GB |
| JMX | 9404 |

### solr.in.sh (via Ansible)

```bash
SOLR_HEAP="8g"
SOLR_HOME="/data/solr"
ZK_HOST="node1:2181,node2:2181,node3:2181"
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

**Ansible Playbook:** `baremetal/05-ansible/spark.yml`

| Komponente | Node | Heap |
|------------|------|------|
| Master | node0 | 2 GB |
| Worker | node1-4 | 6 GB |

### spark-defaults.conf (via Ansible)

```properties
spark.master                     spark://node0.cloud.local:7077
spark.local.dir                  /data/spark
spark.executor.memory            6g
spark.executor.cores             2
spark.driver.memory              4g
spark.sql.shuffle.partitions     48
```

---

## Ressourcen-Verteilung (32 GB RAM / 4 Cores)

| Node | Solr | Spark | ZooKeeper | Monitoring |
|------|------|-------|-----------|------------|
| node0 | - | Master 2 GB | - | Prometheus, Grafana |
| node1 | 8 GB | Worker 6 GB | 512 MB | - |
| node2 | 8 GB | Worker 6 GB | 512 MB | - |
| node3 | 8 GB | Worker 6 GB | 512 MB | - |
| node4 | 8 GB | Worker 6 GB | - | - |

---

## Ports

| Service | Port |
|---------|------|
| ZooKeeper | 2181, 2888, 3888 |
| ZooKeeper Metrics | 7070 |
| Solr | 8983 |
| Solr JMX | 9404 |
| Spark Master | 7077 |
| Spark Master UI | 8081 |
| Spark Worker UI | 8081 |
| Spark JMX | 9405 |

---

*Weiter mit [MONITORING-SETUP.md](MONITORING-SETUP.md)*

---

## Lizenz

MIT License - siehe [LICENSE](LICENSE) | © 2026 Johannes Weigend, Weigend AM
