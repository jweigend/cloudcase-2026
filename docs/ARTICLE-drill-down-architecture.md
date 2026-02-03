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

### Der Trick: Paralleles Shard-Loading via /export

Hier passiert die eigentliche Magie. Statt alle Daten über einen einzelnen Solr-Node zu ziehen, **lädt jeder Spark Executor direkt von seinem lokalen Shard**:

```
┌─────────────────────────────────────────────────────────────────┐
│  PARALLELES LESEN: Jeder Executor → Lokaler Shard               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Spark holt Shard→Node Mapping via CLUSTERSTATUS API        │
│     → shard1: node1, shard2: node2, shard3: node3, shard4: node4│
│                                                                 │
│  2. Shards werden als RDD parallelisiert (1 Partition/Shard)   │
│                                                                 │
│  3. Jeder Executor ruft /export auf SEINEM lokalen Shard:      │
│                                                                 │
│     Executor 1 ──► node1:8983/solr/core_shard1/export ──┐      │
│     Executor 2 ──► node2:8983/solr/core_shard2/export ──┼──► RDD│
│     Executor 3 ──► node3:8983/solr/core_shard3/export ──┤      │
│     Executor 4 ──► node4:8983/solr/core_shard4/export ──┘      │
│                                                                 │
│  Ergebnis: 4x paralleler I/O, kein Single-Node-Bottleneck!     │
└─────────────────────────────────────────────────────────────────┘
```

**Warum das entscheidend ist:**

| Ansatz | Durchsatz | Bottleneck |
|--------|-----------|------------|
| Naiv: `/export` an Collection | ~500k Docs/s | Ein Node sammelt von allen Shards |
| **Parallel: `/export` pro Shard** | ~2M Docs/s | Kein Bottleneck, lineares Scaling |

Der `/export` Handler ist dafür perfekt: Er streamt alle Ergebnisse sortiert, nutzt DocValues (kein Heap-Verbrauch), und arbeitet auf dem **lokalen Core** ohne Netzwerk-Overhead.

### Das Pattern: Schreiben und Lesen symmetrisch

```
SCHREIBEN (Import):
  Executor → 127.0.0.1:8983 → SolrCloud routet zu Shard

LESEN (Export):  
  Executor → node:8983/core_shardN/export → Direkt vom Shard
```

Beide Richtungen nutzen Data Locality. Das ist der Kern dieser Architektur.

### Fokussierte Daten, schnelle Analyse

Du hast via Facetten bereits die interessante Teilmenge identifiziert. Statt 100 Millionen Datensätze lädst du nur die relevanten 50.000 nach Spark – und das parallel von allen Shards.

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

| Säule | Technologie | Aufgabe | Latenz | Data Locality |
|-------|-------------|---------|--------|---------------|
| **1. Import** | Spark → lokaler Solr | Paralleler Push, SolrCloud routet | Minuten | Executor → 127.0.0.1 |
| **2. Facetten** | Solr Facetten + Tag/Exclude | Multi-Select Navigation | <50ms | Distributed |
| **3. Aggregation** | Streaming Expressions | Summen, Rankings ohne Spark | 100-500ms | Distributed |
| **4. Deep Analytics** | Spark via /export | ML, Korrelationen, Statistik | Sekunden | Executor → lokaler Shard |

**Der Trick:** Sowohl Import als auch Export nutzen Data Locality. Kein zentraler Bottleneck.

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

## Technische Umsetzung: Die Kernprinzipien

Die vollständige Implementierung liegt im Repository. Hier die Kernideen:

### 1. Import: Executor → Lokaler Solr als Entry Point

```python
# Jeder Executor schreibt an 127.0.0.1 (lokaler Solr)
url = f"http://127.0.0.1:8983/solr/{collection}/update"
requests.post(url, json=batch)
# → SolrCloud routet automatisch zum richtigen Shard
```

**Warum:** Spart den ersten Netzwerk-Hop. Bei 4 Nodes werden ~75% weitergeleitet, aber der lokale Entry Point ist trotzdem schneller als ein zentraler.

### 2. Export: Executor → Direkt zum lokalen Shard

```python
# Shard-Mapping holen
shard_info = get_shard_info(collection)  
# → [{'node': 'node1', 'core': 'collection_shard1_replica'}, ...]

# Parallel von allen Shards laden
for shard in shard_info:
    url = f"http://{shard['node']}:8983/solr/{shard['core']}/export"
    # → Jeder Executor ruft SEINEN lokalen Shard ab
```

**Warum:** Kein Single-Node-Bottleneck. 4x paralleler I/O.

### 3. Facetten mit Tag/Exclude

```python
# Facetten mit lokalem Exclude für Multi-Select UI
params = {
    "q": "*:*",
    "fq": "{!tag=payment}payment_type:1",  # Tagged Filter
    "facet.field": "{!ex=payment}payment_type",  # Exclude beim Zählen
}
# → Facette zeigt alle Werte, nicht nur den gefilterten
```

**Warum:** Ermöglicht Mehrfachauswahl ohne dass Facetten-Werte verschwinden.

### 4. Streaming Expressions für In-Solr Aggregation

```python
expr = f'''
rollup(
  search({collection}, q="{query}", fl="{fields}", sort="{sort}", qt="/export"),
  over="{group_by}",
  sum(amount), avg(amount), count(*)
)
'''
```

**Warum:** 80% der Aggregationen brauchen kein Spark. Latenz: 100-500ms statt Sekunden.

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
