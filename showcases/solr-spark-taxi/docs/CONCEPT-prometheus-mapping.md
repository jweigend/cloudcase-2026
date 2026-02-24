# Konzept: Prometheus → Dimensionales Modell

## Problem

Prometheus speichert Metriken als flache Key-Value-Paare mit Labels. Das führt zu:
- **Inkonsistenten Namenskonventionen** (node_*, jvm_*, solr_metrics_*, ...)
- **Labels mit doppelter Bedeutung** (mal Dimensionen, mal Metrik-Varianten)
- **Fehlender Hierarchie** (kein Schema, keine Gruppierung)

## Ziel

Transformation in ein **fixes dimensionales Modell**:

```
ProcessGroup | Process | HostGroup | Host | MetricGroup | Metric
```

**WICHTIG:** Das Schema ist fix. Keine zusätzlichen Spalten möglich!

## Label-Klassifikation

### 1. STANDARD Labels (→ ProcessGroup, Process, Host)
```
job      → ProcessGroup (1:1)
instance → Process (vollständige URL) UND Host (erster Teil vor dem Punkt)
```

### 2. ANDERE Labels (→ Metric)
ALLE anderen Labels werden alphabetisch sortiert und an den Metriknamen angehängt:
```
Format: base_labelname1_value1_labelname2_value2_...

Beispiele:
cpu="0", mode="idle"           → cpu_seconds_total_cpu_0_mode_idle
area="heap"                    → memory_bytes_used_area_heap
category="QUERY", internal="false", shard="shard1" → errors_total_category_QUERY_internal_false_shard_shard1
```

### 3. IGNORIEREN Labels
Redundante Labels die weggelassen werden:
```
base_url    # redundant zu instance
cluster_id  # konstant pro Cluster
core        # redundant (enthält collection+shard+replica)
fstype      # meist irrelevant
```

### 4. HISTOGRAM Labels (Spezialfall)
```
quantile # 0.5, 0.9, 0.99 → Suffix _p50, _p90, _p99 (statt _quantile_0.5)
le       # Bucket-Grenzen → ignorieren (nur _sum/_count verwenden)
```

### 5. INFO Metriken (Komplett ignorieren)
```
*_info   # node_uname_info, node_os_info, etc.
```

---

## Mapping-Regeln

### MetricGroup: Job + dynamische Erweiterung

**Basis-Regel:**
```
MetricGroup = job (1:1)
```

**Erweiterung bei vielen Label-Varianten (rekursiv):**
Wenn ein Präfix viele Label-Kombinationen (>100 Varianten) hat, werden Teile des Metriknamens in die MetricGroup verschoben. Dies geschieht **rekursiv** bis der Präfix unter dem Threshold liegt:

```
Wenn prefix_count > threshold:
    MetricGroup = job + "_" + nächster_teil
    → Prüfe erneut ob neuer Präfix > threshold
    → Wiederhole bis unter threshold
```

**Beispiel rekursive Erweiterung (threshold=100):**
```
solr/metrics           → 35909 Varianten > 100 → erweitern
solr/metrics_core      → 35197 Varianten > 100 → erweitern  
solr/metrics_core_query → 11510 Varianten > 100 → erweitern
solr/metrics_core_query_errors → 1070 Varianten > 100 → erweitern
solr/metrics_core_query_errors_1minRate → 80 < 100 → STOP

Ergebnis: MetricGroup = solr_metrics_core_query_errors
          Metric = 1minRate_...
```

| Metrik | Varianten | MetricGroup |
|--------|-----------|-------------|
| `solr_metrics_core_query_errors_total` | >1000 | `solr_metrics_core_query_errors` |
| `solr_metrics_core_searcher_cache` | >400 | `solr_metrics_core_searcher` |
| `node_cpu_seconds_total` | >300 | `node_cpu_seconds` |
| `node_memory_bytes` | <100 | `node` |
| `jvm_memory_bytes_used` | <100 | `spark` (=job) |
| `avg_latency` | <100 | `zookeeper` (=job) |

### Metric: Metrikname + Labels

**Job-Präfix entfernen:**
Wenn der Metrikname mit `job + "_"` beginnt, wird das Präfix entfernt:
```
solr_metrics_core_errors (job=solr) → metrics_core_errors
node_cpu_seconds_total (job=node)  → cpu_seconds_total
avg_latency (job=zookeeper)        → avg_latency (kein Präfix)
```

**Labels anhängen:**
```
Metric = BaseName + "_" + label1_value1 + "_" + label2_value2 + ...
```

Labels werden alphabetisch nach Label-Namen sortiert und mit Unterstrich verkettet.

| Prometheus Metrik | job | Metric |
|-------------------|-----|--------|
| `node_cpu_seconds_total{cpu="0", mode="idle"}` | node | `seconds_total_cpu_0_mode_idle` |
| `jvm_memory_bytes_used{area="heap"}` | spark | `jvm_memory_bytes_used_area_heap` |
| `solr_metrics_core_errors_total{category="QUERY", ...}` | solr | `errors_total_category_QUERY_...` |
| `avg_latency{}` | zookeeper | `avg_latency` |

