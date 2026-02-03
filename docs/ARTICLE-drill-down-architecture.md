# Die vergessene Kunst der Datenexploration: Warum Solr + Spark immer noch unschlagbar ist

*Eine Architektur, die ich 2016 entdeckt habe – und die 2026 relevanter ist denn je.*

---

## Einleitung: Das Paradox der modernen Datenanalyse

Wir leben in einer seltsamen Zeit. Unternehmen sammeln mehr Daten als je zuvor, investieren Millionen in Data Lakes und Analytics-Plattformen – und trotzdem höre ich immer wieder dieselbe Frage: *"Wir haben die Daten, aber wie finden wir darin etwas Nützliches?"*

Das Problem ist nicht die Technologie. Es ist die **Architektur**.

Die meisten modernen Data-Stacks sind für eine Welt gebaut, in der Analysten bereits wissen, wonach sie suchen. Sie schreiben SQL-Queries, bauen Dashboards für bekannte KPIs, trainieren ML-Modelle auf vordefinierten Features. Das funktioniert – solange die Fragen bekannt sind.

Aber was, wenn du **nicht weißt, wonach du suchst**?

Was, wenn du 100 Millionen Datensätze hast und erstmal verstehen willst, *was da überhaupt drin ist*? Welche Muster existieren? Welche Anomalien? Welche Teilmengen sind interessant genug für eine tiefere Analyse?

Genau hier versagen die meisten Architekturen. Und genau hier glänzt eine Kombination, die ich vor fast zehn Jahren zum ersten Mal eingesetzt habe: **Apache Solr für Navigation, Apache Spark für Analyse.**

---

## Das fundamentale Problem: Drei Schritte, die niemand zusammen löst

Jede Datenexploration besteht aus drei Phasen:

**1. Orientierung** – *"Was habe ich überhaupt?"*

Bevor du analysieren kannst, musst du die Landschaft verstehen. Wie verteilen sich die Daten über Zeit, Kategorien, Regionen? Wo sind die großen Cluster, wo die Ausreißer?

**2. Einschränkung** – *"Zeig mir die interessante Teilmenge"*

In 100 Millionen Datensätzen ist nicht alles gleich relevant. Du willst dich fokussieren – auf einen Zeitraum, eine Kundengruppe, ein Produktsegment. Und du willst dabei *sofort* sehen, wie sich die anderen Dimensionen verändern.

**3. Tiefenanalyse** – *"Was bedeuten diese Daten?"*

Wenn du die interessante Teilmenge gefunden hast, willst du richtig reinschauen: Korrelationen berechnen, Cluster identifizieren, Prognosen erstellen.

Die Crux: **Die meisten Systeme sind nur für einen dieser Schritte optimiert.**

- **Data Warehouses** (Snowflake, BigQuery) sind gut für Phase 3, aber langsam für interaktive Exploration
- **OLAP-Cubes** (Druid, Pinot) sind schnell für vordefinierte Dimensionen, aber unflexibel
- **SQL-Datenbanken** können alles irgendwie, aber nichts richtig gut
- **Suchmaschinen** (Solr, Elasticsearch) sind Meister der Exploration, aber schwach bei komplexer Analytik

Die Lösung? **Zwei spezialisierte Werkzeuge, perfekt kombiniert.**

---

## Die Architektur: Solr als Kompass, Spark als Mikroskop

