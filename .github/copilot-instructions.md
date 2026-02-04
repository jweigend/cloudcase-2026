# Copilot Instructions für Cloudkoffer 2026

> **Hinweis für Copilot:** Wenn in einer neuen Session wichtige Erkenntnisse entstehen (Bugfixes, neue Versionen, geänderte Architektur), dokumentiere diese knapp in dieser Datei. Bei Widersprüchen zwischen dieser Dokumentation und dem tatsächlichen Code: Nachfragen und bei Bedarf dieses Dokument aktualisieren, damit die Anweisungen nicht veralten.

## Projektübersicht

Portabler Big Data Cluster auf 5 Intel NUCs für Demos und Workshops.

## Cluster-Architektur

| Node | IP | Rollen |
|------|-----|--------|
| node0 | 192.168.1.100 | Spark Master, Jupyter, Grafana, Prometheus, nginx, Webapp Backend |
| node1 | 192.168.1.101 | ZooKeeper, Solr, Spark Worker |
| node2 | 192.168.1.102 | ZooKeeper, Solr, Spark Worker |
| node3 | 192.168.1.103 | ZooKeeper, Solr, Spark Worker |
| node4 | 192.168.1.104 | Solr, Spark Worker |

## Wichtige Befehle

### Ansible Deployment

```bash
cd baremetal/05-ansible

# Alle Services deployen
ansible-playbook site.yml -i inventory.yml

# Mit spezifischem Tag deployen
ansible-playbook site.yml --tags <tag> -i inventory.yml

# Notebooks MÜSSEN mit force=true überschrieben werden!
ansible-playbook site.yml --tags notebooks -i inventory.yml -e "force=true"
```

### Verfügbare Ansible Tags

- `zookeeper` - ZooKeeper Cluster
- `solr` - Solr Cloud
- `spark` - Spark Master + Workers
- `jupyter` - JupyterLab
- `notebooks` - Jupyter Notebooks (braucht `-e "force=true"`)
- `monitoring` - Prometheus + Grafana
- `webapp-backend` - Flask Backend
- `webapp-frontend` - nginx + Vue.js Frontend

### Makefile im baremetal/ Verzeichnis

```bash
cd baremetal
make status      # Cluster-Status anzeigen
make start       # Alle Nodes starten (Wake-on-LAN)
make shutdown    # Alle Nodes herunterfahren
make jupyter     # JupyterLab deployen
```

## Verzeichnisstruktur

```
baremetal/
  05-ansible/
    templates/           # Jinja2 Templates für Ansible
      jupyter/           # Notebook Templates (.ipynb.j2)
      webapp-backend/    # Flask Backend Template (app.py.j2)
      webapp-frontend/   # nginx + Vue.js Templates
      grafana/           # Dashboard Templates
    inventory.yml        # Ansible Inventory
    site.yml             # Haupt-Playbook

webapp/                  # Lokale Entwicklungsversion der Webapp
  backend/               # Flask Backend (app.py)
  src/                   # Vue.js Frontend

docs/
  screenshots/           # Screenshots für Dokumentation
  images/                # Bilder (z.B. Cluster-Foto)
```

## Wichtige Hinweise

### Templates vs. Lokale Dateien

- **Templates** in `baremetal/05-ansible/templates/` werden via Ansible deployed
- **Lokale Dateien** in `webapp/` sind für lokale Entwicklung
- Bei Änderungen: BEIDE synchron halten!

### Webapp Backend

- Läuft auf node0 als systemd Service `webapp-backend`
- Port 5001, nginx proxied `/api/` dorthin
- **Single Source of Truth**: `webapp/backend/backend-services.py`
- Konfiguration via Umgebungsvariablen (lokal via `run.sh`, Cluster via systemd)
- Keine Jinja2-Templates mehr für Backend-Code!

### Spark Konfiguration

- Master: `spark://node0.cloud.local:7077`
- Executor Memory: 16g
- Executor Cores: 4
- Executor Instances: 4

### Solr

- Collection: `nyc_taxi` mit 4 Shards
- ZooKeeper: `node1:2181,node2:2181,node3:2181`

## Typische Workflows

### Notebook ändern

1. Template bearbeiten: `baremetal/05-ansible/templates/jupyter/*.ipynb.j2`
2. Deployen: `ansible-playbook site.yml --tags notebooks -i inventory.yml -e "force=true"`

### Backend ändern

1. Datei bearbeiten: `webapp/backend/backend-services.py`
2. Lokal testen: `./run.sh` (setzt Umgebungsvariablen automatisch)
3. Deployen: `ansible-playbook site.yml --tags webapp-backend -i inventory.yml`

### Frontend ändern

1. In `webapp/src/` entwickeln
2. Deployen: `ansible-playbook -i inventory.yml webapp-frontend.yml`
   - Das Frontend hat ein **separates Playbook** (nicht über site.yml Tags!)
   - Build erfolgt automatisch auf node0