### ProcessGroup: Job Label (1:1)

```
ProcessGroup = job
```

### Process: Instance URL (1:1)

```
Process = instance (vollständig, z.B. "node1.cloud.local:9100")
```

### Host: Extrahierter Hostname

```
Host = instance.split('.')[0]  (z.B. "node1")
```

### HostGroup: Konstant

```
HostGroup = "cluster"
```

---

## Beispiele

### Beispiel 1: node_cpu_seconds_total

**Prometheus:**
```
node_cpu_seconds_total{cpu="0", instance="node1.cloud.local:9100", job="node", mode="idle"} 123456.78
node_cpu_seconds_total{cpu="0", instance="node1.cloud.local:9100", job="node", mode="user"} 45678.90
node_cpu_seconds_total{cpu="1", instance="node1.cloud.local:9100", job="node", mode="idle"} 123000.00
```

**Klassifikation:**
- STANDARD: job, instance
- ANDERE: cpu, mode → Metric (alphabetisch)

**Mapping:**
| ProcessGroup | Process | HostGroup | Host | MetricGroup | Metric |
|--------------|---------|-----------|------|-------------|--------|
| node | node1.cloud.local:9100 | cluster | node1 | node | cpu_seconds_total_cpu_0_mode_idle |
| node | node1.cloud.local:9100 | cluster | node1 | node | cpu_seconds_total_cpu_0_mode_user |
| node | node1.cloud.local:9100 | cluster | node1 | node | cpu_seconds_total_cpu_1_mode_idle |

---

### Beispiel 2: jvm_memory_bytes_used

**Prometheus:**
```
jvm_memory_bytes_used{area="heap", instance="node0.cloud.local:9404", job="spark"} 268435456
jvm_memory_bytes_used{area="nonheap", instance="node0.cloud.local:9404", job="spark"} 67108864
```

**Klassifikation:**
- STANDARD: job, instance
- ANDERE: area → Metric
- Metrikname beginnt NICHT mit job → kein Präfix entfernen

**Mapping:**
| ProcessGroup | Process | HostGroup | Host | MetricGroup | Metric |
|--------------|---------|-----------|------|-------------|--------|
| spark | node0.cloud.local:9404 | cluster | node0 | spark | jvm_memory_bytes_used_area_heap |
| spark | node0.cloud.local:9404 | cluster | node0 | spark | jvm_memory_bytes_used_area_nonheap |

---

### Beispiel 3: solr_metrics_core_errors_total (komplex)

**Prometheus:**
```
solr_metrics_core_errors_total{
  base_url="http://node1.cloud.local:8983/solr",
  category="QUERY",
  cluster_id="...",
  collection="nyc_taxi",
  core="nyc_taxi_shard1_replica_n1",
  handler="/select",
  instance="node1.cloud.local:9854",
  internal="false",
  job="solr",
  replica="replica_n1",
  shard="shard1"
} 42
```

**Klassifikation:**
- STANDARD: job, instance
- IGNORIEREN: base_url, cluster_id, core (redundant)
- ANDERE: category, collection, handler, internal, replica, shard → Metric (alphabetisch)

**Mapping:**
| ProcessGroup | Process | HostGroup | Host | MetricGroup | Metric |
|--------------|---------|-----------|------|-------------|--------|
| solr | node1.cloud.local:9854 | cluster | node1 | solr_metrics_core | errors_total_category_QUERY_collection_nyc_taxi_handler_/select_internal_false_replica_replica_n1_shard_shard1 |
| solr | node1.cloud.local:9854 | cluster | node1 | solr_metrics_core | errors_total_category_ADMIN_collection_nyc_taxi_handler_/select_internal_false_replica_replica_n1_shard_shard1 |

---

### Beispiel 4: avg_latency (einfach)

**Prometheus:**
```
avg_latency{instance="node1.cloud.local:7070", job="zookeeper"} 0.5
```

**Klassifikation:**
- STANDARD: job, instance
- ANDERE: (keine)
- Metrikname beginnt NICHT mit job → kein Präfix entfernen

**Mapping:**
| ProcessGroup | Process | HostGroup | Host | MetricGroup | Metric |
|--------------|---------|-----------|------|-------------|--------|
| zookeeper | node1.cloud.local:7070 | cluster | node1 | zookeeper | avg_latency |

---

### Beispiel 5: go_gc_duration_seconds (Histogram)

**Prometheus:**
```
go_gc_duration_seconds{instance="node0.cloud.local:9090", job="prometheus", quantile="0.5"} 0.00012
go_gc_duration_seconds{instance="node0.cloud.local:9090", job="prometheus", quantile="0.9"} 0.00045
go_gc_duration_seconds{instance="node0.cloud.local:9090", job="prometheus", quantile="0.99"} 0.00123
go_gc_duration_seconds_sum{...} 45.67
go_gc_duration_seconds_count{...} 12345
```

