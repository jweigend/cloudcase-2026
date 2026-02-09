# Cloudkoffer 2026

Ein portabler Big Data Cluster auf 5 Intel NUCs für Demos, Workshops und Entwicklung.

<img src="docs/images/Cloudkoffer-2026.PNG" alt="Cloudkoffer NUC Cluster" width="400">

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
│   └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘           │
│        └───────────┴───────────┴───────────┴───────────┘                │
│                          Gigabit Switch                                 │
│                               │                                         │
│                     ┌─────────┴─────────┐                               │
│                     │    EdgeRouter X   │──── Internet                  │
│                     └───────────────────┘                               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Was ist das?

Der **Cloudkoffer** ist ein kompletter Big Data Stack in einem transportablen Koffer:

- **5 Intel NUCs** mit je 32 GB RAM, 4 Cores, NVMe SSD
- **EdgeRouter X** für Netzwerk und DHCP
- **Gigabit Switch** für interne Kommunikation

### Technologie-Stack

| Kategorie | Komponenten |
|-----------|-------------|
| **Datenverarbeitung** | Apache Solr, Apache Spark, ZooKeeper |
| **Monitoring** | Prometheus, Grafana, Node Exporter |
| **Demo-App** | NYC Taxi Explorer (Vue.js + Flask) |
| **Infrastruktur** | Ubuntu 24.04, Cloud-Init, Ansible |

### Einsatzzwecke

- 📊 **Demos** - Big Data Technologien live zeigen
- 🎓 **Workshops** - Hands-on Training ohne Cloud-Abhängigkeit  
- 🧪 **Entwicklung** - Lokaler Cluster für Tests
- 🏢 **Offline-Umgebungen** - Funktioniert ohne Internet

---

## Quick Start

```bash
# 1. Cluster aufsetzen (siehe Setup Guide)
cd baremetal/05-ansible
ansible-playbook -i inventory.yml site.yml

# 2. Validieren
./baremetal/09-smoke-tests/smoke-tests.sh

# 3. Services nutzen
open http://node0.cloud.local:3000   # Grafana
open http://node0.cloud.local:8888   # JupyterLab
open http://node0.cloud.local/       # NYC Taxi Explorer
```

---

## Dokumentation

| Dokument | Inhalt |
|----------|--------|
| **[docs/SETUP-GUIDE.md](docs/SETUP-GUIDE.md)** | Komplette Installationsanleitung |
| **[docs/REFERENCE.md](docs/REFERENCE.md)** | IPs, Ports, Versionen, Credentials |
| **[README-NYC-TAXI-EXPLORER.md](README-NYC-TAXI-EXPLORER.md)** | Die Demo-Webapp erklärt |
| **[docs/ARTICLE-drill-down-architecture.md](docs/ARTICLE-drill-down-architecture.md)** | Architektur Deep-Dive |

---

## Warum kein Kubernetes?

| Aspekt | Kubernetes | Unser Ansatz |
|--------|------------|--------------|
| **Komplexität** | Control Plane, etcd, CNI, ... | Direkter Zugriff auf Services |
| **Ressourcen** | ~2-4 GB RAM für K8s selbst | Alles für Solr/Spark verfügbar |
| **Debugging** | Pod-Logs, kubectl | SSH + journalctl |
| **Lernkurve** | Steil | Linux-Basics reichen |

> *"Use the simplest thing that could possibly work."* - Ward Cunningham

---

## Lizenz

MIT License - siehe [LICENSE](LICENSE) | © 2026 Johannes Weigend, Weigend AM
