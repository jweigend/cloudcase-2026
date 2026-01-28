# Monitoring Setup - Prometheus & Grafana

Diese Dokumentation beschreibt das Monitoring-Setup für den Cloudkoffer-Cluster mit Prometheus und Grafana.

---

## Übersicht

Das Monitoring läuft zentralisiert auf **NUC1** und überwacht alle 5 Nodes des Clusters.

| Komponente | Port | Beschreibung |
|------------|------|--------------|
| Prometheus | 9090 | Metrics Collection & Storage |
| Grafana | 3000 | Dashboards & Visualisierung |
| Node Exporter | 9100 | System-Metriken (alle Nodes) |
| JMX Exporter | 9404-9406 | Java-Applikations-Metriken |

---

## Prometheus

**Node:** NUC1  
**Port:** 9090  
**Data Dir:** `/data/prometheus`

### Konfiguration

| Parameter | Wert |
|-----------|------|
| Scrape-Intervall | 15s |
| Evaluation-Intervall | 15s |
| Retention | 15 Tage |
| Storage | `/data/prometheus` |

### prometheus.yml

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  # Node Exporter - System Metrics (alle Nodes)
  - job_name: 'node'
    static_configs:
      - targets:
        - 'nuc1:9100'
        - 'nuc2:9100'
        - 'nuc3:9100'
        - 'nuc4:9100'
        - 'nuc5:9100'

  # Solr JMX Exporter (alle Nodes)
  - job_name: 'solr'
    static_configs:
      - targets:
        - 'nuc1:9404'
        - 'nuc2:9404'
        - 'nuc3:9404'
        - 'nuc4:9404'
        - 'nuc5:9404'

  # Spark JMX Exporter (Master + Worker)
  - job_name: 'spark'
    static_configs:
      - targets:
        - 'nuc2:9405'
        - 'nuc3:9405'
        - 'nuc4:9405'
        - 'nuc5:9405'

  # ZooKeeper JMX Exporter
  - job_name: 'zookeeper'
    static_configs:
      - targets:
        - 'nuc1:9406'
        - 'nuc2:9406'
        - 'nuc3:9406'
```

### Prometheus starten

```bash
# Als Systemd Service
sudo systemctl start prometheus
sudo systemctl enable prometheus

# Oder manuell
/opt/prometheus/prometheus \
  --config.file=/opt/prometheus/prometheus.yml \
  --storage.tsdb.path=/data/prometheus \
  --storage.tsdb.retention.time=15d \
  --web.listen-address=0.0.0.0:9090
```

### Systemd Service

```ini
# /etc/systemd/system/prometheus.service
[Unit]
Description=Prometheus
After=network.target

[Service]
Type=simple
User=cloudadmin
ExecStart=/opt/prometheus/prometheus \
  --config.file=/opt/prometheus/prometheus.yml \
  --storage.tsdb.path=/data/prometheus \
  --storage.tsdb.retention.time=15d \
  --web.listen-address=0.0.0.0:9090
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

---

## Grafana

**Node:** NUC1  
**Port:** 3000  
**Default Login:** admin / admin

### Konfiguration

```ini
# /etc/grafana/grafana.ini
[server]
http_port = 3000
root_url = http://nuc1:3000

[security]
admin_user = admin
admin_password = admin

[paths]
data = /var/lib/grafana
logs = /var/log/grafana
```

### Prometheus Datasource hinzufügen

1. Grafana öffnen: `http://nuc1:3000`
2. Configuration → Data Sources → Add data source
3. Prometheus auswählen
4. URL: `http://localhost:9090`
5. Save & Test

### Empfohlene Dashboards

| Dashboard | Grafana ID | Beschreibung |
|-----------|------------|--------------|
| Node Exporter Full | 1860 | System-Metriken |
| Solr Dashboard | 2551 | Solr Cloud Metriken |
| Spark Dashboard | 7890 | Spark Cluster Metriken |
| ZooKeeper Dashboard | 10465 | ZooKeeper Ensemble |

**Dashboard importieren:**
1. Grafana → + → Import
2. ID eingeben (z.B. 1860)
3. Prometheus Datasource auswählen
4. Import

---

## Node Exporter

Node Exporter sammelt System-Metriken und läuft auf **allen 5 Nodes**.

**Port:** 9100

### Installation (alle Nodes)

```bash
# Download
wget https://github.com/prometheus/node_exporter/releases/download/v1.7.0/node_exporter-1.7.0.linux-amd64.tar.gz
tar -xzf node_exporter-1.7.0.linux-amd64.tar.gz
sudo mv node_exporter-1.7.0.linux-amd64/node_exporter /usr/local/bin/

# Systemd Service erstellen
sudo tee /etc/systemd/system/node_exporter.service << EOF
[Unit]
Description=Node Exporter
After=network.target

[Service]
Type=simple
User=cloudadmin
ExecStart=/usr/local/bin/node_exporter
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# Starten
sudo systemctl daemon-reload
sudo systemctl enable node_exporter
sudo systemctl start node_exporter
```

### Verfügbare Metriken