**Mapping (Quantile als Suffix _pXX):**
| ProcessGroup | Process | HostGroup | Host | MetricGroup | Metric |
|--------------|---------|-----------|------|-------------|--------|
| prometheus | node0.cloud.local:9090 | cluster | node0 | prometheus | go_gc_duration_seconds_p50 |
| prometheus | node0.cloud.local:9090 | cluster | node0 | prometheus | go_gc_duration_seconds_p90 |
| prometheus | node0.cloud.local:9090 | cluster | node0 | prometheus | go_gc_duration_seconds_p99 |
| prometheus | node0.cloud.local:9090 | cluster | node0 | prometheus | go_gc_duration_seconds_sum |
| prometheus | node0.cloud.local:9090 | cluster | node0 | prometheus | go_gc_duration_seconds_count |

**Quantil-Suffix-Mapping:**
| quantile | Suffix |
|----------|--------|
| 0.5 | _p50 |
| 0.75 | _p75 |
| 0.9 | _p90 |
| 0.95 | _p95 |
| 0.99 | _p99 |
| 0.999 | _p999 |

---

## Vollständiges Modell

```
┌─────────────────────────────────────────────────────────────────────────┐
│ ProcessGroup (= job Label)                                              │
│   ├── prometheus                                                        │
│   ├── grafana                                                           │
│   ├── node                                                              │
│   ├── solr                                                              │
│   ├── spark                                                             │
│   └── zookeeper                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ Process (= instance URL)                                                │
│   ├── node0.cloud.local:9090  (prometheus)                              │
│   ├── node0.cloud.local:3000  (grafana)                                 │
│   ├── node1.cloud.local:9100  (node_exporter)                           │
│   ├── node1.cloud.local:9854  (solr_exporter)                           │
│   ├── node0.cloud.local:9404  (spark)                                   │
│   └── node1.cloud.local:7070  (zk_exporter)                             │
├─────────────────────────────────────────────────────────────────────────┤
│ HostGroup                                                               │
│   └── cluster                                                           │
├─────────────────────────────────────────────────────────────────────────┤
│ Host (extrahiert aus instance)                                          │
│   ├── node0, node1, node2, node3, node4                                 │
├─────────────────────────────────────────────────────────────────────────┤
│ MetricGroup (= job, ggf. erweitert)                                     │
│   ├── node (wenige Varianten)                                           │
│   ├── node_cpu (viele Varianten → erweitert)                            │
│   ├── prometheus                                                        │
│   ├── solr (wenige Varianten)                                           │
│   ├── solr_metrics_core (viele Varianten → erweitert)                   │
│   ├── spark                                                             │
│   └── zookeeper                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│ Metric (Metrikname ohne job-Präfix + Labels)                            │
│   ├── seconds_total_cpu_0_mode_idle (node_cpu_* erweitert)              │
│   ├── jvm_memory_bytes_used_area_heap (beginnt nicht mit spark)         │
│   ├── errors_total_category_QUERY_... (solr_metrics_core erweitert)     │
│   ├── go_gc_duration_seconds_p50 (beginnt nicht mit prometheus)         │
│   └── avg_latency (beginnt nicht mit zookeeper)                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Label-Klassifikation (Zusammenfassung)

| Label | Kategorie | Ziel |
|-------|-----------|------|
| job | STANDARD | ProcessGroup |
| instance | STANDARD | Process + Host |
| alle anderen (cpu, mode, area, collection, ...) | ANDERE | Metric (als `label_value`) |
| quantile | HISTOGRAM | Metric (als `_p50`, `_p99`, ...) |
| base_url, cluster_id, core, fstype | IGNORIEREN | - |

---

## Entscheidungen

1. **`*_info` Metriken:** ✅ **Ignorieren**
   - Metriken die auf `_info` enden werden nicht gemappt
   - Beispiel: `node_uname_info`, `node_os_info` → werden übersprungen

2. **Histogram-Behandlung:** ✅ **Quantile als Suffix**
   - `quantile="0.5"` → `_p50`
   - `quantile="0.99"` → `_p99`
   - `_sum` und `_count` bleiben unverändert

3. **Multi-Job-Metriken:** Gleiche Metrik von verschiedenen Jobs
   - `jvm_*` kommt von Solr UND Spark → MetricGroup=job unterscheidet (solr vs spark)

4. **Leere Varianten:** Metriknamen ohne Suffix wenn keine Labels
   - `avg_latency` bleibt `avg_latency` (ohne Unterstrich am Ende)

---

## Implementierung

✅ **Mapping-Script:** `tools/prometheus_to_dimensional.py`

```bash
# Verwendung
python3 prometheus_to_dimensional.py --url http://prometheus:9090 --output output.csv --threshold 100

# Parameter
--url        Prometheus URL (default: http://node0.cloud.local:9090)
--output     Output CSV Datei
--threshold  Schwellwert für MetricGroup-Erweiterung (default: 100)
```

Das Skript:
1. Holt alle Metriken und Serien von Prometheus
2. Analysiert Präfix-Varianten (für alle Präfix-Längen)
3. Bestimmt **rekursiv** MetricGroup-Erweiterungen
4. Exportiert in CSV mit 6 Spalten

**Statistik (threshold=100):**
- 77 MetricGroups
- Max 2.520 Metriken pro Group
- 39.642 eindeutige Zeilen gesamt