Die Grundidee ist einfach: Nutze das beste Werkzeug für jeden Schritt.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│                    DIE DRILL-DOWN ARCHITEKTUR                           │
│                                                                         │
│   ═══════════════════════════════════════════════════════════════════   │
│                                                                         │
│                         ┌─────────────────┐                             │
│                         │   ROHDATEN      │                             │
│                         │  ───────────    │                             │
│                         │  Parquet, CSV,  │                             │
│                         │  Kafka, APIs    │                             │
│                         └────────┬────────┘                             │
│                                  │                                      │
│                                  │ Paralleler Import                    │
│                                  │ via Spark                            │
│                                  ▼                                      │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │                                                                  │  │
│   │                        APACHE SOLR                               │  │
│   │                     ════════════════                             │  │
│   │                                                                  │  │
│   │    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │  │
│   │    │ Invertierter│  │  Facetten   │  │  Streaming  │             │  │
│   │    │    Index    │  │   Engine    │  │ Expressions │             │  │
│   │    │             │  │             │  │             │             │  │
│   │    │ Alle Daten  │  │ Multi-Dim.  │  │  In-Solr    │             │  │
│   │    │ durchsuchbar│  │ Navigation  │  │ Aggregation │             │  │
│   │    └─────────────┘  └─────────────┘  └─────────────┘             │  │
│   │                                                                  │  │
│   │         PHASE 1 & 2: Orientierung + Einschränkung                │  │
│   │                    Latenz: < 50ms pro Interaktion                │  │
│   │                                                                  │  │
│   └──────────────────────────────────────────────────────────────────┘  │
│                                  │                                      │
│                                  │ User hat interessante                │
│                                  │ Teilmenge identifiziert              │
│                                  │                                      │
│                                  ▼                                      │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │                                                                  │  │
│   │                       APACHE SPARK                               │  │
│   │                    ═════════════════                             │  │
│   │                                                                  │  │
│   │    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │  │
│   │    │   Lädt nur  │  │  MLlib für  │  │   Window    │             │  │
│   │    │  relevante  │  │  ML/Stats   │  │  Functions  │             │  │
│   │    │   Teilmenge │  │             │  │             │             │  │
│   │    │ via /export │  │ Clustering, │  │  Komplexe   │             │  │
│   │    │   Handler   │  │ Regression  │  │   Analytik  │             │  │
│   │    └─────────────┘  └─────────────┘  └─────────────┘             │  │
│   │                                                                  │  │
│   │             PHASE 3: Tiefenanalyse auf fokussierter              │  │
│   │                      Datenmenge (nicht auf allem!)               │  │
│   │                                                                  │  │
│   └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Der Kern der Idee:** Solr hilft dir, die Nadel im Heuhaufen zu finden. Spark hilft dir, die Nadel zu analysieren. Du zwingst Spark nie, blind durch Petabytes zu wühlen.

---

## Der geheime Held: Facetten

Wenn ich einen einzigen Grund nennen müsste, warum diese Architektur funktioniert, wäre es: **Facetten**.

Facetten sind die Antwort auf die Frage: *"Wie verteilen sich meine Daten über verschiedene Dimensionen – und wie ändert sich das, wenn ich filtere?"*

Klingt simpel. Ist es nicht.

### Ein konkretes Beispiel

Stell dir vor, du hast 5 Millionen Taxi-Fahrten in New York. Du öffnest deine Analytics-UI und siehst:

```
Gesamte Fahrten: 4.847.293

Nach Tageszeit:           Nach Bezirk:            Nach Zahlungsart:
├─ Morgen:    823.000    ├─ Manhattan: 2.100.000  ├─ Kreditkarte: 3.200.000
├─ Mittag:  1.200.000    ├─ Brooklyn:    890.000  ├─ Bargeld:     1.500.000
├─ Abend:   1.824.000    ├─ Queens:      650.000  └─ Sonstige:      147.293
└─ Nacht:   1.000.293    └─ Bronx:       407.293
```

Diese Übersicht erscheint **in unter 50 Millisekunden**. Eine einzige Query an Solr.

Jetzt klickst du auf "Abend". Sofort aktualisieren sich alle anderen Facetten:

```
Gefiltert: Abendfahrten (1.824.000)

Nach Bezirk:              Nach Zahlungsart:
├─ Manhattan: 1.100.000   ├─ Kreditkarte: 1.400.000
├─ Brooklyn:    380.000   ├─ Bargeld:       400.000
└─ Queens:      244.000   └─ Sonstige:       24.000
```

**Wieder unter 50ms.** Du siehst sofort: Abends wird mehr mit Karte bezahlt, Manhattan dominiert noch stärker.

Du klickst weiter auf "Manhattan" und dann auf "Bargeld". Jetzt hast du 320.000 Fahrten – Abends, in Manhattan, bar bezahlt. Interessante Gruppe. Zeit für die Tiefenanalyse.

