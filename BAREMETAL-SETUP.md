# Baremetal Setup - Ubuntu Autoinstall & Cloud-Init

Provisioning der 5 Intel NUCs mit Ubuntu Server und Cloud-Init.

> **Skripte:** [`baremetal/`](baremetal/)

---

## Workflow

```
┌──────────────────────────────────────────────────────────────────────┐
│  02-generate-configs/     Autoinstall user-data generieren          │
│         ▼                                                            │
│  01-create-iso/           Bootfähiges ISO mit Autoinstall           │
│         ▼                                                            │
│  03-write-usb/            ISO auf USB schreiben                     │
│         ▼                                                            │
│      [ NUC von USB booten → automatische Ubuntu Installation ]      │
│         ▼                                                            │
│  05-ansible/              Ansible Playbooks für alle Services       │
│         ▼                                                            │
│    zookeeper.yml          → node1-3                                 │
│    solr.yml               → node1-4                                 │
│    spark.yml              → Master: node0, Workers: node1-4         │
│    monitoring.yml         → Prometheus/Grafana: node0               │
│    dnsmasq.yml            → alle Nodes                              │
│    jupyter.yml            → node0                                   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Schritt 1: Konfigurationen generieren

```bash
cd baremetal/02-generate-configs
./generate-all.sh ~/.ssh/id_rsa.pub
```

Erstellt für jeden Node:
- `autoinstall/user-data-nucX.yaml` - Ubuntu Autoinstall
- `autoinstall/meta-data-nucX` - Instance Metadaten

---

## Schritt 2: ISO erstellen

```bash
cd baremetal/01-create-iso
./create-iso.sh
# Erstellt ein universelles ISO für alle Nodes
```

---

## Schritt 3: USB schreiben & booten

```bash
cd baremetal/03-write-usb
./write-usb.sh /dev/sdb
```

NUC von USB booten (F10), "Cloudkoffer Autoinstall" wählen.

---

## Schritt 4: Ansible Playbooks ausführen

Nach der Ubuntu-Installation:

```bash
cd baremetal/05-ansible
ansible-playbook -i inventory.yml site.yml
```

Das installiert alle Services automatisch auf den richtigen Nodes.

---

## Ansible Playbooks

| Playbook | Nodes | Inhalt |
|----------|-------|--------|
| dnsmasq.yml | Alle | DNS-Cache auf allen Nodes |
| zookeeper.yml | node1-3 | ZK 3.9.4, zoo.cfg, systemd |
| solr.yml | node1-4 | Solr 9.8, solr.in.sh, systemd |
| spark.yml | node0-4 | Master auf node0, Workers auf node1-4 |
| monitoring.yml | node0 | Prometheus, Grafana, Node Exporter |
| prometheus-exporters.yml | Alle | Node Exporter, JMX Exporter |
| jupyter.yml | node0 | JupyterLab mit PySpark |

---

## Autoinstall user-data

```yaml
#cloud-config
autoinstall:
  version: 1
  locale: de_DE.UTF-8
  keyboard:
    layout: de
  
  identity:
    hostname: nucX
    username: cloudadmin
    password: '<SHA-512-Hash>'
  
  ssh:
    install-server: true
    allow-pw: false
    authorized-keys:
      - <SSH Public Key>
  
  packages:
    - openssh-server
    - openjdk-17-jdk
    - curl
    - wget
    - netcat-openbsd
  
  late-commands:
    - mkdir -p /data/solr /data/spark /data/zookeeper /data/prometheus
    # /etc/hosts mit allen Nodes
```

---

## Voraussetzungen (Admin-Rechner)

```bash
sudo apt-get install -y xorriso wget curl netcat-openbsd whois
```

---

*Weiter mit [SOLR-SPARK-SETUP.md](SOLR-SPARK-SETUP.md)*
