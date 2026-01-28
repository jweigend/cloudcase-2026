# Cloudkoffer 2026 - Big Data Cluster Setup

## Übersicht

Dieses Projekt beschreibt das Setup eines portablen Big Data Clusters auf 5 Intel NUCs ("Cloudkoffer"). Das System kombiniert Apache Solr Cloud für Volltextsuche, Apache Spark für verteilte Datenverarbeitung, ZooKeeper für Cluster-Koordination sowie Prometheus und Grafana für Monitoring.

---

## Dokumentation

| Dokument | Beschreibung |
|----------|--------------|
| [README.md](README.md) | Übersicht, Hardware, Netzwerk, Monitoring |
| [SOLR-SPARK.md](SOLR-SPARK.md) | Solr Cloud, Spark, ZooKeeper Konfiguration |
| [BAREMETAL-SETUP.md](BAREMETAL-SETUP.md) | Ubuntu Autoinstall & Cloud-Init |

---

## Hardware-Spezifikation

| Komponente | Spezifikation |
|------------|---------------|
| **RAM** | 32 GB pro Node |
| **CPU** | 4 echte Cores pro Node |
| **Storage** | SSD oder NVMe |
| **Netzwerk** | Gigabit Ethernet |

---

## Netzwerk & Rollenverteilung

| Node | Hostname | IP-Adresse | Rollen |
|------|----------|------------|--------|
| NUC1 | nuc1 | 192.168.0.100 | ZooKeeper, Solr, Prometheus, Grafana |
| NUC2 | nuc2 | 192.168.0.101 | ZooKeeper, Solr, Spark Master |
| NUC3 | nuc3 | 192.168.0.102 | ZooKeeper, Solr, Spark Worker |
| NUC4 | nuc4 | 192.168.0.103 | Solr, Spark Worker |
| NUC5 | nuc5 | 192.168.0.104 | Solr, Spark Worker |

> **Hinweis:** ZooKeeper Leader wird automatisch per Election gewählt (kein fixer Leader-Node).  
> **Hinweis:** Spark Worker laufen **nur** auf NUC3, NUC4, NUC5 – keine Worker auf NUC1/NUC2.

### Netzwerk-Empfehlung

- DHCP auf OS-Seite verwenden
- Feste IPs nur im Router vergeben (MAC-Bindung)
- `/etc/hosts` auf allen Nodes identisch pflegen

---

## Komponenten

### Big Data Stack

➡️ **[SOLR-SPARK.md](SOLR-SPARK.md)** - Detaillierte Konfiguration:
- Apache ZooKeeper Ensemble (3 Nodes)
- Apache Solr Cloud (5 Nodes)
- Apache Spark (1 Master + 3 Worker)
- Ressourcen-Aufteilung & Isolation

### Monitoring (NUC1)

**Prometheus:**
- Port: 9090
- Scrape-Intervall: 15s
- Retention: 15 Tage
- Data Dir: `/data/prometheus`

**Grafana:**
- Port: 3000
- Dashboards für: Cluster Overview, Solr, Spark, ZooKeeper

**Prometheus Scrape Targets (via JMX Exporter):**

| Service | Exporter | Port | Nodes |
|---------|----------|------|-------|
| Node Metrics | node_exporter | 9100 | Alle |
| Solr | JMX Exporter | 9404 | Alle |
| Spark | JMX Exporter | 9405 | NUC2-NUC5 |
| ZooKeeper | JMX Exporter | 9406 | NUC1-NUC3 |

**prometheus.yml Scrape Config:**
\`\`\`yaml
scrape_configs:
  - job_name: 'node'
    static_configs:
      - targets:
        - 'nuc1:9100'
        - 'nuc2:9100'
        - 'nuc3:9100'
        - 'nuc4:9100'
        - 'nuc5:9100'

  - job_name: 'solr'
    static_configs:
      - targets:
        - 'nuc1:9404'
        - 'nuc2:9404'
        - 'nuc3:9404'
        - 'nuc4:9404'
        - 'nuc5:9404'

  - job_name: 'spark'
    static_configs:
      - targets:
        - 'nuc2:9405'
        - 'nuc3:9405'
        - 'nuc4:9405'
        - 'nuc5:9405'

  - job_name: 'zookeeper'
    static_configs:
      - targets:
        - 'nuc1:9406'
        - 'nuc2:9406'
        - 'nuc3:9406'
\`\`\`

---

## Storage-Layout

| Verzeichnis | Zweck | Nodes |
|-------------|-------|-------|
| \`/data/solr\` | Solr Index | Alle |
| \`/data/spark\` | Spark Shuffle/Spill | NUC2-NUC5 |
| \`/data/zookeeper\` | ZK Data + Snapshots | NUC1-NUC3 |
| \`/data/prometheus\` | Prometheus TSDB | NUC1 |

---

## Provisioning

➡️ **[BAREMETAL-SETUP.md](BAREMETAL-SETUP.md)** - Ubuntu Autoinstall & Cloud-Init

---

## Port-Übersicht

| Service | Port | Nodes |
|---------|------|-------|
| ZooKeeper Client | 2181 | NUC1, NUC2, NUC3 |
| ZooKeeper Follower | 2888 | NUC1, NUC2, NUC3 |
| ZooKeeper Election | 3888 | NUC1, NUC2, NUC3 |
| Solr | 8983 | Alle |
| Spark Master | 7077 | NUC2 |
| Spark Master UI | 8080 | NUC2 |
| Spark Worker UI | 8081 | NUC3, NUC4, NUC5 |
| Prometheus | 9090 | NUC1 |
| Grafana | 3000 | NUC1 |
| Node Exporter | 9100 | Alle |
| Solr JMX Exporter | 9404 | Alle |
| Spark JMX Exporter | 9405 | NUC2-NUC5 |
| ZooKeeper JMX Exporter | 9406 | NUC1-NUC3 |

---

## Smoke Tests

\`\`\`bash
# ZooKeeper Health Check
echo ruok | nc nuc1 2181
echo ruok | nc nuc2 2181
echo ruok | nc nuc3 2181

# Solr System Info
curl http://nuc1:8983/solr/admin/info/system

# Spark Master UI
curl http://nuc2:8080

# Prometheus Ready Check
curl http://nuc1:9090/-/ready

# Grafana Health
curl http://nuc1:3000/api/health
\`\`\`

---

## Nächste Schritte

1. [x] ~~Hardware-Spezifikationen der NUCs klären (RAM, CPU, Storage)~~
2. [ ] Autoinstall ISO erstellen und testen
3. [ ] Cloud-Init Konfigurationen finalisieren
4. [ ] ZooKeeper Ensemble aufsetzen und testen
5. [ ] Solr Cloud deployen und Collection erstellen
6. [ ] Spark Cluster deployen und Test-Job ausführen
7. [ ] Prometheus + Grafana + JMX Exporter einrichten
8. [ ] Smoke Tests durchführen
9. [ ] End-to-End Tests durchführen

---

*Erstellt: Januar 2026*
