#!/usr/bin/env python3
"""
Prometheus to Dimensional Model Transformer v3

Transformiert Prometheus-Metriken in ein fixes dimensionales Schema:
ProcessGroup | Process | HostGroup | Host | MetricGroup | Metric

Regeln:
1. ProcessGroup = job (1:1)
2. Process = instance URL (vollständig)
3. Host = erster Teil von instance (vor dem Punkt)
4. HostGroup = "cluster" (konstant)
5. MetricGroup = job (Basis), ggf. erweitert bei vielen Label-Varianten
6. Metric = Metrikname (ohne job-Präfix) + Labels als suffix

Erweiterungslogik:
- Wenn Metrikname mit job+"_" beginnt → job-Präfix entfernen
- Bei vielen Label-Varianten → Teile des Metriknamens in MetricGroup verschieben
- Beispiel: solr_metrics_core_errors (viele Labels) → MetricGroup=solr_metrics_core, Metric=errors

Usage:
    python prometheus_to_dimensional_v3.py [--url URL] [--output FILE] [--threshold N]
"""

import argparse
import csv
import sys
from collections import defaultdict
from datetime import datetime

import requests


def log(msg: str):
    """Print mit sofortigem Flush."""
    print(msg, flush=True)


# ============================================================================
# Konfiguration nach Konzept
# ============================================================================

# Labels die ignoriert werden (redundant oder konstant)
IGNORE_LABELS = {'base_url', 'cluster_id', 'core', 'fstype', '__name__'}

# Standard-Labels (werden zu ProcessGroup/Process/Host)
STANDARD_LABELS = {'job', 'instance'}

# Quantil → Suffix Mapping
QUANTILE_SUFFIX = {
    '0.5': '_p50',
    '0.75': '_p75',
    '0.9': '_p90',
    '0.95': '_p95',
    '0.99': '_p99',
    '0.999': '_p999',
    '1': '_p100',
}

# Schwellwert: Ab dieser Anzahl Label-Varianten wird MetricGroup erweitert
DEFAULT_EXPANSION_THRESHOLD = 100


# ============================================================================
# Prometheus Client
# ============================================================================

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
    
    def get_all_series(self, metric_names: list[str]) -> list[dict[str, str]]:
        """Alle Zeitreihen (Label-Kombinationen) abrufen."""
        url = f"{self.base_url}/api/v1/series"
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


# ============================================================================
# Hilfs-Funktionen
# ============================================================================

def extract_host(instance: str) -> str:
    """Extrahiert den Host aus der instance URL."""
    if not instance:
        return ''
    # node1.cloud.local:9100 → node1
    host = instance.split('.')[0]
    # Falls kein Punkt vorhanden: vor dem Doppelpunkt
    if '.' not in instance and ':' in host:
        host = host.split(':')[0]
    return host


def is_info_metric(metric_name: str) -> bool:
    """Prüft ob es eine _info Metrik ist (werden ignoriert)."""
    return metric_name.endswith('_info')


def strip_job_prefix(metric_name: str, job: str) -> str:
    """
    Entfernt das Job-Präfix vom Metriknamen wenn vorhanden.
    
    Beispiel: solr_metrics_core_errors (job=solr) → metrics_core_errors
    """
    if job and metric_name.startswith(job + '_'):
        return metric_name[len(job) + 1:]
    return metric_name


def build_label_suffix(labels: dict[str, str]) -> tuple[str, str | None]:
    """
    Baut den Label-Suffix für den Metriknamen.
    
    Returns: (suffix, quantile_suffix)
    """
    filtered_labels = {}
    quantile_suffix = None
    
    for label, value in labels.items():
        # Standard und ignorierte Labels überspringen
        if label in STANDARD_LABELS or label in IGNORE_LABELS:
            continue
        
        # Histogram-Spezialbehandlung
        if label == 'quantile':
            quantile_suffix = QUANTILE_SUFFIX.get(value, f'_p{value.replace(".", "")}')
            continue
        if label == 'le':
            # le-Labels werden ignoriert (nur _sum/_count verwenden)
            continue
        
        filtered_labels[label] = value
    
    # Suffix bauen: alphabetisch sortiert
    suffix_parts = []
    for label in sorted(filtered_labels.keys()):
        value = filtered_labels[label]
        # Sonderzeichen im Value behandeln
        safe_value = value.replace('/', '_').replace(' ', '_')
        suffix_parts.append(f"{label}_{safe_value}")
    
    suffix = '_'.join(suffix_parts) if suffix_parts else ''
    return suffix, quantile_suffix


