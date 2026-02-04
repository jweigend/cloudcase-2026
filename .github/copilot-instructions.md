# Copilot Instructions für Cloudkoffer 2026

> **Hinweis für Copilot:** Bei wichtigen Erkenntnissen (Bugfixes, neue Versionen, geänderte Architektur) diese Datei aktualisieren. Bei Widersprüchen zwischen Dokumentation und Code: Nachfragen.

## Projektübersicht

Portabler Big Data Cluster auf 5 Intel NUCs für Demos und Workshops.

> **Referenz:** Alle IPs, Ports, Versionen → [docs/REFERENCE.md](../docs/REFERENCE.md)

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
```

## Verzeichnisstruktur

```
baremetal/
  05-ansible/
    templates/           # Jinja2 Templates für Ansible
      jupyter/           # Notebook Templates (.ipynb.j2)
      webapp-frontend/   # nginx + Vue.js Templates
      grafana/           # Dashboard Templates
    inventory.yml        # Ansible Inventory
    site.yml             # Haupt-Playbook

webapp/                  # Lokale Entwicklungsversion der Webapp
  backend/               # Flask Backend (backend_services.py)
  src/                   # Vue.js Frontend

docs/
  REFERENCE.md           # IPs, Ports, Versionen (Single Source of Truth)
  SETUP-GUIDE.md         # Installationsanleitung
  ARTICLE-*.md           # Architektur-Artikel
  screenshots/           # Screenshots für Dokumentation
```

## Wichtige Hinweise

### Templates vs. Lokale Dateien

- **Templates** in `baremetal/05-ansible/templates/` werden via Ansible deployed
- **Lokale Dateien** in `webapp/` sind für lokale Entwicklung
- Bei Änderungen: BEIDE synchron halten!

### Webapp Backend

- Läuft auf node0 als systemd Service `webapp-backend`
- Port 5001, nginx proxied `/api/` dorthin
- **Single Source of Truth**: `webapp/backend/backend_services.py`
- Konfiguration via Umgebungsvariablen (lokal via `run.sh`, Cluster via systemd)
- Keine Jinja2-Templates mehr für Backend-Code!

### Spark Konfiguration

- Master: `spark://node0.cloud.local:7077`
- Executor Memory: 6g
- Executor Cores: 2
- Driver Memory: 4g

### Solr

- Collection: `nyc_taxi` mit 4 Shards
- ZooKeeper: `node1:2181,node2:2181,node3:2181`

## Typische Workflows

### Notebook ändern

1. Template bearbeiten: `baremetal/05-ansible/templates/jupyter/*.ipynb.j2`
2. Deployen: `ansible-playbook site.yml --tags notebooks -i inventory.yml -e "force=true"`

### Backend ändern

1. Datei bearbeiten: `webapp/backend/backend_services.py`
2. Lokal testen: `./run.sh` (setzt Umgebungsvariablen automatisch)
3. Deployen: `ansible-playbook site.yml --tags webapp-backend -i inventory.yml`

### Frontend ändern

1. In `webapp/src/` entwickeln
2. Deployen: `ansible-playbook -i inventory.yml webapp-frontend.yml`
   - Das Frontend hat ein **separates Playbook** (nicht über site.yml Tags!)
   - Build erfolgt automatisch auf node0