### Warum SQL-Datenbanken hier scheitern

Versuch das Gleiche mit einer SQL-Datenbank:

```sql
-- Du brauchst EINE Query pro Facette
SELECT tageszeit, COUNT(*) FROM fahrten WHERE ... GROUP BY tageszeit;
SELECT bezirk, COUNT(*) FROM fahrten WHERE ... GROUP BY bezirk;
SELECT zahlungsart, COUNT(*) FROM fahrten WHERE ... GROUP BY zahlungsart;
```

**Drei Queries** für die initiale Ansicht. Drei weitere nach jedem Klick. Bei 10 Facetten sind das 10 Queries. Bei 5 Drill-Down-Ebenen sind das **50 Queries**.

Und jede Query muss:
- Die Daten erneut scannen (oder auf Caches hoffen)
- Unabhängig ausgeführt werden
- Vom Backend orchestriert werden

In Solr? **Eine Query. Immer. Egal wie viele Facetten.**

### Die Magie dahinter

Solr nutzt einen **invertierten Index** – dieselbe Technologie, die Google-Suchen in Millisekunden ermöglicht.

Für jedes Feld weiß Solr: *"Welche Dokumente haben diesen Wert?"*

```
Index für "bezirk":
├─ Manhattan → [Doc1, Doc2, Doc5, Doc8, Doc9, ...]
├─ Brooklyn  → [Doc3, Doc4, Doc7, Doc12, ...]
└─ Queens    → [Doc6, Doc10, Doc11, ...]
```

Wenn du nach "Manhattan AND Abend" filterst, macht Solr eine **Mengen-Schnittmenge** – eine Operation, die in Mikrosekunden läuft. Die Facetten-Counts? Einfach die Länge der resultierenden Listen.

Kein Scan. Kein Sort. Kein Group By. **Lookup-Operationen.**

---

## Streaming Expressions: Ad-hoc Aggregationen ohne Spark

Manchmal brauchst du mehr als Counts. Du willst Summen, Durchschnitte, Top-N Rankings. Dafür hat Solr **Streaming Expressions** – eine unterschätzte Superkraft.

```
rollup(
  search(taxi_collection,
    q="bezirk:Manhattan AND tageszeit:Abend",
    fl="zahlungsart,betrag,trinkgeld",
    sort="zahlungsart asc",
    qt="/export"
  ),
  over="zahlungsart",
  sum(betrag),
  avg(trinkgeld),
  count(*)
)
```

Diese Expression:
1. Streamt alle passenden Dokumente (ohne sie in RAM zu laden)
2. Aggregiert sie nach Zahlungsart
3. Berechnet Summe, Durchschnitt und Count

**Alles in Solr.** Kein Spark. Keine externe Verarbeitung. Typische Latenz: 100-500ms für Millionen von Dokumenten.

Streaming Expressions können auch:
- `top()` – Top-N Rankings
- `unique()` – Distinct Values
- `innerJoin()`, `leftOuterJoin()` – Joins zwischen Collections
- `classify()` – Einfache ML-Klassifikation

Für 80% der Analytics-Anfragen brauchst du Spark gar nicht.

---

## Spark: Wenn es ernst wird

Aber es gibt Grenzen. Wenn du brauchst:

- **Korrelationsanalysen** zwischen vielen Variablen
- **Machine Learning** (Clustering, Regression, Neural Networks)
- **Window Functions** (Moving Averages, Cumulative Sums)
- **Komplexe Joins** über mehrere Datenquellen

...dann ist Spark das richtige Werkzeug.

Der Trick: **Spark arbeitet nie auf allem.** 

Du hast via Facetten bereits die interessante Teilmenge identifiziert. Statt 100 Millionen Datensätze lädst du nur die relevanten 50.000 nach Spark.

