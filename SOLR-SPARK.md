# Solr Cloud, Spark & ZooKeeper - Konfiguration

Diese Dokumentation beschreibt die detaillierte Konfiguration von Apache Solr Cloud, Apache Spark und Apache ZooKeeper auf dem Cloudkoffer-Cluster.

---

## Architektur-Übersicht

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
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. ZooKeeper Ensemble (3 Nodes)

**Nodes:** NUC1, NUC2, NUC3

ZooKeeper bildet das Rückgrat des Clusters und koordiniert:
- Solr Cloud Leader Election
- Cluster State Management
- Configuration Management

### Konfiguration

| Parameter | Wert |
|-----------|------|
| Ensemble Size | 3 Nodes (Quorum, toleriert 1 Ausfall) |
| Client Port | 2181 |
| Follower Port | 2888 |
| Election Port | 3888 |
| Heap | 1 GB |
| Data Dir | `/data/zookeeper` |

> Leader wird automatisch per Election gewählt – kein fixer Leader-Node.

### ZK IDs (myid)

| Node | myid |
|------|------|
| NUC1 | 1 |
| NUC2 | 2 |
| NUC3 | 3 |

### zoo.cfg

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

### JVM Optionen

```bash
# In zookeeper-env.sh:
export JVMFLAGS="-Xms1g -Xmx1g"
```

---

## 2. Apache Solr Cloud (5 Nodes)

**Nodes:** NUC1 - NUC5 (alle Nodes)

Solr Cloud läuft verteilt auf allen 5 NUCs für maximale Suchleistung.

### Konfiguration

| Parameter | Wert |
|-----------|------|
| Port | 8983 |
| Heap | 8 GB pro Node |
| Data Dir | `/data/solr` |
| ZK Connect | `nuc1:2181,nuc2:2181,nuc3:2181` |

### Solr starten (Cloud Mode)

```bash
bin/solr start -c -z nuc1:2181,nuc2:2181,nuc3:2181 -m 8g
```

### solr.in.sh

```bash
SOLR_HEAP="8g"
SOLR_HOME="/data/solr"
ZK_HOST="nuc1:2181,nuc2:2181,nuc3:2181"
SOLR_OPTS="$SOLR_OPTS -Dsolr.autoSoftCommit.maxTime=3000"
```

### Default Collection erstellen

```bash
bin/solr create_collection -c default \
  -shards 4 \
  -replicationFactor 2 \
  -maxShardsPerNode 2 \
  -autoAddReplicas true
```

| Parameter | Wert | Beschreibung |
|-----------|------|--------------|
| numShards | 4 | Anzahl der Shards |
| replicationFactor | 2 | Jeder Shard hat 2 Kopien |
| maxShardsPerNode | 2 | Max. 2 Shards pro Node |
| autoAddReplicas | true | Auto-Recovery bei Node-Ausfall |

### Collection Status prüfen

```bash
curl "http://nuc1:8983/solr/admin/collections?action=CLUSTERSTATUS"
```

---

## 3. Apache Spark (1 Master + 3 Worker)

**Master:** NUC2  
**Workers:** NUC3, NUC4, NUC5

> **Wichtig:** Keine Spark Worker auf NUC1 (Monitoring) und NUC2 (Master).

### Spark Master (NUC2)

| Parameter | Wert |
|-----------|------|
| Port | 7077 |
| Web UI | 8080 |
| Heap | 2 GB |

**spark-env.sh (NUC2):**
```bash
export SPARK_MASTER_HOST=nuc2
export SPARK_MASTER_PORT=7077
export SPARK_MASTER_WEBUI_PORT=8080
export SPARK_DAEMON_MEMORY=2g
```

### Spark Worker (NUC3-NUC5)

| Parameter | Wert |
|-----------|------|
| Executor Memory | 8 GB |
| Executors pro Node | 2 |
| Cores pro Executor | 2 |
| Web UI | 8081 |
| Data Dir | `/data/spark` |

**spark-env.sh (Worker Nodes):**
```bash
export SPARK_WORKER_MEMORY=16g
export SPARK_WORKER_CORES=4
export SPARK_WORKER_DIR=/data/spark
export SPARK_LOCAL_DIRS=/data/spark
```

### spark-defaults.conf (alle Nodes)

