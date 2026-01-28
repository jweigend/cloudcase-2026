# Baremetal Setup - Ubuntu Autoinstall & Cloud-Init

Diese Dokumentation beschreibt das Provisioning der 5 Intel NUCs mit Ubuntu Server unter Verwendung von Autoinstall und Cloud-Init.

---

## Provisioning Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                    PROVISIONING WORKFLOW                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. USB Boot mit Ubuntu Server ISO + Autoinstall                │
│     └─► user-data & meta-data auf USB/HTTP-Server               │
│                                                                  │
│  2. Ubuntu Autoinstall                                          │
│     └─► Partitionierung, Basis-Pakete, Netzwerk                 │
│                                                                  │
│  3. Cloud-Init (First Boot)                                     │
│     └─► Hostname, SSH Keys, Basis-Konfiguration                 │
│                                                                  │
│  4. Ansible/Shell Scripts (Post-Install)                        │
│     └─► Java, ZooKeeper, Solr, Spark, Monitoring                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Verzeichnisstruktur

```
cloudkoffer-2026/
├── autoinstall/
│   ├── user-data.yaml          # Autoinstall Konfiguration
│   └── meta-data               # Leere Datei oder Metadaten
├── cloud-init/
│   ├── common/
│   │   └── cloud-config.yaml   # Gemeinsame Config für alle Nodes
│   └── nodes/
│       ├── nuc1.yaml
│       ├── nuc2.yaml
│       ├── nuc3.yaml
│       ├── nuc4.yaml
│       └── nuc5.yaml
├── ansible/                    # Optional: Ansible Playbooks
│   ├── inventory.ini
│   ├── playbook-base.yaml
│   ├── playbook-zookeeper.yaml
│   ├── playbook-solr.yaml
│   ├── playbook-spark.yaml
│   └── playbook-monitoring.yaml
├── configs/
│   ├── zookeeper/
│   ├── solr/
│   ├── spark/
│   ├── prometheus/
│   └── grafana/
└── README.md
```

---

## Ubuntu Autoinstall

### USB-Stick Vorbereitung

1. Ubuntu Server ISO herunterladen (24.04 LTS empfohlen)
2. ISO auf USB-Stick schreiben (z.B. mit `dd` oder Balena Etcher)
3. `autoinstall/` Verzeichnis auf USB-Stick erstellen
4. `user-data` und `meta-data` Dateien hinzufügen

### user-data (Beispiel)

```yaml
#cloud-config
autoinstall:
  version: 1
  locale: de_DE.UTF-8
  keyboard:
    layout: de
  identity:
    hostname: nucX  # Wird per Node angepasst (nuc1, nuc2, ...)
    username: cloudadmin
    password: <hashed-password>
  ssh:
    install-server: true
    allow-pw: false
    authorized-keys:
      - ssh-rsa AAAA... # Dein SSH Public Key
  network:
    version: 2
    ethernets:
      enp0s31f6:  # NIC-Name prüfen! (ip link show)
        dhcp4: true
  storage:
    layout:
      name: direct
  packages:
    - openssh-server
    - htop
    - net-tools
    - openjdk-17-jdk
    - curl
    - netcat-openbsd
  late-commands:
    - curtin in-target -- systemctl enable ssh
    - curtin in-target -- mkdir -p /data/solr /data/spark /data/zookeeper /data/prometheus
```

### Passwort-Hash generieren

```bash
# Passwort-Hash für user-data erstellen
mkpasswd --method=SHA-512
```

### meta-data

```yaml
# Kann leer sein oder Instance-ID enthalten
instance-id: cloudkoffer-nucX
```

---

## Cloud-Init Konfiguration

### Gemeinsame /etc/hosts (alle Nodes)

```yaml
#cloud-config
manage_etc_hosts: true

write_files:
  - path: /etc/hosts
    append: true
    content: |
      192.168.0.100 nuc1 nuc1.cloudkoffer.local
      192.168.0.101 nuc2 nuc2.cloudkoffer.local
      192.168.0.102 nuc3 nuc3.cloudkoffer.local
      192.168.0.103 nuc4 nuc4.cloudkoffer.local
      192.168.0.104 nuc5 nuc5.cloudkoffer.local
```

### Node-spezifische Konfiguration

#### NUC1 (ZooKeeper, Solr, Prometheus, Grafana)

```yaml
#cloud-config
hostname: nuc1
fqdn: nuc1.cloudkoffer.local

write_files:
  - path: /data/zookeeper/myid
    content: "1"

runcmd:
  - echo "NUC1 initialized" >> /var/log/cloud-init-custom.log
```

#### NUC2 (ZooKeeper, Solr, Spark Master)

```yaml
#cloud-config
hostname: nuc2
fqdn: nuc2.cloudkoffer.local

write_files:
  - path: /data/zookeeper/myid
    content: "2"

runcmd:
  - echo "NUC2 initialized" >> /var/log/cloud-init-custom.log
```

#### NUC3 (ZooKeeper, Solr, Spark Worker)

```yaml
#cloud-config
hostname: nuc3
fqdn: nuc3.cloudkoffer.local

write_files:
  - path: /data/zookeeper/myid
    content: "3"

runcmd:
  - echo "NUC3 initialized" >> /var/log/cloud-init-custom.log
```

#### NUC4 (Solr, Spark Worker)