```python
# Gefilterte Daten aus Solr laden
response = requests.get(f"{SOLR}/export", params={
    "q": "bezirk:Manhattan AND tageszeit:Abend AND zahlungsart:Bargeld",
    "fl": "betrag,trinkgeld,distanz,dauer",
    "sort": "betrag asc"
})

# In Spark für ML
df = spark.createDataFrame(response.json()["response"]["docs"])

# Jetzt die komplexe Analyse
from pyspark.ml.stat import Correlation
from pyspark.ml.feature import VectorAssembler

assembler = VectorAssembler(inputCols=["betrag", "distanz", "dauer"], outputCol="features")
df_vector = assembler.transform(df)
corr_matrix = Correlation.corr(df_vector, "features").head()[0]
```

Die ML-Analyse läuft in Sekunden statt Stunden – weil sie auf fokussierten Daten arbeitet.

---

## Die User Journey: Vom Heuhaufen zur Erkenntnis

Lass mich den kompletten Flow visualisieren:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                           │
│  SCHRITT 1: Orientierung                                                  │
│  ════════════════════════                                                 │
│                                                                           │
│  User öffnet Dashboard. Sieht:                                            │
│                                                                           │
│     "Sie haben 147.382.910 Transaktionen"                                 │
│                                                                           │
│     Zeitraum     │  Region      │  Kategorie   │  Status                  │
│     ────────────────────────────────────────────────────                  │
│     2024: 52M    │  Nord: 41M   │  A: 67M      │  Aktiv: 140M             │
│     2023: 48M    │  Süd:  38M   │  B: 45M      │  Archiv: 7M              │
│     2022: 47M    │  Ost:  35M   │  C: 35M      │                          │
│                  │  West: 33M   │              │                          │
│                                                                           │
│  ⏱️ Ladezeit: 35ms                                                        │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ User klickt: "2024" + "Region Nord"
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                           │
│  SCHRITT 2: Drill-Down                                                    │
│  ═════════════════════                                                    │
│                                                                           │
│  Filter: 2024, Region Nord                                                │
│                                                                           │
│     "12.847.293 Transaktionen"                                            │
│                                                                           │
│     Kategorie    │  Status      │  Kunde        │  Produkt                │
│     ────────────────────────────────────────────────────────              │
│     A: 6.2M      │  Aktiv: 12M  │  Enterprise: 8M│  Premium: 4M           │
│     B: 4.1M      │  Archiv: 0.8M│  SMB: 3M       │  Standard: 6M          │
│     C: 2.5M      │              │  Startup: 1.8M │  Basic: 2.8M           │
│                                                                           │
│  ⏱️ Ladezeit: 28ms                                                        │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ User klickt: "Kategorie A" + "Enterprise"
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                           │
│  SCHRITT 3: Fokussierte Teilmenge                                         │
│  ════════════════════════════════                                         │
│                                                                           │
│  Filter: 2024, Region Nord, Kategorie A, Enterprise-Kunden                │
│                                                                           │
│     "2.847.293 Transaktionen"                                             │
│                                                                           │
│     Streaming Expression: Umsatz pro Monat                                │
│                                                                           │
│     Jan: €4.2M  │ Apr: €5.1M │ Jul: €3.8M │ Okt: €6.2M                    │
│     Feb: €3.9M  │ Mai: €5.5M │ Aug: €4.1M │ Nov: €5.8M                    │
│     Mär: €4.5M  │ Jun: €4.9M │ Sep: €5.3M │ Dez: €7.1M                    │
│                                                                           │
│  ⏱️ Aggregation: 180ms                                                    │
│                                                                           │
│  User denkt: "Interessant – warum der Einbruch im Juli?"                  │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ User klickt: "Juli-Daten nach Spark exportieren"
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                           │
│  SCHRITT 4: Tiefenanalyse                                                 │
│  ════════════════════════                                                 │
│                                                                           │
│  Spark lädt: 287.000 Juli-Transaktionen (nicht 147 Millionen!)            │
│                                                                           │
│  Korrelationsanalyse:                                                     │
│     - Starke Korrelation zwischen Umsatzeinbruch und                      │
│       Produktversion 2.3.x (-0.72)                                        │
│     - Cluster-Analyse zeigt: 3 Enterprise-Kunden machten                  │
│       85% des Einbruchs aus                                               │
│                                                                           │
│  Erkenntnis: Version 2.3.1 hatte einen Bug, der drei                      │
│              Großkunden zum Pausieren brachte.                            │
│                                                                           │
│  ⏱️ Analyse: 4.2 Sekunden                                                 │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