- CPU: `node_cpu_seconds_total`
- Memory: `node_memory_MemAvailable_bytes`
- Disk: `node_filesystem_avail_bytes`
- Network: `node_network_receive_bytes_total`

---

## JMX Exporter

JMX Exporter exportiert Java-Metriken für Prometheus.

### Ports

| Service | JMX Exporter Port | Nodes |
|---------|-------------------|-------|
| Solr | 9404 | Alle (NUC1-NUC5) |
| Spark | 9405 | NUC2-NUC5 |
| ZooKeeper | 9406 | NUC1-NUC3 |

### JMX Exporter für Solr

```bash
# Download
wget https://repo1.maven.org/maven2/io/prometheus/jmx/jmx_prometheus_javaagent/0.20.0/jmx_prometheus_javaagent-0.20.0.jar

# In solr.in.sh hinzufügen:
SOLR_OPTS="$SOLR_OPTS -javaagent:/opt/jmx_exporter/jmx_prometheus_javaagent-0.20.0.jar=9404:/opt/jmx_exporter/solr.yml"
```

**solr.yml (JMX Config):**
```yaml
lowercaseOutputName: true
lowercaseOutputLabelNames: true
rules:
  - pattern: "solr<dom=(\\w+), category=(\\w+), scope=(\\w+), name=(\\w+)><>(\\w+)"
    name: solr_$1_$2_$3_$4_$5
    type: GAUGE
```

### JMX Exporter für Spark

```bash
# In spark-env.sh hinzufügen:
export SPARK_DAEMON_JAVA_OPTS="-javaagent:/opt/jmx_exporter/jmx_prometheus_javaagent-0.20.0.jar=9405:/opt/jmx_exporter/spark.yml"
```

**spark.yml (JMX Config):**
```yaml
lowercaseOutputName: true
lowercaseOutputLabelNames: true
rules:
  - pattern: "metrics<name=(.*)><>(\\w+)"
    name: spark_$1_$2
    type: GAUGE
```

### JMX Exporter für ZooKeeper

```bash
# In zookeeper-env.sh hinzufügen:
SERVER_JVMFLAGS="-javaagent:/opt/jmx_exporter/jmx_prometheus_javaagent-0.20.0.jar=9406:/opt/jmx_exporter/zookeeper.yml $SERVER_JVMFLAGS"
```

**zookeeper.yml (JMX Config):**
```yaml
lowercaseOutputName: true
lowercaseOutputLabelNames: true
rules:
  - pattern: "org.apache.ZooKeeperService<name0=(\\w+), name1=(\\w+), name2=(\\w+)><>(\\w+)"
    name: zookeeper_$4
    type: GAUGE
    labels:
      server: "$1"
      member: "$2"
```

---

## Port-Übersicht (Monitoring)

| Service | Port | Nodes |
|---------|------|-------|
| Prometheus | 9090 | NUC1 |
| Grafana | 3000 | NUC1 |
| Node Exporter | 9100 | Alle |
| Solr JMX Exporter | 9404 | Alle |
| Spark JMX Exporter | 9405 | NUC2-NUC5 |
| ZooKeeper JMX Exporter | 9406 | NUC1-NUC3 |

---

## Smoke Tests

```bash
# Prometheus Ready Check
curl http://nuc1:9090/-/ready

# Prometheus Targets Status
curl http://nuc1:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# Grafana Health
curl http://nuc1:3000/api/health

# Node Exporter (jeder Node)
curl http://nuc1:9100/metrics | head -20

# JMX Exporter (Solr auf NUC1)
curl http://nuc1:9404/metrics | head -20
```

---

## Alerting (Optional)

### Alertmanager

```yaml
# alertmanager.yml
global:
  smtp_smarthost: 'localhost:25'
  smtp_from: 'alertmanager@cloudkoffer.local'

route:
  receiver: 'default'

receivers:
  - name: 'default'
    email_configs:
      - to: 'admin@example.com'
```

### Alert Rules (Prometheus)

```yaml
# alerts.yml
groups:
  - name: cloudkoffer
    rules:
      - alert: NodeDown
        expr: up{job="node"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Node {{ $labels.instance }} ist down"

      - alert: HighMemoryUsage
        expr: (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Hohe Memory-Auslastung auf {{ $labels.instance }}"

      - alert: SolrDown
        expr: up{job="solr"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Solr auf {{ $labels.instance }} ist down"
```

---

## Troubleshooting

### Prometheus

```bash
# Logs prüfen
journalctl -u prometheus -f

# Config validieren
/opt/prometheus/promtool check config /opt/prometheus/prometheus.yml

# Targets prüfen
curl http://nuc1:9090/api/v1/targets
```

### Grafana

```bash
# Logs prüfen
journalctl -u grafana-server -f
tail -f /var/log/grafana/grafana.log

# Datasource Test
curl -u admin:admin http://nuc1:3000/api/datasources
```

### Node Exporter

```bash
# Metriken prüfen
curl http://localhost:9100/metrics | grep node_cpu

# Service Status
systemctl status node_exporter
```

---

*Zurück zur [Hauptdokumentation](README-SETUP.md)*
