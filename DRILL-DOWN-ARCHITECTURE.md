# Drill-Down Architektur: Solr + Spark

**Warum diese Kombination für Big Data Analytics unschlagbar ist.**

---

## Das Problem

Du hast Millionen oder Milliarden von Datensätzen. User wollen:

1. **Sich orientieren** – "Was habe ich überhaupt?"
2. **Einschränken** – "Zeig mir nur die interessanten Daten"
3. **Analysieren** – "Was bedeuten diese Daten?"

Die meisten Architekturen lösen nur einen dieser Punkte gut.

---

## Die Lösung: Zwei Werkzeuge, perfekt kombiniert

```
┌─────────────────────────────────────────────────────────────────────┐
│                     DRILL-DOWN ARCHITEKTUR                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌────────────────────────────────────────────────────────────┐    │
│   │                      ROHDATEN                               │    │
│   │              (Parquet, CSV, Kafka, ...)                     │    │
│   └────────────────────────────────────────────────────────────┘    │
│                              │                                       │
│                              ▼                                       │
│   ┌────────────────────────────────────────────────────────────┐    │
│   │                    APACHE SOLR                              │    │
│   │                                                             │    │
│   │   • Invertierter Index über ALLE Daten                      │    │
│   │   • Facetten für interaktive Navigation                     │    │
│   │   • Streaming Expressions für Ad-hoc Aggregation            │    │
│   │   • Sub-50ms Response für Drill-Down                        │    │
│   │                                                             │    │
│   └────────────────────────────────────────────────────────────┘    │
│                              │                                       │
│                    User findet interessante                          │
│                    Teilmenge via Facetten                            │
│                              │                                       │
│                              ▼                                       │
│   ┌────────────────────────────────────────────────────────────┐    │
│   │                    APACHE SPARK                             │    │
│   │                                                             │    │
│   │   • Lädt gefilterte Daten via Solr /export                  │    │
│   │   • Komplexe Statistik, ML, Korrelationen                   │    │
│   │   • Nur auf relevanter Teilmenge (nicht Petabytes!)         │    │
│   │                                                             │    │
│   └────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Warum Solr für Navigation?

### Facetten: Der geheime Killer

Eine einzige Solr-Query liefert:

```
GET /solr/collection/select?q=*:*
    &facet=true
    &facet.field=kategorie
    &facet.field=region
    &facet.field=zeitraum
    &facet.field=status
    &fq=datum:[2024-01-01 TO 2024-12-31]
```

**Antwort in ~20ms:**
```json
{
  "numFound": 4.847.293,
  "facets": {
    "kategorie":  {"A": 1200000, "B": 980000, "C": 2667293},
    "region":     {"Nord": 800000, "Süd": 1200000, ...},
    "zeitraum":   {"Q1": 1100000, "Q2": 1300000, ...},
    "status":     {"aktiv": 4000000, "archiv": 847293}
  }
}
```

**Was hier passiert:**
- 4,8 Millionen Dokumente durchsucht
- 4 verschiedene Dimensionen aggregiert
- Alle Counts berechnet
- **In einer Query, unter 50ms**

### Warum SQL-Datenbanken hier versagen

Das gleiche in ClickHouse/PostgreSQL:

```sql
-- Query 1: Gesamtzahl
SELECT count(*) FROM data WHERE datum BETWEEN '2024-01-01' AND '2024-12-31';

-- Query 2: Facette 1
SELECT kategorie, count(*) FROM data 
WHERE datum BETWEEN '2024-01-01' AND '2024-12-31' 
GROUP BY kategorie;

-- Query 3: Facette 2
SELECT region, count(*) FROM data 
WHERE datum BETWEEN '2024-01-01' AND '2024-12-31' 
GROUP BY region;

-- Query 4, 5, ... für jede weitere Facette
```

**Ergebnis:**
- N+1 Queries statt einer
- Jede Query scannt die Daten neu
- Backend muss Queries orchestrieren
- Latenz addiert sich

### Das Drill-Down Dilemma

User klickt auf `kategorie: A` → **Alle Facetten müssen sofort neu berechnet werden**

| System | Was passiert | Latenz |
|--------|--------------|--------|
| **Solr** | `fq=kategorie:A` hinzufügen, eine Query | ~25ms |
| **SQL** | N Queries mit neuem WHERE | N × 50-100ms |

Bei einer komplexen UI mit 10 Facetten und 5 Drill-Down Ebenen:
- Solr: 5 Queries × 25ms = **125ms** gesamt
- SQL: 5 × 10 Queries × 75ms = **3.750ms** gesamt

---

## Warum Spark für Analyse?

Solr ist fantastisch für Navigation, aber **nicht für komplexe Analytik**:

| Aufgabe | Solr | Spark |
|---------|------|-------|
| Facetten-Counts | ✅ Perfekt | ⚠️ Overkill |
| Top-N Aggregation | ✅ Streaming Expressions | ✅ Gut |
| Korrelationsanalyse | ❌ Nicht möglich | ✅ Perfekt |
| Machine Learning | ❌ Nicht möglich | ✅ MLlib |
| Komplexe Joins | ⚠️ Limitiert | ✅ Perfekt |
| Window Functions | ❌ Nein | ✅ Ja |

### Der Workflow

```
User Journey:
┌──────────────────────────────────────────────────────────────────┐
│                                                                   │
│  1. Start: 100 Millionen Datensätze                              │
│     └─► Solr Facetten: "Was gibt es?"                            │
│                                                                   │
│  2. Drill-Down: User klickt auf interessante Werte               │
│     └─► Solr: Filtert auf 500.000 Datensätze (~25ms)             │
│                                                                   │
│  3. Weiterer Drill-Down                                          │
│     └─► Solr: Filtert auf 12.000 Datensätze (~20ms)              │
│                                                                   │
│  4. "Diese Daten will ich genauer analysieren"                   │
│     └─► Spark: Lädt 12.000 Docs via /export                      │
│     └─► ML-Analyse, Korrelationen, Statistik                     │
│                                                                   │
│  5. Ergebnis: Insights aus fokussierter Datenmenge               │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

