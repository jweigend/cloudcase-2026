# Monitoring Setup - Prometheus & Grafana

Monitoring über Cloud-Init.

> **Cloud-Init Dateien:** [`baremetal/08-install-monitoring/`](baremetal/08-install-monitoring/)

---

## Übersicht

```
┌──────────────────────────────────────────────────────────────┐
│                      node0 (Monitoring)                       │
│  ┌────────────────┐     ┌────────────────┐                   │
│  │   Prometheus   │────►│    Grafana     │                   │
│  │    :9090       │     │    :3000       │                   │
│  └───────┬────────┘     └────────────────┘                   │
└──────────┼───────────────────────────────────────────────────┘
           │ scrapes
           ▼
┌──────────────────────────────────────────────────────────────┐
│  Node Exporter :9100     (alle Nodes)                        │
│  Solr JMX      :9404     (node1-4)                           │
│  Spark JMX     :9405     (node0-4)                           │
│  ZooKeeper     :7070     (node1-3, Prometheus Metrics)       │
└──────────────────────────────────────────────────────────────┘
```

---

## Ansible Playbooks

| Playbook | Node | Inhalt |
|----------|------|--------|
| monitoring.yml | node0 | Prometheus, Grafana |
| prometheus-exporters.yml | Alle | Node Exporter, JMX Exporter |

---

## prometheus.yml (via Ansible)

```yaml
scrape_configs:
  - job_name: 'node'
    static_configs:
      - targets: ['node0:9100', 'node1:9100', 'node2:9100', 'node3:9100', 'node4:9100']

  - job_name: 'solr'
    static_configs:
      - targets: ['node1:9404', 'node2:9404', 'node3:9404', 'node4:9404']

  - job_name: 'spark'
    static_configs:
      - targets: ['node0:9405', 'node1:9405', 'node2:9405', 'node3:9405', 'node4:9405']

  - job_name: 'zookeeper'
    static_configs:
      - targets: ['node1:7070', 'node2:7070', 'node3:7070']
```

---

## Services starten

```bash
# Via Ansible (empfohlen)
cd baremetal/05-ansible
ansible-playbook -i inventory.yml monitoring.yml
ansible-playbook -i inventory.yml prometheus-exporters.yml

# Oder manuell auf node0
ssh cloudadmin@node0 'sudo systemctl start prometheus grafana-server'
```

---

## Zugriff

| Service | URL | Login |
|---------|-----|-------|
| Prometheus | http://node0:9090 | - |
| Grafana | http://node0:3000 | admin/admin |
| JupyterLab | http://node0:8888 | - |

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

---

## Lizenz

MIT License - siehe [LICENSE](../LICENSE) | © 2026 Johannes Weigend, Weigend AM