**Gesamtzeit von "147 Millionen Datensätze" bis "Bug in Version 2.3.1 gefunden": unter 10 Sekunden interaktiver Exploration.**

---

## Die vier Säulen im Detail

| Säule | Technologie | Aufgabe | Latenz |
|-------|-------------|---------|--------|
| **1. Vollständiger Index** | Solr mit Rohdaten | Alle Daten durchsuchbar und facettierbar | Einmaliger Import |
| **2. Facetten-Navigation** | Solr Facetten | Interaktive Multi-Dimensionale Exploration | <50ms pro Klick |
| **3. In-Solr Aggregation** | Streaming Expressions | Summen, Durchschnitte, Rankings ohne Spark | 100-500ms |
| **4. Deep Analytics** | Spark via /export | ML, Korrelationen, komplexe Statistik | Sekunden |

---

## Ehrlicher Vergleich mit den Alternativen

Ich will fair sein. Diese Architektur ist nicht für alles optimal. Hier der ehrliche Vergleich:

### ClickHouse oder DuckDB

**Wenn du es stattdessen nutzen solltest:**
- Du brauchst nur SQL-Aggregationen, keine interaktive Facetten-UI
- Deine Analysten schreiben SQL, keine explorative Navigation
- Du hast <10 Milliarden Rows und optimierte Queries

**Warum Solr+Spark trotzdem besser ist für Exploration:**
- Facetten in ClickHouse = N separate GROUP BY Queries
- Jeder Drill-Down-Klick = N weitere Queries
- Backend-Komplexität explodiert bei komplexen UIs
- Kein Tag/Exclude für Facetten (→ UI-Albtraum)

### Elasticsearch

**Praktisch gleichwertig** für die meisten Use Cases. Elasticsearch hat:
- Aggregations statt Facetten (ähnlich mächtig)
- Besseren Spark-Connector
- Mehr Enterprise-Features

**Warum ich Solr bevorzuge:**
- Streaming Expressions sind mächtiger als Elasticsearch Aggregations
- Einfacher zu betreiben (kein X-Pack Chaos)
- Solr Cloud ist battle-tested seit über 15 Jahren

### Druid oder Apache Pinot

**Wenn du es stattdessen nutzen solltest:**
- Real-Time Dashboards sind der Hauptfokus
- Du hast Time-Series mit bekannten Dimensionen
- Sub-Second Aggregationen über Milliarden Rows

**Warum Solr+Spark besser ist für Exploration:**
- Druid/Pinot brauchen vordefinierte Dimensionen beim Ingestion
- Keine Volltextsuche (Solr kann beides!)
- Weniger flexibel für ad-hoc Exploration

### Cloud-Native: Snowflake, BigQuery, Databricks

**Wenn du es stattdessen nutzen solltest:**
- Budget ist kein Problem
- Operations-Team ist klein oder nicht vorhanden
- Du bist bereits im Cloud-Ökosystem

**Warum Solr+Spark besser ist:**
- Keine laufenden Kosten bei großen Datenmengen
- Keine Vendor Lock-in
- Du kontrollierst alles
- Läuft auf 5 Intel NUCs genauso wie auf 500 Cloud-VMs

---

## Technische Umsetzung: So baust du es

### Der Import: Parallel mit lokalem Entry Point

Der Trick ist, **nicht durch den Driver zu gehen**. Jeder Spark Executor schreibt an seinen **lokalen Solr** (127.0.0.1) als Entry Point:

```
┌─────────────────────────────────────────────────────────────────┐
│  Spark liest Parquet optimiert (alle Row Groups parallel)       │
│  → 4 Executors × 4 Cores = 16 parallele Tasks                  │
│  → Jeder Executor schreibt an lokalen Solr (127.0.0.1:8983)    │
│                                                                 │
│  Hinweis: Lokaler Solr ist nur Entry Point!                    │
│  SolrCloud routet Dokumente basierend auf ID zum richtigen     │
│  Shard, der auf einem anderen Node liegen kann.                │
└─────────────────────────────────────────────────────────────────┘
```

