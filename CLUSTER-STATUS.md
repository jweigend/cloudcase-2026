# Cloudkoffer Big Data Cluster

**Stand:** 29. Januar 2026

## Cluster Übersicht

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Cloudkoffer Netzwerk                               │
│                           192.168.1.0/24                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │  node0   │  │  node1   │  │  node2   │  │  node3   │  │  node4   │      │
│  │  .100    │  │  .101    │  │  .102    │  │  .103    │  │  .104    │      │
│  ├──────────┤  ├──────────┤  ├──────────┤  ├──────────┤  ├──────────┤      │
│  │Prometheus│  │ZooKeeper │  │ZooKeeper │  │ZooKeeper │  │          │      │
│  │ Grafana  │  │  Solr    │  │  Solr    │  │  Solr    │  │  Solr    │      │
│  │  DNS     │  │Spark-Mstr│  │Spark-Wrkr│  │Spark-Wrkr│  │Spark-Wrkr│      │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Komponenten Status

| Komponente | Nodes | Status |
|------------|-------|--------|
| **ZooKeeper 3.9.4** | node1, node2, node3 | ✅ 3/3 Nodes aktiv |
| **Solr Cloud 9.10.1** | node1, node2, node3, node4 | ✅ 4/4 Nodes aktiv |
| **Spark Master 3.5.8** | node1 | ✅ Läuft auf Port 7077 |
| **Spark Workers 3.5.8** | node2, node3, node4 | ✅ 3 Workers aktiv |
| **Prometheus 2.54.1** | node0 | ✅ Läuft auf Port 9090 |
| **Grafana 11.4.0** | node0 | ✅ Läuft auf Port 3000 |
| **Node Exporter 1.8.2** | alle Nodes | ✅ 5/5 Nodes aktiv |

## Web UIs

| Service | URL | Zugangsdaten |
|---------|-----|--------------|
| **Grafana** | http://192.168.1.100:3000 | admin / admin |
| **Prometheus** | http://192.168.1.100:9090 | - |
| **Spark Master** | http://192.168.1.101:8081 | - |
| **Solr Admin** | http://192.168.1.101:8983/solr | - |

## Node Details

| Node | IP | Hostname | Rolle |
|------|-----|----------|-------|
| node0 | 192.168.1.100 | node0.cloud.local | Monitoring, DNS |
| node1 | 192.168.1.101 | node1.cloud.local | ZooKeeper, Solr, Spark Master |
| node2 | 192.168.1.102 | node2.cloud.local | ZooKeeper, Solr, Spark Worker |
| node3 | 192.168.1.103 | node3.cloud.local | ZooKeeper, Solr, Spark Worker |
| node4 | 192.168.1.104 | node4.cloud.local | Solr, Spark Worker |

## Ports

| Service | Port | Beschreibung |
|---------|------|--------------|
| SSH | 22 | Alle Nodes |
| ZooKeeper Client | 2181 | node1, node2, node3 |
| ZooKeeper Peer | 2888 | node1, node2, node3 |
| ZooKeeper Election | 3888 | node1, node2, node3 |
| Grafana | 3000 | node0 |
| Spark Master | 7077 | node1 |
| Spark Master UI | 8081 | node1 |
| Spark Worker UI | 8081 | node2, node3, node4 |
| Solr | 8983 | node1, node2, node3, node4 |
| Prometheus | 9090 | node0 |
| Node Exporter | 9100 | Alle Nodes |

## Verbindungsstrings

### ZooKeeper
```
node1.cloud.local:2181,node2.cloud.local:2181,node3.cloud.local:2181
```

### Solr Cloud (mit ZooKeeper)
```
node1.cloud.local:2181,node2.cloud.local:2181,node3.cloud.local:2181/solr
```

### Spark Master
```
spark://node1.cloud.local:7077
```

## Hardware

- **5x Intel NUC** mit Ubuntu 24.04.3 LTS
- **Edgerouter X** als Switch/Router (192.168.1.1)
- **Netzwerk**: 192.168.1.0/24, Domain: cloud.local

## SSH Zugang

```bash
ssh cloudadmin@node0.cloud.local
ssh cloudadmin@node1.cloud.local
ssh cloudadmin@node2.cloud.local
ssh cloudadmin@node3.cloud.local
ssh cloudadmin@node4.cloud.local
```

## Ansible Playbooks

Alle Playbooks befinden sich in `/ansible/`:

```bash
cd ansible

# Gesamten Stack installieren
ansible-playbook -i inventory.yml site.yml

# Einzelne Komponenten
ansible-playbook -i inventory.yml zookeeper.yml
ansible-playbook -i inventory.yml solr.yml
ansible-playbook -i inventory.yml spark.yml
ansible-playbook -i inventory.yml monitoring.yml

# Nur bestimmte Nodes
ansible-playbook -i inventory.yml site.yml --limit node2
```

## Quick Status Check

```bash
# ZooKeeper Status
for n in 1 2 3; do echo -n "node$n: "; ssh cloudadmin@192.168.1.10$n "echo ruok | nc localhost 2181"; done

# Spark Workers
curl -s http://192.168.1.101:8081/json/ | python3 -m json.tool

# Solr Status
curl -s http://192.168.1.101:8983/solr/admin/info/system | python3 -m json.tool

# Node Exporter (alle Nodes)
for n in 0 1 2 3 4; do echo -n "node$n: "; curl -s http://192.168.1.10$n:9100/metrics | head -1; done
```
