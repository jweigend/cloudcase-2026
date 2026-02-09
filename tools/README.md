# Prometheus Metric Mapper Tool

Maps Prometheus metrics to a structured dimensional model for data warehousing/analytics.

## Target Structure

Each metric is mapped to these dimensions:

| Dimension | Description | Example |
|-----------|-------------|---------|
| **HOSTGROUP** | Cluster/Environment name | `Democluster` |
| **HOST** | Individual node | `node0` |
| **METRICGROUP** | Category of metrics | `jvm`, `node`, `spark` |
| **METRIC** | Specific metric name | `heap_memory_used` |
| **PROCESSGROUP** | Application type | `zookeeper`, `spark` |
| **PROCESS** | Process identifier | `java`, `master` |
| **MEASUREMENT** | Role/Instance type | `master`, `worker` |

## Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Run against cluster (default URL: http://node0.cloud.local:9090)
python prometheus_mapper.py

# Custom Prometheus URL
python prometheus_mapper.py --url http://localhost:9090

# Specify output file
python prometheus_mapper.py --output my_mapping.yaml

# Continue from existing rules (learned patterns are preserved)
python prometheus_mapper.py --rules prometheus_mapping.yaml
```

## Interactive Mode

The tool groups metrics by prefix and asks you to create mapping rules:

1. **Wildcard rules**: Create one rule for many similar metrics (e.g., `node_*`)
2. **Individual rules**: Map specific metrics one by one
3. **Skip**: Ignore metric groups you don't need

### Mapping Sources

For each dimension, you can specify:

- **constant**: Fixed value (e.g., `Democluster`)
- **label**: Extract from Prometheus label (e.g., `instance`, `job`)
- **substring**: Part of the metric name
- **regex**: Pattern matching on metric name
- **concat**: Combine multiple sources
- **transform**: Apply transformation (e.g., `extract_host` removes port from `node0:9100`)

## Output Format (YAML)

```yaml
version: '1.0'
description: Prometheus metric mapping rules
target_structure:
  dimensions:
    - HOSTGROUP
    - HOST
    - METRICGROUP
    - METRIC
    - PROCESSGROUP
    - PROCESS
    - MEASUREMENT

rules:
  - pattern: node_*
    hostgroup: Democluster
    host:
      label: instance
      transform: extract_host
    metricgroup: node
    metric:
      source: metric_name
      remove_prefix: node_
    processgroup: system
    process:
      label: job
    measurement: null

  - pattern: jvm_*
    label_conditions:
      job: spark-master
    hostgroup: Democluster
    host:
      label: instance
      transform: extract_host
    metricgroup: jvm
    metric:
      source: metric_name
      remove_prefix: jvm_
    processgroup: spark
    process: java
    measurement: master
```

## Wildcards

The `pattern` field supports `*` wildcards:

- `node_*` - All metrics starting with `node_`
- `*_total` - All counter metrics
- `jvm_memory_*` - Specific subset

## Label Conditions

Filter rules by label values:

```yaml
- pattern: jvm_*
  label_conditions:
    job: spark-master
  measurement: master

- pattern: jvm_*
  label_conditions:
    job: spark-worker
  measurement: worker
```

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
