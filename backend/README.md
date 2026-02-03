# Taxi Routes Backend

Flask + PySpark Backend für die Routen-Analyse.

## Voraussetzungen

- Python 3.11+
- Zugang zum Spark-Cluster (`node1.cloud.local:7077`)
- Solr-Spark Connector

## Installation auf dem Cluster

```bash
# Auf node1 einloggen
ssh node1.cloud.local

# Virtualenv erstellen
cd /opt
sudo mkdir -p taxi-backend
sudo chown $USER taxi-backend
cd taxi-backend

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Spark-Solr Connector herunterladen
wget https://repo1.maven.org/maven2/com/lucidworks/spark/spark-solr/4.0.2/spark-solr-4.0.2-shaded.jar \
    -O spark-solr.jar
```

## Starten

```bash
# Mit Spark-Solr Connector
export PYSPARK_SUBMIT_ARGS="--jars /opt/taxi-backend/spark-solr.jar pyspark-shell"
source venv/bin/activate
python app.py
```

## API Endpoints

### GET /api/health
Health Check

### POST /api/count
Zählt Fahrten für Filter (schnell, direkt Solr)

```json
{
  "filters": {
    "pickup_dayofweek": [6, 7],
    "pickup_hour": [18, 19, 20]
  }
}
```

### POST /api/top-routes
Berechnet Top 5 lukrativsten Routen (Spark-Job)

```json
{
  "filters": {
    "pickup_dayofweek": [6, 7],
    "pickup_hour": [18, 19, 20]
  },
  "limit": 5
}
```

Response:
```json
{
  "routes": [
    {
      "PULocationID": 132,
      "DOLocationID": 265,
      "trip_count": 1234,
      "avg_fare": 45.50,
      "avg_duration_min": 22.5,
      "avg_distance": 12.3,
      "score": 2486.67,
      "fare_per_minute": 2.02
    }
  ],
  "total_trips": 50000,
  "query": "pickup_dayofweek:(6 OR 7) AND ..."
}
```

## Lukrativitäts-Score

```
Score = (trip_count × avg_fare) / avg_duration_min
```

- **Hohe Frequenz**: Viele Fahrten auf der Route → wenig Wartezeit
- **Hoher Fahrpreis**: Mehr Umsatz pro Fahrt
- **Kurze Dauer**: Mehr Fahrten pro Stunde möglich
