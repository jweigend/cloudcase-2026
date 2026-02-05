#!/usr/bin/env python3
"""
Prometheus Metric Mapper Tool

Maps Prometheus metrics to a structured format:
- HOSTGROUP/HOST (e.g., Democluster/node0)
- METRICGROUP/METRIC (e.g., jvm/heap_memory_used)
- PROCESSGROUP/PROCESS (e.g., zookeeper/java)
- MEASUREMENT (role, e.g., master, worker)

Usage:
    python prometheus_mapper.py [--url URL] [--output FILE] [--rules FILE]
"""

import argparse
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
import yaml


def log(msg: str):
    """Print with immediate flush."""
    print(msg, flush=True)


@dataclass
class MappingRule:
    """A single mapping rule with optional wildcards."""
    pattern: str
    label_conditions: dict[str, str] = field(default_factory=dict)
    hostgroup: Any = None
    host: Any = None
    metricgroup: Any = None
    metric: Any = None
    processgroup: Any = None
    process: Any = None
    measurement: Any = None


@dataclass 
class MetricInfo:
    """Information about a Prometheus metric."""
    name: str
    labels: set[str]
    label_values: dict[str, set[str]]
    metric_type: str = "unknown"
    help_text: str = ""


class PrometheusClient:
    """Client for Prometheus HTTP API."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        
    def get_all_metric_names(self) -> list[str]:
        """Get all metric names from Prometheus."""
        url = f"{self.base_url}/api/v1/label/__name__/values"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        if data['status'] != 'success':
            raise RuntimeError(f"Prometheus API error: {data}")
        return sorted(data['data'])
    
    def get_metric_metadata(self) -> dict[str, dict]:
        """Get metadata (type, help) for all metrics."""
        url = f"{self.base_url}/api/v1/metadata"
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            if data['status'] == 'success':
                return data['data']
        except Exception:
            pass
        return {}
    
    def get_series_for_metric(self, metric_name: str) -> list[dict[str, str]]:
        """Get all time series (label combinations) for a metric."""
        url = f"{self.base_url}/api/v1/series"
        params = {'match[]': metric_name}
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        if data['status'] != 'success':
            raise RuntimeError(f"Prometheus API error: {data}")
        return data['data']


class MetricAnalyzer:
    """Analyzes Prometheus metrics and extracts structure."""
    
    def __init__(self, client: PrometheusClient):
        self.client = client
        self.metrics: dict[str, MetricInfo] = {}
        
    def analyze_all_metrics(self) -> dict[str, MetricInfo]:
        """Fetch and analyze all metrics from Prometheus."""
        log("Fetching metric names...")
        metric_names = self.client.get_all_metric_names()
        log(f"Found {len(metric_names)} metrics")
        
        log("Fetching metric metadata...")
        metadata = self.client.get_metric_metadata()
        
        log("Analyzing metric labels (this may take a while)...")
        total = len(metric_names)
        
        for i, name in enumerate(metric_names):
            if (i + 1) % 50 == 0 or i == 0:
                log(f"  Processing {i+1}/{total}...")
            
            try:
                series = self.client.get_series_for_metric(name)
            except Exception as e:
                log(f"  Warning: Could not fetch series for {name}: {e}")
                continue
                
            labels = set()
            label_values = defaultdict(set)
            
            for s in series:
                for label, value in s.items():
                    if label != '__name__':
                        labels.add(label)
                        label_values[label].add(value)
            
            meta = metadata.get(name, [{}])
            if isinstance(meta, list) and meta:
                meta = meta[0]
            
            self.metrics[name] = MetricInfo(
                name=name,
                labels=labels,
                label_values=dict(label_values),
                metric_type=meta.get('type', 'unknown'),
                help_text=meta.get('help', '')
            )
        
        log(f"Analyzed {len(self.metrics)} metrics")
        return self.metrics
    
    def group_by_prefix(self) -> dict[str, list[MetricInfo]]:
        """Group metrics by their prefix (first part before _)."""
        groups = defaultdict(list)
        for metric in self.metrics.values():
            parts = metric.name.split('_')
            prefix = parts[0] if len(parts) > 1 else metric.name
            groups[prefix].append(metric)
        return dict(groups)


class InteractiveMapper:
    """Interactive tool for creating mapping rules.
    
    Target structure hierarchy:
    - HOSTGROUP (collection) → HOST (element): e.g., Democluster → node0, node1
    - METRICGROUP (collection) → METRIC (element): e.g., jvm → heap_memory_used
    - PROCESSGROUP (collection) → PROCESS (element): e.g., spark → spark-master
    - MEASUREMENT: role/instance type, e.g., master, worker, leader
    """
    
    KNOWN_HOSTGROUPS = ["Democluster"]
    # PROCESSGROUP = application/service category
    KNOWN_PROCESSGROUPS = ["spark", "solr", "zookeeper", "node", "prometheus", "grafana"]
    # METRICGROUP = technical/functional metric category  
    KNOWN_METRICGROUPS = ["memory", "cpu", "disk", "network", "gc", "threads", "query", "latency", "connections", "cache", "io", "http", "health"]
    # MEASUREMENT = role within the process group
    KNOWN_MEASUREMENTS = ["master", "worker", "leader", "follower", "standalone", "server"]
    
    def __init__(self, metrics: dict[str, MetricInfo], auto_mode: bool = False):
        self.metrics = metrics
        self.rules: list[dict] = []
        self.learned_patterns: dict[str, dict] = {}
        self.auto_mode = auto_mode
        
    def extract_host_from_instance(self, instance: str) -> str:
        """Extract hostname from instance label."""
        if ':' in instance:
            return instance.split(':')[0]
        return instance
    
    def guess_metricgroup(self, metric_name: str) -> str:
        """Guess metric group (technical category) from metric name.
        
        METRICGROUP is the technical/functional category:
        memory, cpu, disk, network, gc, threads, query, latency, etc.
        """
        name_lower = metric_name.lower()
        
        # Memory related
        if any(x in name_lower for x in ['memory', 'heap', 'buffer', 'pool', 'bytes_used', 'ram']):
            return 'memory'
        # CPU related
        if any(x in name_lower for x in ['cpu', 'processor']):
            return 'cpu'
        # Disk/Storage related
        if any(x in name_lower for x in ['disk', 'filesystem', 'storage', 'file_']):
            return 'disk'
        # Network related
        if any(x in name_lower for x in ['network', 'net_', 'socket', 'tcp', 'udp', 'packets']):
            return 'network'
        # Garbage Collection
        if any(x in name_lower for x in ['_gc_', 'garbage']):
            return 'gc'
        # Threads
        if any(x in name_lower for x in ['thread', 'daemon']):
            return 'threads'
        # Query/Request handling
        if any(x in name_lower for x in ['query', 'request', 'search']):
            return 'query'
        # Latency/Timing
        if any(x in name_lower for x in ['latency', 'time', 'duration', 'seconds']):
            return 'latency'
        # Connections
        if any(x in name_lower for x in ['connection', 'session', 'client']):
            return 'connections'
        # Cache
        if any(x in name_lower for x in ['cache', 'hit', 'miss']):
            return 'cache'
        # I/O
        if any(x in name_lower for x in ['_io_', 'read', 'write', 'sync']):
            return 'io'
        # HTTP
        if any(x in name_lower for x in ['http', 'response', 'status']):
            return 'http'
        # Health/Status
        if any(x in name_lower for x in ['up', 'health', 'alive', 'ready', 'info']):
            return 'health'
        # Counter totals
        if name_lower.endswith('_total') or name_lower.endswith('_count'):
            return 'counters'
            
        return 'general'
    
    def guess_processgroup(self, metric: MetricInfo) -> str | None:
        """Guess process group (application category) from metric name or labels.
        
        PROCESSGROUP is the application/service type, e.g., 'spark', 'solr', 'zookeeper'.
        PROCESS (determined separately) is the specific job/instance within that group.
        """
        name = metric.name.lower()
        
        # Check metric name prefix FIRST (more reliable than job label)
        if name.startswith('node_'):
            return 'node'
        if name.startswith('solr_'):
            return 'solr'
        if name.startswith('spark_') or name.startswith('metrics_'):
            return 'spark'
        if name.startswith('zk_') or name.startswith('zookeeper_'):
            return 'zookeeper'
        if name.startswith('go_') or name.startswith('prometheus_') or name.startswith('promhttp_'):
            return 'prometheus'
        if name.startswith('jvm_') or name.startswith('java_') or name.startswith('process_'):
            return 'jvm'
            
        # ZooKeeper-specific metrics without zk_ prefix
        zk_metrics = ['ack_', 'commit_', 'election_', 'follower_', 'leader_', 'learner_',
                      'proposal_', 'quorum_', 'session_', 'sync_', 'write_', 'read_',
                      'outstanding_', 'pending_', 'prep_', 'snap', 'uptime', 'watch_',
                      'znode_', 'ensemble_', 'connection_', 'fsync', 'dbinittime']
        for prefix in zk_metrics:
            if name.startswith(prefix):
                return 'zookeeper'
        
        # Fallback: Check job label for hints about the application
        if 'job' in metric.label_values:
            jobs = metric.label_values['job']
            for job in jobs:
                job_lower = job.lower()
                if 'spark' in job_lower:
                    return 'spark'
                if 'solr' in job_lower:
                    return 'solr'
                if 'zookeeper' in job_lower or job_lower == 'zk':
                    return 'zookeeper'
                if 'node' in job_lower:
                    return 'node'
                if 'prometheus' in job_lower:
                    return 'prometheus'
                if 'grafana' in job_lower:
                    return 'grafana'
            
        return 'unknown'
    
    def create_auto_mapping(self, metric: MetricInfo, pattern: str = None) -> dict:
        """Automatically create a mapping rule using intelligent defaults."""
        if pattern is None:
            pattern = metric.name
            
        rule_config = {}
        
        # HOSTGROUP - always Democluster
        rule_config['hostgroup'] = "Democluster"
        
        # HOST - from instance label
        if 'instance' in metric.labels:
            rule_config['host'] = {"label": "instance", "transform": "extract_host"}
        else:
            rule_config['host'] = None
        
        # METRICGROUP - technical category
        rule_config['metricgroup'] = self.guess_metricgroup(metric.name)
        
        # METRIC - remove common prefix
        prefix = metric.name.split('_')[0] + '_'
        rule_config['metric'] = {"source": "metric_name", "remove_prefix": prefix}
        
        # PROCESSGROUP - application/service
        rule_config['processgroup'] = self.guess_processgroup(metric) or "unknown"
        
        # PROCESS - from job label
        if 'job' in metric.labels:
            rule_config['process'] = {"label": "job"}
        else:
            rule_config['process'] = None
        
        # MEASUREMENT - nicht im Mapping, wird beim Import mit Timestamp gefüllt
        
        return self.create_rule_dict(pattern, rule_config)
    
    def guess_measurement(self, metric: MetricInfo) -> str | None:
        """Guess measurement/role from labels."""
        role_labels = ['role', 'type', 'mode', 'state']
        for label in role_labels:
            if label in metric.label_values:
                values = metric.label_values[label]
                for v in values:
                    if v.lower() in self.KNOWN_MEASUREMENTS:
                        return v.lower()
        
        if 'job' in metric.label_values:
            for job in metric.label_values['job']:
                job_lower = job.lower()
                if 'master' in job_lower:
                    return 'master'
                if 'worker' in job_lower:
                    return 'worker'
                    
        return None
    
    def create_rule_dict(self, pattern: str, rule_config: dict) -> dict:
        """Create a rule dictionary for YAML output."""
        rule = {'pattern': pattern}
        
        if rule_config.get('label_conditions'):
            rule['label_conditions'] = rule_config['label_conditions']
            
        for dim in ['hostgroup', 'host', 'metricgroup', 'metric', 
                    'processgroup', 'process', 'measurement']:
            if dim in rule_config and rule_config[dim] is not None:
                rule[dim] = rule_config[dim]
                
        return rule
    
    def ask_user(self, prompt: str, options: list[str] = None, 
                 default: str = None, allow_custom: bool = True) -> str:
        """Ask user for input with optional choices."""
        sys.stdout.flush()
        sys.stderr.flush()
        
        if options:
            log(f"\n{prompt}")
            for i, opt in enumerate(options, 1):
                marker = " (default)" if opt == default else ""
                log(f"  {i}. {opt}{marker}")
            if allow_custom:
                log(f"  {len(options)+1}. [Custom value]")
            log(f"  0. [Skip/None]")
            
            max_attempts = 10
            attempts = 0
            while attempts < max_attempts:
                attempts += 1
                try:
                    sys.stdout.write("> ")
                    sys.stdout.flush()
                    choice = input().strip()
                    
                    # Empty input with default
                    if not choice and default:
                        log(f"  -> Using default: {default}")
                        return default
                    
                    # Skip
                    if choice == '0':
                        log("  -> Skipped")
                        return None
                    
                    # Numeric choice
                    try:
                        idx = int(choice) - 1
                        if 0 <= idx < len(options):
                            log(f"  -> Selected: {options[idx]}")
                            return options[idx]
                        if allow_custom and idx == len(options):
                            sys.stdout.write("Enter custom value: ")
                            sys.stdout.flush()
                            custom = input().strip()
                            log(f"  -> Custom: {custom}")
                            return custom
                    except ValueError:
                        pass
                    
                    # Direct text match
                    if choice in options:
                        log(f"  -> Selected: {choice}")
                        return choice
                    
                    # Allow any custom value
                    if allow_custom and choice:
                        log(f"  -> Custom: {choice}")
                        return choice
                        
                    log("Invalid choice, try again (or 0 to skip)")
                    
                except EOFError:
                    log("\nEOF received, using default or skipping")
                    return default
                    
            log(f"Too many invalid attempts, using default: {default}")
            return default
        else:
            suffix = f" [{default}]" if default else ""
            sys.stdout.write(f"{prompt}{suffix}: ")
            sys.stdout.flush()
            try:
                result = input().strip()
                return result if result else default
            except EOFError:
                return default
    
    def ask_mapping_source(self, dimension: str, metric: MetricInfo, 
                           suggestion: str = None) -> dict | str | None:
        """Ask user how to map a dimension."""
        log(f"\n--- Mapping {dimension.upper()} ---")
        log(f"Metric: {metric.name}")
        log(f"Labels: {', '.join(sorted(metric.labels)) or '(none)'}")
        
        if metric.label_values:
            log("Label values:")
            for label, values in sorted(metric.label_values.items()):
                vals = list(values)[:5]
                more = f"... (+{len(values)-5})" if len(values) > 5 else ""
                log(f"  {label}: {vals}{more}")
        
        options = ["constant", "label", "substring", "regex", "concat"]
        if suggestion:
            log(f"\nSuggestion: {suggestion}")
            options.insert(0, f"use suggestion: {suggestion}")
        
        choice = self.ask_user(f"How to determine {dimension}?", options)
        
        if choice is None:
            return None
        if choice and choice.startswith("use suggestion"):
            return suggestion
        if choice == "constant":
            return self.ask_user("Enter constant value")
        if choice == "label":
            label = self.ask_user("Which label?", sorted(metric.labels))
            if label:
                return {"label": label}
            return None
        if choice == "substring":
            log(f"Metric name: {metric.name}")
            start = self.ask_user("Start index (0-based)", default="0")
            end = self.ask_user("End index (empty for end)")
            return {"substring": {"start": int(start or 0), "end": int(end) if end else None}}
        if choice == "regex":
            log(f"Metric name: {metric.name}")
            pattern = self.ask_user("Regex pattern (use group 1 for extraction)")
            return {"regex": pattern}
        if choice == "concat":
            parts = []
            log("Add parts (empty to finish):")
            while True:
                part_type = self.ask_user("Part type", ["constant", "label", "substring", "done"])
                if not part_type or part_type == "done":
                    break
                if part_type == "constant":
                    parts.append({"constant": self.ask_user("Value")})
                elif part_type == "label":
                    parts.append({"label": self.ask_user("Label name")})
                elif part_type == "substring":
                    start = int(self.ask_user("Start", default="0") or 0)
                    end = self.ask_user("End")
                    parts.append({"substring": {"start": start, "end": int(end) if end else None}})
            return {"concat": parts} if parts else None
        
        return choice
    
    def process_metric_group(self, prefix: str, metrics: list[MetricInfo]) -> list[dict]:
        """Process a group of metrics with similar prefix."""
        log(f"\n{'='*60}")
        log(f"METRIC GROUP: {prefix}* ({len(metrics)} metrics)")
        log('='*60)
        
        log("\nSample metrics in this group:")
        for m in metrics[:5]:
            labels_str = ', '.join(sorted(m.labels)[:5])
            if len(m.labels) > 5:
                labels_str += f" (+{len(m.labels)-5})"
            log(f"  - {m.name}")
            log(f"    Labels: {labels_str or '(none)'}")
        if len(metrics) > 5:
            log(f"  ... and {len(metrics)-5} more")
        
        # Check for learned patterns
        if prefix in self.learned_patterns:
            log(f"\nFound learned pattern for '{prefix}*'")
            use_learned = self.ask_user("Use learned pattern?", ["yes", "no"], default="yes")
            if use_learned == "yes":
                return [self.learned_patterns[prefix]]
        
        create_rule = self.ask_user(
            f"Create mapping rule for this group?",
            ["wildcard rule for all", "individual rules", "skip entire group"],
            default="wildcard rule for all"
        )
        
        if create_rule == "skip entire group":
            log("  -> Skipping group")
            return []
        
        if create_rule == "wildcard rule for all":
            template = metrics[0]
            
            # Merge all labels from group
            all_labels = set()
            merged_values = defaultdict(set)
            for m in metrics:
                all_labels.update(m.labels)
                for label, values in m.label_values.items():
                    merged_values[label].update(values)
            
            template.labels = all_labels
            template.label_values = dict(merged_values)
            
            log(f"\nCreating wildcard rule for {prefix}_*")
            rule_config = self.create_mapping_interactively(template, pattern=f"{prefix}_*")
            
            self.learned_patterns[prefix] = rule_config
            return [rule_config]
        
        # Individual rules
        rules = []
        for metric in metrics:
            skip = self.ask_user(f"\nMap metric '{metric.name}'?", ["yes", "skip"], default="yes")
            if skip == "skip":
                continue
            rule = self.create_mapping_interactively(metric)
            rules.append(rule)
        
        return rules
    
    def create_mapping_interactively(self, metric: MetricInfo, 
                                      pattern: str = None) -> dict:
        """Create a mapping rule interactively for a metric."""
        if pattern is None:
            pattern = metric.name
            
        rule_config = {}
        
        log("\n" + "-"*40)
        log("Step 1/7: HOSTGROUP")
        
        # HOSTGROUP
        hostgroup = self.ask_user(
            "HOSTGROUP (cluster name)?",
            self.KNOWN_HOSTGROUPS + ["[Custom]"],
            default="Democluster"
        )
        rule_config['hostgroup'] = hostgroup
        
        # HOST
        log("\n" + "-"*40)
        log("Step 2/7: HOST")
        
        if 'instance' in metric.labels:
            instances = list(metric.label_values.get('instance', []))[:3]
            log(f"Found 'instance' label: {instances}")
            use_instance = self.ask_user(
                "Use 'instance' label (hostname extracted)?",
                ["yes", "no"],
                default="yes"
            )
            if use_instance == "yes":
                rule_config['host'] = {"label": "instance", "transform": "extract_host"}
            else:
                rule_config['host'] = self.ask_mapping_source("host", metric)
        else:
            rule_config['host'] = self.ask_mapping_source("host", metric)
        
        # METRICGROUP (category)
        log("\n" + "-"*40)
        log("Step 3/7: METRICGROUP (technical category)")
        log("  Examples: memory, cpu, disk, network, gc, latency, query")
        
        suggested_group = self.guess_metricgroup(metric.name)
        rule_config['metricgroup'] = self.ask_user(
            f"METRICGROUP (technical category)?",
            self.KNOWN_METRICGROUPS + ["[Custom]"],
            default=suggested_group
        )
        
        # METRIC (specific metric name within the group)
        log("\n" + "-"*40)
        log("Step 4/7: METRIC (specific metric name)")
        log(f"  Full metric name: '{metric.name}'")
        log(f"  This becomes the element within METRICGROUP '{rule_config.get('metricgroup', '?')}'")
        
        metric_options = [
            "use full metric name",
            "remove prefix",
            "custom extraction"
        ]
        metric_choice = self.ask_user("How to determine METRIC?", metric_options, default="remove prefix")
        
        if metric_choice == "use full metric name":
            rule_config['metric'] = {"source": "metric_name"}
        elif metric_choice == "remove prefix":
            prefix_to_remove = self.ask_user("Prefix to remove", default=metric.name.split('_')[0] + '_')
            rule_config['metric'] = {"source": "metric_name", "remove_prefix": prefix_to_remove}
        else:
            rule_config['metric'] = self.ask_mapping_source("metric", metric)
        
        # PROCESSGROUP (application/service category)
        log("\n" + "-"*40)
        log("Step 5/7: PROCESSGROUP (application/service category)")
        log("  Examples: spark, solr, zookeeper, node, prometheus")
        log("  This groups related processes together")
        
        suggested_pg = self.guess_processgroup(metric)
        rule_config['processgroup'] = self.ask_user(
            "PROCESSGROUP (which application/service)?",
            self.KNOWN_PROCESSGROUPS + ["[Custom]"],
            default=suggested_pg
        )
        
        # PROCESS (specific process/job within the group)
        log("\n" + "-"*40)
        log("Step 6/7: PROCESS (specific process/job name)")
        log(f"  This becomes the element within PROCESSGROUP '{rule_config.get('processgroup', '?')}'")
        log("  Examples: spark-master, spark-worker, solr, zookeeper")
        
        if 'job' in metric.labels:
            jobs = list(metric.label_values.get('job', []))[:5]
            log(f"  Found 'job' label with values: {jobs}")
            use_job = self.ask_user(
                "Use 'job' label for PROCESS?",
                ["yes", "no"],
                default="yes"
            )
            if use_job == "yes":
                rule_config['process'] = {"label": "job"}
            else:
                rule_config['process'] = self.ask_mapping_source("process", metric)
        else:
            rule_config['process'] = self.ask_mapping_source("process", metric)
        
        # MEASUREMENT (role within the process)
        log("\n" + "-"*40)
        log("Step 7/7: MEASUREMENT (role/instance type)")
        log("  Examples: master, worker, leader, follower")
        log("  Describes the role of this process instance")
        
        suggested_role = self.guess_measurement(metric)
        if suggested_role:
            rule_config['measurement'] = self.ask_user(
                "MEASUREMENT (role)?",
                self.KNOWN_MEASUREMENTS + ["[Custom]"],
                default=suggested_role
            )
        else:
            # Check for role-like labels
            role_labels = [l for l in metric.labels if l in ['role', 'type', 'mode', 'state']]
            if role_labels:
                log(f"Found potential role labels: {role_labels}")
                use_label = self.ask_user(
                    f"Use label for MEASUREMENT?",
                    role_labels + ["constant", "skip"],
                    default=role_labels[0]
                )
                if use_label in role_labels:
                    rule_config['measurement'] = {"label": use_label}
                elif use_label == "constant":
                    rule_config['measurement'] = self.ask_user("Enter constant value")
                else:
                    rule_config['measurement'] = None
            else:
                rule_config['measurement'] = self.ask_user(
                    "MEASUREMENT (role)? (Enter value or skip)",
                    self.KNOWN_MEASUREMENTS + ["[Custom]", "skip"],
                    default="skip"
                )
                if rule_config['measurement'] == "skip":
                    rule_config['measurement'] = None
        
        log("\n" + "="*40)
        log("Rule created!")
        log("="*40)
        
        return self.create_rule_dict(pattern, rule_config)
    
    def run_auto(self) -> list[dict]:
        """Run automatic mapping with intelligent defaults."""
        log("\n" + "="*60)
        log("PROMETHEUS METRIC MAPPER - Auto Mode")
        log("="*60)
        log(f"\nTotal metrics to map: {len(self.metrics)}")
        
        # Group metrics by prefix
        groups = defaultdict(list)
        for metric in self.metrics.values():
            parts = metric.name.split('_')
            prefix = parts[0] if len(parts) > 1 else metric.name
            groups[prefix].append(metric)
        
        log(f"Grouped into {len(groups)} prefix groups\n")
        
        all_rules = []
        
        for prefix, metrics in sorted(groups.items()):
            # Use first metric as template, merge all labels
            template = metrics[0]
            all_labels = set()
            merged_values = defaultdict(set)
            for m in metrics:
                all_labels.update(m.labels)
                for label, values in m.label_values.items():
                    merged_values[label].update(values)
            
            template.labels = all_labels
            template.label_values = dict(merged_values)
            
            # Create wildcard rule
            pattern = f"{prefix}_*" if len(metrics) > 1 else prefix
            rule = self.create_auto_mapping(template, pattern)
            all_rules.append(rule)
            
            log(f"  {pattern:40} -> {rule.get('processgroup', '?'):12} / {rule.get('metricgroup', '?')}")
        
        log(f"\n>>> Created {len(all_rules)} rules <<<")
        return all_rules
    
    def run_interactive(self) -> list[dict]:
        """Run the interactive mapping process."""
        log("\n" + "="*60)
        log("PROMETHEUS METRIC MAPPER - Interactive Mode")
        log("="*60)
        log(f"\nTotal metrics to map: {len(self.metrics)}")
        log("Press Ctrl+C at any time to save progress and exit.\n")
        
        # Group metrics by prefix
        groups = defaultdict(list)
        for metric in self.metrics.values():
            parts = metric.name.split('_')
            prefix = parts[0] if len(parts) > 1 else metric.name
            groups[prefix].append(metric)
        
        log(f"Grouped into {len(groups)} prefix groups:")
        for prefix, metrics in sorted(groups.items(), key=lambda x: -len(x[1])):
            log(f"  {prefix}*: {len(metrics)} metrics")
        
        all_rules = []
        
        for prefix, metrics in sorted(groups.items()):
            try:
                rules = self.process_metric_group(prefix, metrics)
                all_rules.extend(rules)
                log(f"\n>>> Progress: {len(all_rules)} rules created so far <<<")
            except KeyboardInterrupt:
                log("\n\nInterrupted! Saving progress...")
                break
        
        return all_rules


def save_mapping_yaml(rules: list[dict], output_path: Path):
    """Save mapping rules to YAML file."""
    output = {
        'version': '1.0',
        'description': 'Prometheus metric mapping rules',
        'target_structure': {
            'dimensions': [
                'HOSTGROUP',
                'HOST', 
                'METRICGROUP',
                'METRIC',
                'PROCESSGROUP',
                'PROCESS',
                'MEASUREMENT (set at import time with timestamp, not from Prometheus)'
            ]
        },
        'rules': rules
    }
    
    with open(output_path, 'w') as f:
        yaml.dump(output, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    log(f"\nMapping saved to: {output_path}")


def load_existing_rules(rules_path: Path) -> list[dict]:
    """Load existing rules from YAML file."""
    if rules_path.exists():
        with open(rules_path) as f:
            data = yaml.safe_load(f)
            return data.get('rules', [])
    return []


def main():
    parser = argparse.ArgumentParser(
        description='Map Prometheus metrics to structured format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
    python prometheus_mapper.py --url http://node0.cloud.local:9090
    python prometheus_mapper.py --output my_mapping.yaml
    python prometheus_mapper.py --rules existing_rules.yaml  # Continue from existing
        """
    )
    parser.add_argument(
        '--url', 
        default='http://node0.cloud.local:9090',
        help='Prometheus server URL (default: http://node0.cloud.local:9090)'
    )
    parser.add_argument(
        '--output', '-o',
        default='prometheus_mapping.yaml',
        help='Output YAML file (default: prometheus_mapping.yaml)'
    )
    parser.add_argument(
        '--rules', '-r',
        help='Existing rules file to continue from'
    )
    parser.add_argument(
        '--auto', '-a',
        action='store_true',
        help='Auto mode: use intelligent defaults without prompting'
    )
    
    args = parser.parse_args()
    
    log(f"Connecting to Prometheus at {args.url}...")
    client = PrometheusClient(args.url)
    
    try:
        client.get_all_metric_names()
    except Exception as e:
        log(f"Error: Could not connect to Prometheus: {e}")
        sys.exit(1)
    
    analyzer = MetricAnalyzer(client)
    metrics = analyzer.analyze_all_metrics()
    
    if not metrics:
        log("No metrics found!")
        sys.exit(1)
    
    existing_rules = []
    if args.rules:
        rules_path = Path(args.rules)
        existing_rules = load_existing_rules(rules_path)
        log(f"Loaded {len(existing_rules)} existing rules")
    
    mapper = InteractiveMapper(metrics, auto_mode=args.auto)
    
    for rule in existing_rules:
        pattern = rule.get('pattern', '')
        if pattern.endswith('_*'):
            prefix = pattern[:-2]
            mapper.learned_patterns[prefix] = rule
    
    try:
        if args.auto:
            new_rules = mapper.run_auto()
        else:
            new_rules = mapper.run_interactive()
    except KeyboardInterrupt:
        log("\n\nInterrupted!")
        new_rules = []
    
    all_rules = existing_rules + new_rules
    
    if all_rules:
        output_path = Path(args.output)
        save_mapping_yaml(all_rules, output_path)
        log(f"\nDone! Created {len(new_rules)} new rules ({len(all_rules)} total)")
    else:
        log("\nNo rules created.")


if __name__ == '__main__':
    main()
