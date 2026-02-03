# NYC Taxi Facet Explorer

Interaktive Drill-Down Webapp zur Exploration von NYC Taxi-Daten mit Solr Facetten und Spark Analytics.

## Architektur

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DRILL-DOWN ARCHITEKTUR                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────┐ │
│  │   Vue.js     │────▶│    nginx     │────▶│   Solr Cloud         │ │
│  │   Frontend   │     │   (Proxy)    │     │   (Facetten+Stats)   │ │
│  └──────────────┘     └──────┬───────┘     └──────────────────────┘ │
│                              │                                       │
│                              │ /api/*                                │
│                              ▼                                       │
│                       ┌──────────────┐     ┌──────────────────────┐ │
│                       │   Flask      │────▶│   Spark Cluster      │ │
│                       │   Backend    │     │   (Top-Routes ML)    │ │
│                       └──────────────┘     └──────────────────────┘ │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Features

### Facetten-Navigation (Solr, <50ms)
- **Multi-Select Filter**: Mehrere Werte pro Facette auswählbar (OR-Verknüpfung)
- **Tag/Exclude Pattern**: Facetten-Counts bleiben sichtbar auch bei aktiven Filtern
- **Auf-/Zuklappbare Gruppen**: Übersichtliche UI mit Badge-Counter für aktive Filter

### Chart-Drill-Down
- **Klickbare Balkendiagramme**: Klick auf Stunden- oder Fahrpreis-Balken setzt Filter
- **Visuelle Hervorhebung**: Aktive Filter werden dunkler + mit Border dargestellt
- **Range-Filter**: Fahrpreis-Bereiche als `[10 TO 20]` Solr-Syntax

### Spark Analytics (Top-Routes, ~90s)
- **Paralleles Shard-Loading**: Jeder Spark Executor lädt von seinem lokalen Shard
- **Lukrativitäts-Score**: Kombiniert Umsatz, Fahrtdauer und Fahrpreis/Minute
- **Konfigurierbar**: Top 5/10/20 Routen per UI wählbar

## Tech Stack

| Komponente | Technologie | Port |
|------------|-------------|------|
| Frontend | Vue 3 + Vite + Tailwind CSS | 80 (nginx) |
| Charts | Chart.js + vue-chartjs | - |
| Backend | Flask + PySpark | 5001 |
| Suchindex | Apache Solr Cloud | 8983 |
| Analytics | Apache Spark (Cluster) | 7077 |

## Voraussetzungen

**Daten müssen importiert sein!** 

Die NYC Taxi-Daten werden über das Jupyter Notebook importiert:

1. JupyterLab öffnen: http://node0.cloud.local:8888
2. Notebook `05-drilldown-architecture.ipynb` öffnen
3. Teil 1 (Spark Session) + Teil 2 (Datenimport) ausführen
4. Warten bis ~6M Dokumente in Solr indexiert sind

Alternativ via Ansible:
```bash
cd baremetal/05-ansible
ansible-playbook -i inventory.yml jupyter.yml --tags notebooks -e "force=true"
```

## Lokale Entwicklung

```bash
# Frontend starten (mit Hot-Reload)
cd webapp
npm install
npm run dev

# Backend starten (benötigt Spark-Cluster oder local[*])
cd webapp/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

**Hinweis:** Für lokale Entwicklung muss Solr erreichbar sein. 
Entweder Cluster läuft oder Proxy in `vite.config.js` anpassen.

## Deployment (Ansible)

```bash
cd baremetal/05-ansible

# Frontend + Backend deployen
ansible-playbook -i inventory.yml webapp-frontend.yml webapp-backend.yml

# Nur Frontend aktualisieren
ansible-playbook -i inventory.yml webapp-frontend.yml
```

Das Ansible-Playbook:
1. Baut das Frontend mit `npm run build`
2. Kopiert `/dist` nach nginx auf node0
3. Deployt Backend als systemd Service auf node0
4. Konfiguriert nginx Proxy für `/api/` → Backend:5001

## API Endpoints

### GET `/api/health`
Health-Check für Backend + Spark-Verbindung.

### POST `/api/count`
Schneller Count via Solr (keine Spark-Beteiligung).

```json
{
  "filters": {"pickup_hour": [18, 19], "payment_type": [1]}
}
```

### POST `/api/top-routes`
Berechnet lukrativste Routen via Spark.

```json
{
  "filters": {"pickup_hour": [18, 19]},
  "limit": 5
}
```

Response:
```json
{
  "routes": [...],
  "total_trips": 50000,
  "spark_time_ms": 2500,
  "load_strategy": "parallel_shards",
  "shards_used": 4
}
```

## Verzeichnisstruktur

```
webapp/
├── src/
│   ├── App.vue              # Hauptkomponente
│   ├── api/
│   │   ├── solr.js          # Solr Facetten + Stats API
│   │   └── backend.js       # Spark Backend API
│   └── components/
│       ├── FacetPanel.vue   # Linke Sidebar mit Facetten
│       ├── FacetGroup.vue   # Einzelne Facetten-Gruppe
│       ├── StatsPanel.vue   # Charts (Stunden + Fahrpreis)
│       └── TopRoutesPanel.vue # Spark Top-Routes Tabelle
├── backend/
│   ├── app.py               # Flask + PySpark Backend
│   └── requirements.txt
├── vite.config.js           # Proxy-Konfiguration für Dev
└── package.json
```

## Performance-Charakteristik

| Operation | Latenz | Datenfluss |
|-----------|--------|------------|
| Facetten-Query | <50ms | Browser → nginx → Solr |
| Streaming Stats | 100-500ms | Browser → nginx → Solr |
| Top-Routes (5M Docs) | ~90s | Backend → Spark → 4 Shards parallel |

## Paralleles Shard-Loading (Data Locality)

```
┌─────────────────────────────────────────────────────────────────┐
│  Jeder Executor → Lokaler Shard via /export Handler             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Backend holt Shard→Node Mapping via CLUSTERSTATUS API      │
│                                                                 │
│  2. Spark parallelisiert Shards als RDD:                       │
│     Executor 1 ──► node1:8983/solr/core_shard1/export          │
│     Executor 2 ──► node2:8983/solr/core_shard2/export          │
│     Executor 3 ──► node3:8983/solr/core_shard3/export          │
│     Executor 4 ──► node4:8983/solr/core_shard4/export          │
│                                                                 │
│  Ergebnis: 4x paralleler I/O, kein Single-Node-Bottleneck!     │
└─────────────────────────────────────────────────────────────────┘
```
