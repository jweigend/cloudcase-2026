#!/usr/bin/env python3
"""
Prometheus Metrics to CSV Exporter

Exportiert alle Prometheus-Metriken als filterbare CSV-Matrix.
- Zeilen: Jede Metrik (mit eindeutiger Label-Kombination)
- Spalten: Alle vorkommenden Labels + Metadaten

Usage:
    python prometheus_metrics_to_csv.py [--url URL] [--output FILE]
    
Beispiele:
    python prometheus_metrics_to_csv.py
    python prometheus_metrics_to_csv.py --url http://node0.cloud.local:9090 --output metrics.csv
"""

import argparse
import csv
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any

import requests


def log(msg: str):
    """Print mit sofortigem Flush."""
    print(msg, flush=True)


class PrometheusClient:
    """Client für Prometheus HTTP API."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        
    def get_all_metric_names(self) -> list[str]:
        """Alle Metriknamen von Prometheus abrufen."""
        url = f"{self.base_url}/api/v1/label/__name__/values"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        if data['status'] != 'success':
            raise RuntimeError(f"Prometheus API Fehler: {data}")
        return sorted(data['data'])
    
    def get_metric_metadata(self) -> dict[str, list[dict]]:
        """Metadaten (Typ, Hilfetext) für alle Metriken abrufen."""
        url = f"{self.base_url}/api/v1/metadata"
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            if data['status'] == 'success':
                return data['data']
        except Exception as e:
            log(f"Warnung: Konnte Metadaten nicht laden: {e}")
        return {}
    
    def get_all_series(self, metric_names: list[str] = None) -> list[dict[str, str]]:
        """Alle Zeitreihen (Label-Kombinationen) abrufen.
        
        Wenn metric_names None ist, werden alle Serien abgerufen.
        """
        url = f"{self.base_url}/api/v1/series"
        
        if metric_names:
            # Batch-Abfrage für mehrere Metriken
            all_series = []
            batch_size = 50
            for i in range(0, len(metric_names), batch_size):
                batch = metric_names[i:i+batch_size]
                params = [('match[]', name) for name in batch]
                response = requests.get(url, params=params, timeout=60)
                response.raise_for_status()
                data = response.json()
                if data['status'] == 'success':
                    all_series.extend(data['data'])
                if (i + batch_size) % 200 == 0:
                    log(f"  Serien abgerufen: {min(i+batch_size, len(metric_names))}/{len(metric_names)}...")
            return all_series
        else:
            # Alle Serien auf einmal
            params = {'match[]': '{__name__=~".+"}'}
            response = requests.get(url, params=params, timeout=120)
            response.raise_for_status()
            data = response.json()
            if data['status'] != 'success':
                raise RuntimeError(f"Prometheus API Fehler: {data}")
            return data['data']


def create_metrics_matrix(client: PrometheusClient) -> tuple[list[dict], list[str]]:
    """Erstellt die Metrik-Matrix.
    
    Format: Eine Zeile pro Metrik+Label Kombination.
    job und instance als eigene Spalten (immer gesetzt, eindeutige Bedeutung).
    
    Beispiel:
        metric_name,_type,job,instance,label,count,values
        node_cpu_seconds_total,counter,node,"node0:9100, ...",mode,8,idle, user, ...
    
    Returns:
        Tuple aus (Liste der Zeilen, Liste der Spaltennamen)
    """
    log("Lade Metriknamen...")
    metric_names = client.get_all_metric_names()
    log(f"Gefunden: {len(metric_names)} Metriken")
    
    log("Lade Metadaten...")
    metadata = client.get_metric_metadata()
    
    log("Lade alle Zeitreihen...")
    all_series = client.get_all_series(metric_names)
    log(f"Gefunden: {len(all_series)} Zeitreihen")
    
    # Metriken aggregieren: Pro Metrik-Name alle Label-Werte sammeln
    from collections import defaultdict
    metrics_data = defaultdict(lambda: defaultdict(set))
    
    for series in all_series:
        metric_name = series.get('__name__', 'unknown')
        for label, value in series.items():
            if label != '__name__':
                metrics_data[metric_name][label].add(value)
    
    log(f"Aggregiert zu {len(metrics_data)} eindeutigen Metriken")
    
    def format_values(values_set):
        """Formatiert Werte: count und 2 Beispiele + ..."""
        values = sorted(values_set)
        count = len(values)
        if count <= 2:
            values_str = ', '.join(values)
        else:
            values_str = f"{values[0]}, {values[1]}, ..."
        return count, values_str
    
    # Matrix erstellen - eine Zeile pro Metrik+Label Kombination
    rows = []
    for metric_name in sorted(metrics_data.keys()):
        labels_data = metrics_data[metric_name]
        
        # Metadaten
        meta = metadata.get(metric_name, [{}])
        if isinstance(meta, list) and meta:
            meta = meta[0]
        metric_type = meta.get('type', '')
        
        # job und instance für eigene Spalten
        job_count, job_values = format_values(labels_data.get('job', set()))
        instance_count, instance_values = format_values(labels_data.get('instance', set()))
        
        # Andere Labels (nicht job/instance)
        other_labels = [l for l in sorted(labels_data.keys()) if l not in ('job', 'instance')]
        
        if other_labels:
            # Eine Zeile pro zusätzliches Label
            for label in other_labels:
                count, values_str = format_values(labels_data[label])
                rows.append({
                    'metric_name': metric_name,
                    '_type': metric_type,
                    'job': job_values,
                    'instance': instance_values,
                    'label': label,
                    'count': count,
                    'values': values_str,
                })
        else:
            # Metrik hat nur job/instance - trotzdem eine Zeile
            rows.append({
                'metric_name': metric_name,
                '_type': metric_type,
                'job': job_values,
                'instance': instance_values,
                'label': '',
                'count': '',
                'values': '',
            })
    
    columns = ['metric_name', '_type', 'job', 'instance', 'label', 'count', 'values']
    
    return rows, columns


def fill_gaps(rows: list[dict], columns: list[str]) -> list[dict]:
    """Füllt Lücken in der Matrix für bessere Filterbarkeit."""
    filled_rows = []
    
    for row in rows:
        filled_row = {}
        for col in columns:
            value = row.get(col, '')
            if value == '' or value is None:
                # Sinnvolle Defaults basierend auf Spalte
                if col.startswith('_'):
                    filled_row[col] = 'n/a'
                else:
                    filled_row[col] = ''  # Leere Label-Spalten
            else:
                filled_row[col] = value
        filled_rows.append(filled_row)
    
    return filled_rows


def write_csv(rows: list[dict], columns: list[str], output_file: str):
    """Schreibt die Matrix als CSV."""
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        # Beschreibungszeile mit Prometheus-Feldbezeichnungen
        descriptions = {
            'metric_name': '__name__',
            '_type': 'metadata.type',
            'job': 'label:job',
            'instance': 'label:instance',
            'label': 'label:*',
            'count': '(aggregiert)',
            'values': '(aggregiert)',
        }
        desc_row = [descriptions.get(col, col) for col in columns]
        f.write('# ' + ','.join(desc_row) + '\n')
        
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    
    log(f"CSV geschrieben: {output_file}")
    log(f"  Zeilen: {len(rows)}")
    log(f"  Spalten: {len(columns)}")


def main():
    parser = argparse.ArgumentParser(
        description='Exportiert Prometheus-Metriken als filterbare CSV-Matrix.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
    %(prog)s
    %(prog)s --url http://node0.cloud.local:9090
    %(prog)s --output my_metrics.csv
        """
    )
    parser.add_argument(
        '--url', 
        default='http://node0.cloud.local:9090',
        help='Prometheus URL (default: http://node0.cloud.local:9090)'
    )
    parser.add_argument(
        '--output', '-o',
        default=None,
        help='Ausgabedatei (default: prometheus_metrics_TIMESTAMP.csv)'
    )
    
    args = parser.parse_args()
    
    # Output-Dateiname generieren
    if args.output:
        output_file = args.output
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f'prometheus_metrics_{timestamp}.csv'
    
    log(f"Prometheus URL: {args.url}")
    log(f"Ausgabedatei: {output_file}")
    log("")
    
    try:
        client = PrometheusClient(args.url)
        
        # Matrix erstellen
        rows, columns = create_metrics_matrix(client)
        
        # Lücken füllen
        rows = fill_gaps(rows, columns)
        
        # Als CSV schreiben
        write_csv(rows, columns, output_file)
        
        log("")
        log("Fertig!")
        log(f"Die CSV kann in Excel, LibreOffice oder mit pandas gefiltert werden.")
        
    except requests.exceptions.ConnectionError as e:
        log(f"Fehler: Kann nicht mit Prometheus verbinden: {args.url}")
        log(f"  Ist Prometheus erreichbar?")
        sys.exit(1)
    except Exception as e:
        log(f"Fehler: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