```yaml
#cloud-config
hostname: nuc4
fqdn: nuc4.cloudkoffer.local

runcmd:
  - echo "NUC4 initialized" >> /var/log/cloud-init-custom.log
```

#### NUC5 (Solr, Spark Worker)

```yaml
#cloud-config
hostname: nuc5
fqdn: nuc5.cloudkoffer.local

runcmd:
  - echo "NUC5 initialized" >> /var/log/cloud-init-custom.log
```

---

## Storage-Verzeichnisse erstellen

Auf allen Nodes:

```bash
sudo mkdir -p /data/solr /data/spark /data/zookeeper /data/prometheus
sudo chown -R cloudadmin:cloudadmin /data
```

| Verzeichnis | Zweck | Nodes |
|-------------|-------|-------|
| `/data/solr` | Solr Index | Alle |
| `/data/spark` | Spark Shuffle/Spill | NUC2-NUC5 |
| `/data/zookeeper` | ZK Data + Snapshots | NUC1-NUC3 |
| `/data/prometheus` | Prometheus TSDB | NUC1 |

---

## Post-Install Schritte

Nach dem Autoinstall und Cloud-Init können die Services manuell oder via Ansible installiert werden:

### 1. Java prüfen

```bash
java -version
# Sollte OpenJDK 17 anzeigen
```

### 2. ZooKeeper installieren (NUC1-NUC3)

```bash
# Download und Installation
wget https://downloads.apache.org/zookeeper/zookeeper-3.9.2/apache-zookeeper-3.9.2-bin.tar.gz
tar -xzf apache-zookeeper-3.9.2-bin.tar.gz
sudo mv apache-zookeeper-3.9.2-bin /opt/zookeeper
```

### 3. Solr installieren (alle Nodes)

```bash
wget https://downloads.apache.org/solr/solr/9.5.0/solr-9.5.0.tgz
tar -xzf solr-9.5.0.tgz
sudo mv solr-9.5.0 /opt/solr
```

### 4. Spark installieren (NUC2-NUC5)

```bash
wget https://downloads.apache.org/spark/spark-3.5.0/spark-3.5.0-bin-hadoop3.tgz
tar -xzf spark-3.5.0-bin-hadoop3.tgz
sudo mv spark-3.5.0-bin-hadoop3 /opt/spark
```

---

## Systemd Services

### ZooKeeper Service

```ini
# /etc/systemd/system/zookeeper.service
[Unit]
Description=Apache ZooKeeper
After=network.target

[Service]
Type=forking
User=cloudadmin
Environment="JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64"
Environment="ZOO_LOG_DIR=/data/zookeeper"
ExecStart=/opt/zookeeper/bin/zkServer.sh start
ExecStop=/opt/zookeeper/bin/zkServer.sh stop
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Solr Service

```ini
# /etc/systemd/system/solr.service
[Unit]
Description=Apache Solr
After=network.target zookeeper.service

[Service]
Type=forking
User=cloudadmin
Environment="SOLR_HOME=/data/solr"
Environment="SOLR_HEAP=8g"
ExecStart=/opt/solr/bin/solr start -c -z nuc1:2181,nuc2:2181,nuc3:2181
ExecStop=/opt/solr/bin/solr stop
Restart=on-failure
MemoryMax=8G
CPUQuota=200%

[Install]
WantedBy=multi-user.target
```

### Spark Master Service (nur NUC2)

```ini
# /etc/systemd/system/spark-master.service
[Unit]
Description=Apache Spark Master
After=network.target

[Service]
Type=forking
User=cloudadmin
Environment="SPARK_HOME=/opt/spark"
Environment="SPARK_DAEMON_MEMORY=2g"
ExecStart=/opt/spark/sbin/start-master.sh
ExecStop=/opt/spark/sbin/stop-master.sh
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Spark Worker Service (NUC3-NUC5)

```ini
# /etc/systemd/system/spark-worker.service
[Unit]
Description=Apache Spark Worker
After=network.target

[Service]
Type=forking
User=cloudadmin
Environment="SPARK_HOME=/opt/spark"
Environment="SPARK_WORKER_MEMORY=16g"
Environment="SPARK_WORKER_CORES=4"
ExecStart=/opt/spark/sbin/start-worker.sh spark://nuc2:7077
ExecStop=/opt/spark/sbin/stop-worker.sh
Restart=on-failure
MemoryMax=16G
CPUQuota=200%

[Install]
WantedBy=multi-user.target
```

---

## Services aktivieren

```bash
# ZooKeeper (NUC1-NUC3)
sudo systemctl daemon-reload
sudo systemctl enable zookeeper
sudo systemctl start zookeeper

# Solr (alle Nodes)
sudo systemctl enable solr
sudo systemctl start solr

# Spark Master (nur NUC2)
sudo systemctl enable spark-master
sudo systemctl start spark-master

# Spark Worker (NUC3-NUC5)
sudo systemctl enable spark-worker
sudo systemctl start spark-worker
```

---

## Troubleshooting

### Cloud-Init Logs prüfen

```bash
sudo cat /var/log/cloud-init.log
sudo cat /var/log/cloud-init-output.log
```

### Cloud-Init Status

```bash
cloud-init status
cloud-init status --long
```

### Netzwerk-Interface Namen ermitteln

```bash
ip link show
# Typisch bei Intel NUCs: enp0s31f6 oder eno1
```

---

*Zurück zur [Hauptdokumentation](README.md)*