def count_label_variants(labels: dict[str, str]) -> int:
    """Zählt die Anzahl relevanter Labels (ohne STANDARD und IGNORE)."""
    count = 0
    for label in labels:
        if label not in STANDARD_LABELS and label not in IGNORE_LABELS and label != 'quantile' and label != 'le':
            count += 1
    return count


# ============================================================================
# Analyse-Pass
# ============================================================================

def analyze_metrics(series_list: list[dict[str, str]]) -> dict[tuple[str, str], int]:
    """
    Analysiert alle Serien und zählt Varianten pro (job, prefix).
    
    Zählt für JEDEN Präfix, nicht nur den kompletten Metriknamen.
    Das ermöglicht rekursive Erweiterung.
    
    Beispiel: metrics_core_query_errors_total wird gezählt für:
      - (job, metrics)
      - (job, metrics_core)
      - (job, metrics_core_query)
      - (job, metrics_core_query_errors)
      - (job, metrics_core_query_errors_total)
    
    Returns: Dict mit {(job, prefix): variant_count}
    """
    prefix_counts = defaultdict(int)
    
    for series in series_list:
        metric_name = series.get('__name__', '')
        if is_info_metric(metric_name):
            continue
            
        job = series.get('job', '')
        stripped = strip_job_prefix(metric_name, job)
        
        # Zähle für alle Präfix-Längen
        parts = stripped.split('_')
        for i in range(1, len(parts) + 1):
            prefix = '_'.join(parts[:i])
            prefix_counts[(job, prefix)] += 1
    
    return dict(prefix_counts)


def determine_expansion(stripped_metric: str, job: str, prefix_counts: dict, threshold: int) -> tuple[str, str]:
    """
    Bestimmt rekursiv wie viel vom Metriknamen in die MetricGroup verschoben wird.
    
    Logik: Erweitere solange der aktuelle Präfix > threshold Varianten hat.
    
    Returns: (group_extension, remaining_metric)
    """
    parts = stripped_metric.split('_')
    
    if len(parts) <= 1:
        return '', stripped_metric
    
    # Rekursiv den optimalen Split-Punkt finden
    # Starte mit 1 Teil und erweitere solange > threshold
    best_split = 0  # 0 = keine Erweiterung
    
    for i in range(1, len(parts)):
        prefix = '_'.join(parts[:i])
        count = prefix_counts.get((job, prefix), 0)
        
        if count > threshold:
            # Dieser Präfix hat noch zu viele → erweitern
            best_split = i
        else:
            # Unter threshold → hier aufhören
            break
    
    if best_split == 0:
        return '', stripped_metric
    
    group_ext = '_'.join(parts[:best_split])
    remaining = '_'.join(parts[best_split:]) if best_split < len(parts) else parts[-1]
    
    return group_ext, remaining


# ============================================================================
# Transformation
# ============================================================================

