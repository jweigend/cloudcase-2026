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
│  04-post-install/         Cloud-Init Configs für Services           │
│         ▼                                                            │
│  05-install-zookeeper/    cloud-init.yaml → NUC1-3                  │
│  06-install-solr/         cloud-init.yaml → alle Nodes              │
│  07-install-spark/        cloud-init-master.yaml → NUC2             │
│                           cloud-init-worker.yaml → NUC3-5           │
│  08-install-monitoring/   cloud-init-prometheus.yaml → NUC1         │
│                           cloud-init-exporter.yaml → NUC2-5         │
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
./create-iso.sh nuc1
./create-iso.sh nuc2
# ... für alle Nodes
```

---

## Schritt 3: USB schreiben & booten

```bash
cd baremetal/03-write-usb
./write-usb.sh nuc1 /dev/sdb
```

NUC von USB booten (F10), "Cloudkoffer Autoinstall" wählen.

---

## Schritt 4: Cloud-Init anwenden

Nach der Ubuntu-Installation:

```bash
cd baremetal/04-post-install
./apply-cloud-init.sh nuc1
./apply-cloud-init.sh nuc2
# ... für alle Nodes
```

Das Skript kopiert automatisch die passenden Cloud-Init Dateien basierend auf der Node-Rolle.

---

## Cloud-Init Dateien

| Verzeichnis | Datei | Nodes | Inhalt |
|-------------|-------|-------|--------|
| 04-post-install | base.yaml | Alle | Kernel-Tuning, Limits |
| 05-install-zookeeper | cloud-init.yaml | NUC1-3 | ZK 3.9.2, zoo.cfg, systemd |
| 06-install-solr | cloud-init.yaml | Alle | Solr 9.5, solr.in.sh, systemd |
| 07-install-spark | cloud-init-master.yaml | NUC2 | Spark Master, spark-env.sh |
| 07-install-spark | cloud-init-worker.yaml | NUC3-5 | Spark Worker, systemd |
| 08-install-monitoring | cloud-init-prometheus.yaml | NUC1 | Prometheus, Grafana, Node Exporter |
| 08-install-monitoring | cloud-init-exporter.yaml | NUC2-5 | Node Exporter |

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
