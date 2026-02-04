# Ansible Playbooks für Cloudkoffer

Ansible Playbooks zur Installation des Big Data Stacks.

> **Referenz:** IPs, Ports und Versionen → [docs/REFERENCE.md](../../docs/REFERENCE.md)

---

## Voraussetzungen

1. Ansible installiert:
   ```bash
   sudo apt install pipx
   pipx install ansible
   pipx ensurepath
   ```

2. SSH-Zugang zu allen Nodes mit User `cloudadmin`

3. Basis-Installation via Cloud-Init abgeschlossen

---

## Verwendung

### Gesamten Stack installieren

```bash
cd baremetal/05-ansible
ansible-playbook -i inventory.yml site.yml
```

### Einzelne Komponenten

```bash
ansible-playbook -i inventory.yml dnsmasq.yml      # DNS-Cache
ansible-playbook -i inventory.yml zookeeper.yml    # ZooKeeper
ansible-playbook -i inventory.yml solr.yml         # Solr Cloud
ansible-playbook -i inventory.yml spark.yml        # Spark Cluster
ansible-playbook -i inventory.yml monitoring.yml   # Prometheus + Grafana
ansible-playbook -i inventory.yml jupyter.yml      # JupyterLab
```

### Mit Tags

```bash
ansible-playbook -i inventory.yml site.yml --tags zookeeper
ansible-playbook -i inventory.yml site.yml --tags notebooks -e "force=true"
```

### Connectivity-Test

```bash
ansible all -i inventory.yml -m ping
```

---

## Playbooks

| Playbook | Ziel-Nodes | Inhalt |
|----------|------------|--------|
| site.yml | Alle | Master-Playbook |
| dnsmasq.yml | Alle | DNS-Cache |
| zookeeper.yml | node1-3 | ZooKeeper Ensemble |
| solr.yml | node1-4 | Solr Cloud |
| spark.yml | node0-4 | Spark Master + Workers |
| monitoring.yml | node0 | Prometheus + Grafana |
| prometheus-exporters.yml | Alle | Node Exporter, JMX |
| jupyter.yml | node0 | JupyterLab |
| webapp-backend.yml | node0 | Flask Backend |
| webapp-frontend.yml | node0 | nginx + Vue.js |

---

## Troubleshooting

```bash
# SSH testen
ssh cloudadmin@node1.cloud.local

# Check-Mode (dry run)
ansible-playbook -i inventory.yml site.yml --check

# Verbose
ansible-playbook -i inventory.yml site.yml -vvv

# Nur ein Host
ansible-playbook -i inventory.yml zookeeper.yml --limit node1
```

---

## Lizenz

MIT License - siehe [LICENSE](../../LICENSE) | © 2026 Johannes Weigend, Weigend AM
