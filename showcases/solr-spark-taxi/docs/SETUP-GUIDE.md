# Cloudkoffer Setup Guide

Schritt-für-Schritt Anleitung zur Installation des Big Data Clusters.

> **Referenz:** Alle IPs, Ports und Versionen findest du in [REFERENCE.md](REFERENCE.md)

---

## Übersicht

```
┌───────────────────┐
│  1. BAREMETAL     │  Ubuntu Autoinstall + Cloud-Init
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  2. ANSIBLE       │  ZooKeeper → Solr → Spark → Monitoring
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  3. SMOKE TESTS   │  Cluster-Validierung
└─────────┬─────────┘
          ▼
┌───────────────────┐
│  4. DATEN LADEN   │  NYC Taxi Daten via Jupyter
└───────────────────┘
```

---

## Phase 1: Baremetal Installation

### 1.1 Voraussetzungen (Admin-Rechner)

```bash
sudo apt-get install -y xorriso wget curl netcat-openbsd whois pipx
pipx install ansible
pipx ensurepath
```

### 1.2 EdgeRouter konfigurieren

Der EdgeRouter weist jedem NUC per MAC-Adresse eine feste IP zu.

```bash
cd baremetal/00-edgerouter-config
./configure-edgerouter.sh
```

### 1.3 Autoinstall ISO erstellen

Ein einziges ISO für alle 5 NUCs:

```bash
cd baremetal/01-generate-configs
./generate-all.sh ~/.ssh/id_rsa.pub

cd ../02-create-iso
./create-iso.sh

cd ../03-write-usb
./write-usb.sh /dev/sdX
```

### 1.4 NUCs installieren

1. NUC von USB booten (F10 beim Start)
2. "Cloudkoffer Autoinstall" wählen
3. Warten (~10 Minuten pro Node)
4. Post-Install ausführen:

```bash
cd baremetal/04-post-install

# Pro Node (oder in Schleife)
./apply-cloud-init.sh 192.168.1.100
./apply-cloud-init.sh 192.168.1.101
./apply-cloud-init.sh 192.168.1.102
./apply-cloud-init.sh 192.168.1.103
./apply-cloud-init.sh 192.168.1.104
```

**Wie die Identifikation funktioniert:**
- MAC-Adresse → EdgeRouter vergibt feste IP
- IP → Post-Install setzt Hostname
- Hostname → Ansible weist Rollen zu

---

## Phase 2: Ansible Deployment

### 2.1 Gesamten Stack installieren

```bash
cd baremetal/05-ansible
ansible-playbook -i inventory.yml site.yml
```

### 2.2 Einzelne Komponenten

```bash
# DNS-Cache (alle Nodes)
ansible-playbook -i inventory.yml dnsmasq.yml

# ZooKeeper (node1-3)
ansible-playbook -i inventory.yml zookeeper.yml

# Solr Cloud (node1-4)
ansible-playbook -i inventory.yml solr.yml

# Spark Cluster (node0=Master, node1-4=Workers)
ansible-playbook -i inventory.yml spark.yml

# Monitoring (node0)
ansible-playbook -i inventory.yml monitoring.yml
ansible-playbook -i inventory.yml prometheus-exporters.yml

# JupyterLab (node0)
ansible-playbook -i inventory.yml jupyter.yml

# NYC Taxi Explorer Webapp
ansible-playbook -i inventory.yml webapp-backend.yml
ansible-playbook -i inventory.yml webapp-frontend.yml
```

### 2.3 Verfügbare Tags

```bash
# Mit spezifischem Tag deployen
ansible-playbook site.yml --tags <tag> -i inventory.yml

# Notebooks MÜSSEN mit force=true überschrieben werden!
ansible-playbook site.yml --tags notebooks -i inventory.yml -e "force=true"
```

---

## Phase 3: Smoke Tests

```bash
cd baremetal/09-smoke-tests
./smoke-tests.sh
```

Oder manuell:

```bash
# ZooKeeper
echo ruok | nc node1 2181

# Solr
curl http://node1:8983/solr/admin/info/system

# Spark Master
curl http://node0:8081

# Prometheus
curl http://node0:9090/-/ready

# Grafana
curl http://node0:3000/api/health
```

---

## Phase 4: NYC Taxi Daten laden

### 4.1 JupyterLab öffnen

http://node0.cloud.local:8888

### 4.2 Datenimport-Notebook ausführen

1. Notebook `05-drilldown-architecture.ipynb` öffnen
2. Teil 1 (Spark Session) ausführen
3. Teil 2 (Datenimport) ausführen
4. Warten bis ~6M Dokumente in Solr indexiert sind

### 4.3 Solr Collection erstellen (falls nicht vorhanden)

```bash
cd baremetal/07-create-solr-collection
./create-collection.sh nyc_taxi
```

---

## Service-Konfiguration

### ZooKeeper

| Parameter | Wert |
|-----------|------|
| Nodes | node1, node2, node3 |
| Port | 2181 |
| Heap | 512 MB |
| Data Dir | `/data/zookeeper` |

**zoo.cfg (Auszug):**
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

### Solr Cloud

| Parameter | Wert |
|-----------|------|
| Nodes | node1-4 |
| Port | 8983 |
| Heap | 8 GB |
| JMX | 9404 |

**solr.in.sh (Auszug):**
```bash
SOLR_HEAP="8g"
SOLR_HOME="/data/solr"
ZK_HOST="node1:2181,node2:2181,node3:2181"
```

### Spark

| Komponente | Node | Heap |
|------------|------|------|
| Master | node0 | 2 GB |
| Worker | node1-4 | 6 GB |

**spark-defaults.conf (Auszug):**
```properties
spark.master                     spark://node0.cloud.local:7077
spark.local.dir                  /data/spark
spark.executor.memory            6g
spark.executor.cores             2
spark.driver.memory              4g
spark.sql.shuffle.partitions     48
```

### Prometheus

**Scrape Targets:**
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

### Grafana Dashboards

Import über: Dashboards → Import → ID eingeben

| Dashboard | ID |
|-----------|-----|
| Node Exporter Full | 1860 |
| Solr Dashboard | 2551 |
| Spark Dashboard | 7890 |

---

## Troubleshooting

### Service neustarten

```bash
ssh cloudadmin@nodeX 'sudo systemctl restart <service>'
```

### Logs prüfen

```bash
ssh cloudadmin@nodeX 'journalctl -u <service> -f'
```

### Cluster komplett neustarten

```bash
cd baremetal
make shutdown   # Alle Nodes herunterfahren
make start      # Wake-on-LAN
make status     # Status prüfen
```

---

## Weiterführende Dokumentation

- [REFERENCE.md](REFERENCE.md) - IPs, Ports, Versionen
- [ARTICLE-drill-down-architecture.md](ARTICLE-drill-down-architecture.md) - Die Architektur erklärt
- [../webapp/README.md](../webapp/README.md) - NYC Taxi Explorer Webapp
- [../baremetal/05-ansible/README.md](../baremetal/05-ansible/README.md) - Ansible Details

---

*Stand: Februar 2026*
