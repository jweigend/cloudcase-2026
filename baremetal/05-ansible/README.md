# Ansible Playbooks für Cloudkoffer

Ansible Playbooks zur Installation des Big Data Stacks auf dem Cloudkoffer-Cluster.

## Voraussetzungen

1. Ansible installiert auf dem Control Node (Laptop):
   ```bash
   sudo apt install pipx
   pipx install ansible
   pipx ensurepath
   ```

2. SSH-Zugang zu allen Nodes mit dem User `cloudadmin`

3. Basis-Installation der Nodes via Cloud-init abgeschlossen

## Cluster Übersicht

| Node  | IP            | Rolle                                    |
|-------|---------------|------------------------------------------|
| node0 | 192.168.1.100 | Prometheus, Grafana, DNS (dnsmasq)       |
| node1 | 192.168.1.101 | ZooKeeper, Solr, Spark-Master            |
| node2 | 192.168.1.102 | ZooKeeper, Solr, Spark-Worker            |
| node3 | 192.168.1.103 | ZooKeeper, Solr, Spark-Worker            |
| node4 | 192.168.1.104 | Solr, Spark-Worker                       |

## Verwendung

### Gesamten Stack installieren

```bash
cd baremetal/05-ansible
ansible-playbook -i inventory.yml site.yml
```

### Einzelne Komponenten installieren

```bash
# Nur ZooKeeper
ansible-playbook -i inventory.yml zookeeper.yml

# Nur Solr
ansible-playbook -i inventory.yml solr.yml

# Nur Spark
ansible-playbook -i inventory.yml spark.yml

# Nur Monitoring
ansible-playbook -i inventory.yml monitoring.yml
```

### Mit Tags

```bash
# Nur ZooKeeper über site.yml
ansible-playbook -i inventory.yml site.yml --tags zookeeper
```

### Connectivity-Test

```bash
ansible all -i inventory.yml -m ping
```

## Komponenten

### ZooKeeper (3.9.2)
- **Nodes:** node1, node2, node3
- **Client Port:** 2181
- **Admin Port:** 8080
- **Config:** `/opt/zookeeper/conf/zoo.cfg`

### Solr Cloud (9.7.0)
- **Nodes:** node1, node2, node3, node4
- **Port:** 8983
- **Admin UI:** `http://nodeX:8983/solr`
- **ZK-Verbindung:** `node1:2181,node2:2181,node3:2181/solr`

### Spark (3.5.4)
- **Master:** node1:7077
- **Workers:** node2, node3, node4
- **Web UI Master:** `http://node1:8080`
- **Web UI Workers:** `http://nodeX:8081`

### Monitoring
- **Prometheus:** node0:9090
- **Grafana:** node0:3000 (admin/admin)
- **Node Exporter:** Alle Nodes auf Port 9100

## Dateien

```
ansible/
├── ansible.cfg          # Ansible Konfiguration
├── inventory.yml        # Host-Definitionen
├── site.yml             # Master-Playbook
├── zookeeper.yml        # ZooKeeper Installation
├── solr.yml             # Solr Cloud Installation
├── spark.yml            # Spark Cluster Installation
└── monitoring.yml       # Prometheus + Grafana + Node Exporter
```

## Troubleshooting

### SSH-Verbindung testen
```bash
ssh cloudadmin@node1.cloud.local
```

### Playbook im Check-Mode
```bash
ansible-playbook -i inventory.yml site.yml --check
```

### Verbose Output
```bash
ansible-playbook -i inventory.yml site.yml -vvv
```

### Einzelnen Host ansprechen
```bash
ansible-playbook -i inventory.yml zookeeper.yml --limit node1
```