```properties
spark.master=spark://nuc2:7077
spark.executor.memory=8g
spark.executor.cores=2
spark.driver.memory=2g
spark.local.dir=/data/spark
spark.eventLog.enabled=true
spark.eventLog.dir=/data/spark/events
```

### Cluster starten

```bash
# Auf NUC2 (Master):
$SPARK_HOME/sbin/start-master.sh

# Auf NUC3, NUC4, NUC5 (Worker):
$SPARK_HOME/sbin/start-worker.sh spark://nuc2:7077
```

### Test-Job ausführen

```bash
spark-submit --master spark://nuc2:7077 \
  --class org.apache.spark.examples.SparkPi \
  $SPARK_HOME/examples/jars/spark-examples*.jar 100
```

---

## 4. Ressourcen-Aufteilung (32 GB RAM pro Node)

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

> **Hinweis:** `CPUQuota=100%` entspricht 1 CPU-Core. Bei 4-Core-NUCs bedeutet `CPUQuota=200%` = 2 Cores.

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

> Solr und Spark Worker teilen sich so die 4 Cores fair (je 2 Cores max).

---

## 5. Ressourcen-Isolation: Solr vs. Spark

### Strategie 1: Zeitliche Trennung (Empfohlen für Demos)
- Spark-Jobs nur außerhalb von Solr-Lastspitzen
- Scheduling über Cron/Airflow

### Strategie 2: Systemd Resource Control (siehe oben)
- Harte Limits für Memory und CPU
- Beide Services können parallel laufen

### Strategie 3: Dedizierte Nodes
- NUC1: Nur Solr + Monitoring (kein Spark)
- NUC3-5: Primär Spark, Solr als Sekundär

---

## 6. Storage-Layout

| Verzeichnis | Zweck | Nodes |
|-------------|-------|-------|
| `/data/solr` | Solr Index | Alle |
| `/data/spark` | Spark Shuffle/Spill/Events | NUC2-NUC5 |
| `/data/zookeeper` | ZK Data + Snapshots | NUC1-NUC3 |

### Verzeichnisse erstellen

```bash
sudo mkdir -p /data/solr /data/spark /data/zookeeper
sudo chown -R cloudadmin:cloudadmin /data
```

---

## 7. Port-Übersicht

| Service | Port | Nodes |
|---------|------|-------|
| ZooKeeper Client | 2181 | NUC1, NUC2, NUC3 |
| ZooKeeper Follower | 2888 | NUC1, NUC2, NUC3 |
| ZooKeeper Election | 3888 | NUC1, NUC2, NUC3 |
| Solr | 8983 | Alle |
| Spark Master | 7077 | NUC2 |
| Spark Master UI | 8080 | NUC2 |
| Spark Worker UI | 8081 | NUC3, NUC4, NUC5 |
| Solr JMX Exporter | 9404 | Alle |
| Spark JMX Exporter | 9405 | NUC2-NUC5 |
| ZooKeeper JMX Exporter | 9406 | NUC1-NUC3 |

---

## 8. Smoke Tests

```bash
# ZooKeeper Health Check
echo ruok | nc nuc1 2181
echo ruok | nc nuc2 2181
echo ruok | nc nuc3 2181

# ZooKeeper Cluster Status
echo srvr | nc nuc1 2181

# Solr System Info
curl http://nuc1:8983/solr/admin/info/system

# Solr Cluster Status
curl "http://nuc1:8983/solr/admin/collections?action=CLUSTERSTATUS"

# Spark Master UI
curl http://nuc2:8080

# Spark REST API
curl http://nuc2:6066/v1/submissions/status
```

---

## 9. Troubleshooting

### ZooKeeper Logs

```bash
tail -f /opt/zookeeper/logs/zookeeper-*.out
```

### Solr Logs

```bash
tail -f /opt/solr/server/logs/solr.log
```

### Spark Logs

```bash
# Master
tail -f /opt/spark/logs/spark-*-master-*.out

# Worker
tail -f /opt/spark/logs/spark-*-worker-*.out
```

### Häufige Probleme

| Problem | Lösung |
|---------|--------|
| ZK Election hängt | Prüfe Firewall für Ports 2888/3888 |
| Solr kann ZK nicht erreichen | Prüfe /etc/hosts und Netzwerk |
| Spark Worker verbindet nicht | Prüfe spark://nuc2:7077 erreichbar |
| OOM bei Spark Jobs | Reduziere executor.memory oder Parallelität |

---

*Zurück zur [Hauptdokumentation](README.md)*