```python
def import_to_solr_parallel(spark, parquet_path, collection, batch_size=2000):
    """
    Hochparalleler Import: Spark liest Parquet optimal, 
    Executors schreiben an lokalen Solr als Entry Point.
    
    Datenfluss:
      1. Spark liest Parquet mit optimiertem Reader
      2. Repartition auf 16 Partitionen = 4 Executors × 4 Cores
      3. Jeder Executor sendet an 127.0.0.1 als Entry Point
      4. SolrCloud routet zum richtigen Shard (ggf. anderer Node)
    
    Warum 4 Cores statt mehr?
      - Mehr Cores bringt keinen Vorteil (getestet mit 6 Cores)
      - Der Bottleneck ist SolrCloud-Routing, nicht Spark-Parallelität
      - 4 HT-Cores bleiben für Solr-Indexierung + OS
    """
    # Parquet laden (verteilt auf Executors)
    df = spark.read.parquet(parquet_path)
    
    # Optimale Parallelität: 16 Partitionen für 4 Executors × 4 Cores
    df = df.repartition(16)
    
    # Konfiguration broadcasten
    solr_port = spark.sparkContext.broadcast(8983)
    collection_bc = spark.sparkContext.broadcast(collection)
    
    def send_partition_to_local_solr(partition_index, iterator):
        """Sendet Partition an lokalen Solr (127.0.0.1) als Entry Point."""
        import requests
        import socket
        
        port = solr_port.value
        coll = collection_bc.value
        hostname = socket.gethostname()
        
        # Lokaler Solr als Entry Point - SolrCloud routet weiter
        url = f"http://127.0.0.1:{port}/solr/{coll}/update"
        
        batch = []
        count = 0
        
        for row in iterator:
            doc = row.asDict()
            batch.append(doc)
            
            if len(batch) >= batch_size:
                requests.post(url, json=batch, timeout=60)
                count += len(batch)
                batch = []
        
        if batch:
            requests.post(url, json=batch, timeout=60)
            count += len(batch)
        
        yield (partition_index, hostname, count)
    
    # Parallel auf allen Executors
    results = df.rdd.mapPartitionsWithIndex(send_partition_to_local_solr).collect()
    
    # Commit
    requests.post(f"http://solr:8983/solr/{collection}/update?commit=true", json=[])
    
    return sum(r[2] for r in results)
```

**Warum lokaler Entry Point?**
- Spart den ersten Netzwerk-Hop (Executor → Solr Entry Point)
- SolrCloud routet dann basierend auf Dokument-ID zum Shard Owner
- Bei 4 Shards auf 4 Nodes: ~75% der Dokumente werden weitergeleitet

**Throughput:** 50.000-100.000 Dokumente pro Sekunde, linear skalierend mit Cluster-Größe.

### Die Navigation: Facetten-API

```python
class FacetExplorer:
    def __init__(self, solr_url, collection):
        self.base_url = f"{solr_url}/solr/{collection}"
    
    def explore(self, facet_fields, filters=None):
        params = {
            "q": "*:*",
            "rows": 0,
            "facet": "true",
            "facet.field": facet_fields,
            "facet.limit": 20,
            "facet.mincount": 1
        }
        if filters:
            params["fq"] = filters
        
        response = requests.get(f"{self.base_url}/select", params=params)
        return response.json()["facet_counts"]["facet_fields"]

# Nutzung
explorer = FacetExplorer("http://solr:8983", "transactions")
facets = explorer.explore(
    facet_fields=["kategorie", "region", "status"],
    filters=["jahr:2024", "region:Nord"]
)
```

### Die Aggregation: Streaming Expressions

```python
def aggregate(collection, query, group_by, metrics):
    expr = f"""
    rollup(
      search({collection},
        q="{query}",
        fl="{group_by},{','.join(metrics)}",
        sort="{group_by} asc",
        qt="/export"
      ),
      over="{group_by}",
      {', '.join(f'sum({m}), avg({m})' for m in metrics)},
      count(*)
    )
    """
    
    response = requests.post(
        f"http://solr:8983/solr/{collection}/stream",
        data={"expr": expr}
    )
    return response.json()["result-set"]["docs"]
```

