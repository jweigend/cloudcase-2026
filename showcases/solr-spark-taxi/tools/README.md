# Prometheus Tools

Tools für die Analyse und Transformation von Prometheus-Metriken.

## 1. Prometheus Metrics to CSV Exporter

**Script:** `prometheus_metrics_to_csv.py`

Exportiert alle Prometheus-Metriken als filterbare CSV-Matrix für Analyse in Excel/LibreOffice.

### Features

- **Vollständige Metrik-Extraktion**: Alle Zeitreihen mit allen Labels
- **Aggregierte Darstellung**: Zeigt Label-Kardinalität und Beispielwerte
- **Filterbare Matrix**: Eine Zeile pro Metrik+Label Kombination

### Usage

```bash
# Standard (Cluster Prometheus auf node0)
python prometheus_metrics_to_csv.py

# Lokaler Prometheus
python prometheus_metrics_to_csv.py --url http://localhost:9090

# Eigener Dateiname
python prometheus_metrics_to_csv.py --output meine_metriken.csv
```

### Output-Spalten

| Spalte | Beschreibung |
|--------|--------------|
| `metric_name` | Prometheus Metrikname |
| `_type` | Metriktyp (counter, gauge, histogram) |
| `job` | Job-Label (Process Group) |
| `instance` | Instance-Label (Process) |
| `label` | Name des Labels |
| `count` | Anzahl unterschiedlicher Werte |
| `values` | Beispielwerte (max 2) + ... |

### Beispiel-Output

```csv
metric_name,_type,job,instance,label,count,values
node_cpu_seconds_total,counter,node,"node0:9100, node1:9100, ...",cpu,8,0, 1, ...
node_cpu_seconds_total,counter,node,"node0:9100, node1:9100, ...",mode,8,idle, iowait, ...
jvm_memory_bytes_used,gauge,"solr, spark-master, ...","node0:9405, node1:9404, ...",area,2,heap, nonheap
```

---

## 2. Prometheus to Dimensional Model Transformer

**Script:** `prometheus_to_dimensional.py`

Transformiert Prometheus-Metriken automatisch in ein fixes dimensionales Schema für Data Warehousing.

### Target Structure

Jede Metrik wird auf 6 Dimensionen abgebildet:

| Dimension | Quelle | Beispiel |
|-----------|--------|----------|
| **ProcessGroup** | `job` Label | `solr`, `spark-master`, `node` |
| **Process** | `instance` Label | `node0.cloud.local:9405` |
| **HostGroup** | Konstante | `cluster` |
| **Host** | Erster Teil von `instance` | `node0` |
| **MetricGroup** | `job` + optionale Erweiterung | `solr_metrics_core` |
| **Metric** | Metrikname + Label-Suffix | `query_errors_total_type_parse` |

### Intelligente MetricGroup-Erweiterung

Bei Metriken mit vielen Label-Varianten (>threshold) wird automatisch ein Präfix vom Metriknamen in die MetricGroup verschoben:

```
Beispiel: solr_metrics_core_query_errors_total (200 Varianten)
→ MetricGroup: solr_metrics_core
→ Metric: query_errors_total
```

### Usage

```bash
# Standard (threshold=100)
python prometheus_to_dimensional.py

# Eigener Threshold
python prometheus_to_dimensional.py --threshold 50

# Eigene URL und Output
python prometheus_to_dimensional.py --url http://localhost:9090 --output my_model.csv
```

### Output-Format (CSV)

```csv
ProcessGroup,Process,HostGroup,Host,MetricGroup,Metric
node,node0.cloud.local:9100,cluster,node0,node,cpu_seconds_total_cpu_0_mode_idle
node,node0.cloud.local:9100,cluster,node0,node,cpu_seconds_total_cpu_0_mode_system
solr,node0.cloud.local:9405,cluster,node0,solr_metrics_core,query_errors_total_type_parse
spark-master,node0.cloud.local:8080,cluster,node0,spark,driver_jvm_heap_used
```

---

## Konzept-Dokumentation

Siehe [docs/CONCEPT-prometheus-mapping.md](../docs/CONCEPT-prometheus-mapping.md) für Details zur Architektur und Design-Entscheidungen.

## Known Prefixes (Cloudkoffer)

| Prefix | Source | Metrics |
|--------|--------|---------|
| `node_` | Node Exporter | CPU, Memory, Disk, Network |
| `jvm_` | JMX Exporter | Heap, GC, Threads |
| `process_` | JMX Exporter | Process stats |
| `solr_` | Solr Exporter | Queries, Cache, Index |
| `spark_` | Spark metrics | Jobs, Stages, Executors |
| `zk_` | ZooKeeper | Connections, Latency |
| `go_` | Go runtime | Prometheus/Grafana internals |
| `promhttp_` | Prometheus | Scrape metrics |

---

# Prometheus Metrics to CSV Exporter

Exportiert alle Prometheus-Metriken als filterbare CSV-Matrix.

## Features

- **Vollständige Metrik-Extraktion**: Alle Zeitreihen mit allen Labels
- **Automatische Kategorisierung**: Prozess, Kategorie, Host werden abgeleitet
- **Filterbare Matrix**: Jede Zeile = eine Metrik-Instanz, jede Spalte = ein Label

## Usage

```bash
# Standard (Cluster Prometheus auf node0)
python prometheus_metrics_to_csv.py

# Lokaler Prometheus
python prometheus_metrics_to_csv.py --url http://localhost:9090

# Eigener Dateiname
python prometheus_metrics_to_csv.py --output meine_metriken.csv
```

## Output-Spalten

| Spalte | Beschreibung |
|--------|--------------|
| `metric_name` | Prometheus Metrikname |
| `_type` | Prometheus Metriktyp (counter, gauge, histogram) |
| `label` | Name des Labels |
| `count` | Anzahl unterschiedlicher Werte |
| `values` | 2 Beispielwerte + ... |

## Beispiel-Output

```csv
metric_name,_type,label,count,values
node_cpu_seconds_total,counter,job,1,node
node_cpu_seconds_total,counter,instance,5,node0:9100, node1:9100, ...
node_cpu_seconds_total,counter,cpu,8,0, 1, ...
node_cpu_seconds_total,counter,mode,8,idle, iowait, ...
jvm_memory_bytes_used,gauge,job,3,solr, spark-master, ...
jvm_memory_bytes_used,gauge,instance,5,node0:9405, node1:9404, ...
jvm_memory_bytes_used,gauge,area,2,heap, nonheap
```

**Eine Zeile pro Metrik+Label Kombination** - zeigt Kardinalität und Beispielwerte.
Hilfreich um zu verstehen welche Labels Dimensionen (viele Werte) vs. Metrik-Varianten (wenige, beschreibende Werte) sind.
