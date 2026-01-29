# Monitoring Setup - Prometheus & Grafana

Monitoring über Cloud-Init.

> **Cloud-Init Dateien:** [`baremetal/08-install-monitoring/`](baremetal/08-install-monitoring/)

---

## Übersicht

```
┌──────────────────────────────────────────────────────────────┐
│                      NUC1 (Monitoring)                        │
│  ┌────────────────┐     ┌────────────────┐                   │
│  │   Prometheus   │────►│    Grafana     │                   │
│  │    :9090       │     │    :3000       │                   │
│  └───────┬────────┘     └────────────────┘                   │
└──────────┼───────────────────────────────────────────────────┘
           │ scrapes
           ▼
┌──────────────────────────────────────────────────────────────┐
│  Node Exporter :9100     (alle Nodes)                        │
│  Solr JMX      :9404     (alle Nodes)                        │
│  Spark JMX     :9405     (NUC2-5)                            │
│  ZooKeeper JMX :9406     (NUC1-3)                            │
└──────────────────────────────────────────────────────────────┘
```

---

## Cloud-Init Dateien

| Datei | Node | Inhalt |
|-------|------|--------|
| cloud-init-prometheus.yaml | NUC1 | Prometheus, Grafana, Node Exporter |
| cloud-init-exporter.yaml | NUC2-5 | Node Exporter |

---

## prometheus.yml (via Cloud-Init)

```yaml
scrape_configs:
  - job_name: 'node'
    static_configs:
      - targets: ['nuc1:9100', 'nuc2:9100', 'nuc3:9100', 'nuc4:9100', 'nuc5:9100']

  - job_name: 'solr'
    static_configs:
      - targets: ['nuc1:9404', 'nuc2:9404', 'nuc3:9404', 'nuc4:9404', 'nuc5:9404']

  - job_name: 'spark'
    static_configs:
      - targets: ['nuc2:9405', 'nuc3:9405', 'nuc4:9405', 'nuc5:9405']

  - job_name: 'zookeeper'
    static_configs:
      - targets: ['nuc1:9406', 'nuc2:9406', 'nuc3:9406']
```

---

## Services starten

```bash
# NUC1: Prometheus + Grafana
ssh cloudadmin@nuc1 'sudo systemctl start prometheus node_exporter grafana-server'

# NUC2-5: Node Exporter
for node in nuc2 nuc3 nuc4 nuc5; do
    ssh cloudadmin@$node 'sudo systemctl start node_exporter'
done
```

---

## Zugriff

| Service | URL | Login |
|---------|-----|-------|
| Prometheus | http://nuc1:9090 | - |
| Grafana | http://nuc1:3000 | admin/admin |

---

## Grafana Dashboards

Import über: Dashboards → Import → ID eingeben

| Dashboard | ID | Beschreibung |
|-----------|-----|--------------|
| Node Exporter Full | 1860 | System-Metriken |
| Solr Dashboard | 2551 | Solr Cloud |
| Spark Dashboard | 7890 | Spark Cluster |

---

## Smoke Tests

```bash
cd baremetal/09-smoke-tests
./smoke-tests.sh
```

---

*Zurück zur [Hauptdokumentation](README-SETUP.md)*