### Die Analyse: Spark via /export

```python
def analyze_subset(spark, solr_url, collection, query, fields):
    # Daten aus Solr streamen
    response = requests.get(
        f"{solr_url}/solr/{collection}/export",
        params={
            "q": query,
            "fl": fields,
            "sort": f"{fields.split(',')[0]} asc"
        }
    )
    
    docs = response.json()["response"]["docs"]
    
    # In Spark laden
    return spark.createDataFrame(docs)

# Nutzung
df = analyze_subset(
    spark,
    "http://solr:8983",
    "transactions",
    query="jahr:2024 AND region:Nord AND kategorie:A",
    fields="betrag,marge,kundentyp,produkt"
)

# Jetzt volle Spark-Power
df.stat.corr("betrag", "marge")
```

---

## Wann diese Architektur die richtige Wahl ist

### ✅ Perfekt für:

- **E-Commerce Analytics**: Produktkataloge mit Filter-Navigation, Conversion-Analyse
- **Log & Event Analytics**: Exploration von Millionen Server-Logs, Security-Events
- **Business Intelligence**: Self-Service Analytics für Business-User
- **IoT-Datenplattformen**: Sensor-Daten mit Drill-Down nach Gerät, Zeit, Metrik
- **Dokumenten-Management**: Suche + Kategorisierung + Analyse
- **Customer 360**: Alle Kundendaten durchsuchbar und analysierbar

### ⚠️ Nicht die beste Wahl für:

- **Pure Real-Time Dashboards**: Wenn du nur Live-Metriken brauchst → Druid/Pinot
- **Nur SQL-Aggregationen**: Wenn niemand Facetten nutzt → ClickHouse
- **Kleine Datenmengen** (<10GB): Overkill → DuckDB oder Pandas
- **Keine Exploration**: Wenn Queries immer gleich sind → beliebige DB

---

## Fazit: Warum ich nach 10 Jahren immer noch dabei bleibe

Als ich diese Architektur 2016 zum ersten Mal eingesetzt habe, gab es den Begriff "Data Lakehouse" noch nicht. Hadoop war der heiße Scheiß. Lambda Architecture war das Buzzword.

Heute, 10 Jahre später, ist vieles anders:
- Hadoop ist quasi tot
- Lambda Architecture gilt als Antipattern
- Dutzende neue OLAP-Engines sind erschienen

Und trotzdem: **Diese Kombination aus Solr und Spark funktioniert immer noch.**

Warum? Weil sie auf einem fundamentalen Prinzip basiert, das sich nicht ändert:

> **Facetten sind der erste gute Weg, die Datenmengen beherrschbar einzuschränken.**

Bevor du analysieren kannst, musst du finden. Bevor du finden kannst, musst du navigieren. Und für Navigation in großen Datenmengen ist ein invertierter Index mit Facetten einfach das richtige Werkzeug.

Die Tools mögen sich ändern. Die Cloud mag billiger werden. LLMs mögen SQL schreiben können.

Aber das Grundproblem bleibt: **Menschen müssen große Datenmengen verstehen.** Und dafür brauchst du interaktive Exploration mit sub-sekunden Latenz.

Diese Architektur liefert das. Seit 2010. Ohne Vendor Lock-in. Auf jedem Cluster.

---

*Dieser Artikel basiert auf einem realen Setup: 5 Intel NUCs, Solr Cloud mit 4 Nodes, Spark mit 4 Workers, ~6 Millionen NYC Taxi-Fahrten als Demo-Datensatz. Alles Open Source. Alles reproduzierbar.*

---

**Über den Autor**

Ich baue seit über 15 Jahren Datenplattformen. Von Enterprise Data Warehouses über Hadoop-Cluster bis zu modernen Cloud-Architekturen. Diese Kombination aus Solr und Spark ist eine der wenigen, die ich immer wieder empfehle – weil sie einfach funktioniert.

*Fragen? Feedback? Erreiche mich auf X johannes.weigend*