def transform_series(series: dict[str, str], prefix_counts: dict, threshold: int) -> dict[str, str] | None:
    """
    Transformiert eine Prometheus-Serie in das dimensionale Schema.
    
    Returns None wenn die Serie ignoriert werden soll.
    """
    metric_name = series.get('__name__', '')
    
    # Info-Metriken ignorieren
    if is_info_metric(metric_name):
        return None
    
    # Standard-Labels extrahieren
    job = series.get('job', '')
    instance = series.get('instance', '')
    
    # Job-Präfix entfernen
    stripped = strip_job_prefix(metric_name, job)
    
    # Erweiterung bestimmen (rekursiv basierend auf Präfix-Zählungen)
    group_extension, base_metric = determine_expansion(stripped, job, prefix_counts, threshold)
    
    # MetricGroup bauen: job + optionale Erweiterung
    if group_extension:
        metric_group = f"{job}_{group_extension}" if job else group_extension
    else:
        metric_group = job if job else stripped.split('_')[0]
    
    # Label-Suffix bauen
    label_suffix, quantile_suffix = build_label_suffix(series)
    
    # Metric zusammenbauen
    metric = base_metric
    if label_suffix:
        metric = f"{metric}_{label_suffix}"
    if quantile_suffix:
        metric = f"{metric}{quantile_suffix}"
    
    return {
        'ProcessGroup': job,
        'Process': instance,
        'HostGroup': 'cluster',
        'Host': extract_host(instance),
        'MetricGroup': metric_group,
        'Metric': metric
    }


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Transformiert Prometheus-Metriken in ein dimensionales Modell'
    )
    parser.add_argument(
        '--url',
        default='http://node0.cloud.local:9090',
        help='Prometheus URL (default: http://node0.cloud.local:9090)'
    )
    parser.add_argument(
        '--output',
        default=f'prometheus_dimensional_{datetime.now():%Y%m%d_%H%M%S}.csv',
        help='Output CSV Datei'
    )
    parser.add_argument(
        '--threshold',
        type=int,
        default=DEFAULT_EXPANSION_THRESHOLD,
        help=f'Schwellwert für MetricGroup-Erweiterung (default: {DEFAULT_EXPANSION_THRESHOLD})'
    )
    args = parser.parse_args()
    
    log(f"Prometheus Dimensional Transformer v4")
    log(f"=====================================")
    log(f"URL: {args.url}")
    log(f"Threshold: {args.threshold}")
    log(f"Output: {args.output}")
    log("")
    
    try:
        client = PrometheusClient(args.url)
        
        # 1. Alle Metriknamen holen
        log("1. Hole Metriknamen...")
        metric_names = client.get_all_metric_names()
        log(f"   {len(metric_names)} Metriken gefunden")
        
        # 2. Alle Serien holen
        log("2. Hole Serien (Label-Kombinationen)...")
        all_series = client.get_all_series(metric_names)
        log(f"   {len(all_series)} Serien gefunden")
        
        # 3. Analyse: Präfix-Zählungen für rekursive Erweiterung
        log("3. Analysiere Präfixe (für rekursive Erweiterung)...")
        prefix_counts = analyze_metrics(all_series)
        log(f"   {len(prefix_counts)} (job, prefix) Kombinationen analysiert")
        
        # Top-Präfixe mit vielen Varianten
        high_variant = [(k, v) for k, v in prefix_counts.items() if v > args.threshold]
        if high_variant:
            log(f"   Präfixe über Threshold ({args.threshold}):")
            for (job, prefix), count in sorted(high_variant, key=lambda x: -x[1])[:15]:
                log(f"     {job}/{prefix}: {count} Varianten")
        
        # 4. Transformation
        log("4. Transformiere Serien...")
        transformed = []
        seen = set()  # Für Deduplizierung
        
        for series in all_series:
            row = transform_series(series, prefix_counts, args.threshold)
            if row:
                # Deduplizierung
                key = tuple(row.values())
                if key not in seen:
                    seen.add(key)
                    transformed.append(row)
        
        log(f"   {len(transformed)} eindeutige Zeilen transformiert")
        
        # 5. Statistiken
        log("5. Statistiken:")
        metric_groups = defaultdict(int)
        for row in transformed:
            metric_groups[row['MetricGroup']] += 1
        
        log(f"   {len(metric_groups)} MetricGroups:")
        for group, count in sorted(metric_groups.items(), key=lambda x: -x[1]):
            log(f"     {group}: {count} Metriken")
        
        # 6. CSV schreiben
        log(f"6. Schreibe CSV: {args.output}")
        with open(args.output, 'w', newline='') as f:
            fieldnames = ['ProcessGroup', 'Process', 'HostGroup', 'Host', 'MetricGroup', 'Metric']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in sorted(transformed, key=lambda x: (x['MetricGroup'], x['Metric'])):
                writer.writerow(row)
        
        log("")
        log(f"Fertig! {len(transformed)} Zeilen in {args.output}")
        
    except requests.RequestException as e:
        log(f"Fehler bei Prometheus-Anfrage: {e}")
        sys.exit(1)
    except Exception as e:
        log(f"Fehler: {e}")
        raise


if __name__ == '__main__':
    main()