**Der Trick:** Spark arbeitet nie auf 100 Millionen Datensätzen blind. 
User hat via Facetten bereits die relevante Teilmenge identifiziert.

---

## Die 4 Säulen der Architektur

| # | Komponente | Aufgabe | Typische Latenz |
|---|------------|---------|-----------------|
| 1 | **Rohdaten in Solr** | Vollständiger Index für Drill-Down | Einmaliger Import |
| 2 | **Facetten-Navigation** | Interaktive Exploration | <50ms pro Klick |
| 3 | **Streaming Expressions** | Ad-hoc Aggregationen in Solr | 100-500ms |
| 4 | **Spark via /export** | ML, komplexe Statistik | Sekunden |

---

## Vergleich mit Alternativen

### ClickHouse / DuckDB
```
✅ Schneller für reine SQL-Aggregationen
❌ Keine native Facetten → Backend-Komplexität explodiert
❌ Keine Volltextsuche
❌ Kein Tag/Exclude für Facetten
```

### Elasticsearch
```
✅ Ähnlich stark bei Facetten (Aggregations)
⚠️ Komplexer zu betreiben (X-Pack, Sharding)
⚠️ Kein Äquivalent zu Streaming Expressions
✅ Besserer Spark-Connector
```

### Druid / Pinot
```
✅ Noch schneller für Time-Series OLAP
✅ Real-Time Ingestion
❌ Keine Volltextsuche
❌ Weniger flexibel
```

### Cloud-Native (Snowflake, BigQuery, Databricks)
```
✅ Zero Operations
⚠️ Teuer bei großen Datenmengen
❌ Vendor Lock-in
❌ Keine echten Facetten
```

---

## Wann diese Architektur wählen?

### ✅ Perfekt für:
- **E-Commerce**: Produktkataloge mit Filter-Navigation
- **Log-Analyse**: Exploration von Millionen Events
- **Business Intelligence**: Self-Service Analytics
- **IoT-Daten**: Sensor-Daten mit Drill-Down
- **Dokumenten-Management**: Suche + Kategorisierung

### ⚠️ Nicht ideal für:
- Reine Real-Time Dashboards (→ Druid)
- Nur SQL-Aggregationen ohne Facetten (→ ClickHouse)
- Kleine Datenmengen <10GB (→ DuckDB/Polars)

---

## Technische Umsetzung

### Import: Parallel via Spark

```python
# Spark liest Parquet parallel
df = spark.read.parquet("/data/*.parquet")

# Jede Partition sendet direkt an Solr (Round-Robin)
df.rdd.mapPartitionsWithIndex(send_to_solr).collect()
```

### Navigation: Solr Facetten

```python
response = requests.get(f"{SOLR}/select", params={
    "q": "*:*",
    "facet": "true",
    "facet.field": ["kategorie", "region", "status"],
    "fq": user_filters
})
```

### Aggregation: Streaming Expressions

```python
expr = f"""
rollup(
  search(collection, q="*:*", fl="field1,field2", qt="/export"),
  over="field1",
  sum(field2), avg(field2), count(*)
)
"""
```

### Analyse: Spark via /export

```python
# Gefilterte Daten aus Solr
docs = requests.get(f"{SOLR}/export", params={
    "q": "kategorie:A AND region:Nord",
    "fl": "field1,field2,field3"
}).json()

# In Spark für ML
df = spark.createDataFrame(docs)
correlation = Correlation.corr(df, "features")
```

---

## Fazit

Diese Architektur ist ein Killer, weil sie **das richtige Werkzeug für jeden Schritt** verwendet:

| Schritt | Werkzeug | Warum |
|---------|----------|-------|
| **Orientierung** | Solr Facetten | Invertierter Index = O(1) Lookups |
| **Einschränkung** | Solr Filter | Filter-Queries sind gecached |
| **Aggregation** | Streaming Expressions | Keine Netzwerk-Roundtrips |
| **Tiefenanalyse** | Spark | Verteiltes Compute |

**Seit 2010 bewährt. Keine Vendor Lock-in. Open Source.**

```
        "Facetten sind der erste gute Weg, 
         die Datenmengen beherrschbar einzuschränken."
         
                                    – Johannes, 2016 & 2026
```
