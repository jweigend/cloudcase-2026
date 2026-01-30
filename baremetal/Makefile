# Cloudkoffer Baremetal Makefile
#
# Verwendung: make [target]
#

.PHONY: help iso configs usb ansible zookeeper solr spark monitoring smoke-tests collection clean

# Ansible Pfad
ANSIBLE := ~/.local/share/pipx/venvs/ansible/bin/ansible-playbook
ANSIBLE_DIR := 05-ansible
INVENTORY := $(ANSIBLE_DIR)/inventory.yml

# Default: Hilfe anzeigen
help:
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════════════╗"
	@echo "║                    CLOUDKOFFER BAREMETAL SETUP                           ║"
	@echo "╠══════════════════════════════════════════════════════════════════════════╣"
	@echo "║                                                                          ║"
	@echo "║  INSTALLATION (in dieser Reihenfolge):                                   ║"
	@echo "║  ─────────────────────────────────────────────────────────────────────── ║"
	@echo "║  make iso              Ubuntu Autoinstall ISO erstellen                  ║"
	@echo "║  make usb DEVICE=/dev/sdX   ISO auf USB-Stick schreiben                  ║"
	@echo "║  make ansible          Kompletten Big Data Stack installieren            ║"
	@echo "║  make smoke-tests      Cluster-Tests ausführen                           ║"
	@echo "║  make collection       Solr Demo-Collection erstellen                    ║"
	@echo "║                                                                          ║"
	@echo "║  EINZELNE KOMPONENTEN:                                                   ║"
	@echo "║  ─────────────────────────────────────────────────────────────────────── ║"
	@echo "║  make zookeeper        Nur ZooKeeper installieren                        ║"
	@echo "║  make solr             Nur Solr Cloud installieren                       ║"
	@echo "║  make spark            Nur Spark Cluster installieren                    ║"
	@echo "║  make monitoring       Nur Monitoring (Prometheus/Grafana) installieren  ║"
	@echo "║                                                                          ║"
	@echo "║  STATUS & TESTS:                                                         ║"
	@echo "║  ─────────────────────────────────────────────────────────────────────── ║"
	@echo "║  make status           Cluster-Status anzeigen                           ║"
	@echo "║  make ping             Alle Nodes anpingen                               ║"
	@echo "║                                                                          ║"
	@echo "║  WEB UIs:                                                                ║"
	@echo "║  ─────────────────────────────────────────────────────────────────────── ║"
	@echo "║  Grafana:      http://node0:3000  (admin/admin)                          ║"
	@echo "║  Prometheus:   http://node0:9090                                         ║"
	@echo "║  Spark Master: http://node1:8081                                         ║"
	@echo "║  Solr Admin:   http://node1:8983/solr                                    ║"
	@echo "║                                                                          ║"
	@echo "╚══════════════════════════════════════════════════════════════════════════╝"
	@echo ""

# ============================================
# INSTALLATION
# ============================================

iso:
	@echo "=== Ubuntu Autoinstall ISO erstellen ==="
	cd 01-create-iso && ./create-iso.sh

configs:
	@echo "=== Autoinstall Konfigurationen generieren ==="
	cd 02-generate-configs && ./generate-all.sh

usb:
ifndef DEVICE
	@echo "FEHLER: USB-Gerät angeben mit DEVICE=/dev/sdX"
	@echo "Beispiel: make usb DEVICE=/dev/sdb"
	@exit 1
endif
	@echo "=== ISO auf USB-Stick schreiben ($(DEVICE)) ==="
	cd 03-write-usb && ./write-usb.sh $(DEVICE)

# ============================================
# ANSIBLE PLAYBOOKS
# ============================================

ansible:
	@echo "=== Kompletten Big Data Stack installieren ==="
	$(ANSIBLE) -i $(INVENTORY) $(ANSIBLE_DIR)/site.yml

zookeeper:
	@echo "=== ZooKeeper Cluster installieren ==="
	$(ANSIBLE) -i $(INVENTORY) $(ANSIBLE_DIR)/zookeeper.yml

solr:
	@echo "=== Solr Cloud installieren ==="
	$(ANSIBLE) -i $(INVENTORY) $(ANSIBLE_DIR)/solr.yml

spark:
	@echo "=== Spark Cluster installieren ==="
	$(ANSIBLE) -i $(INVENTORY) $(ANSIBLE_DIR)/spark.yml

monitoring:
	@echo "=== Monitoring (Prometheus/Grafana) installieren ==="
	$(ANSIBLE) -i $(INVENTORY) $(ANSIBLE_DIR)/monitoring.yml

# ============================================
# TESTS & STATUS
# ============================================

smoke-tests:
	@echo "=== Smoke Tests ausführen ==="
	cd 06-smoke-tests && bash smoke-tests.sh

collection:
	@echo "=== Solr Demo-Collection erstellen ==="
	cd 07-create-solr-collection && bash create-collection.sh

status:
	@echo ""
	@echo "=== CLUSTER STATUS ==="
	@echo ""
	@echo "--- ZooKeeper ---"
	@for node in node1 node2 node3; do \
		result=$$(echo ruok | nc -w1 $$node 2181 2>/dev/null || echo "OFFLINE"); \
		echo "$$node: $$result"; \
	done
	@echo ""
	@echo "--- Solr ---"
	@for node in node1 node2 node3 node4; do \
		result=$$(curl -s --max-time 2 "http://$$node:8983/solr/admin/info/system" 2>/dev/null | grep -oP '"solr-spec-version":"\K[^"]+' || echo "OFFLINE"); \
		echo "$$node: $$result"; \
	done
	@echo ""
	@echo "--- Spark Workers ---"
	@workers=$$(curl -s --max-time 2 http://node1:8081/ 2>/dev/null | grep -c "ALIVE" || echo "0"); \
	echo "Aktive Workers: $$workers"
	@echo ""
	@echo "--- Prometheus ---"
	@result=$$(curl -s --max-time 2 "http://node0:9090/-/ready" 2>/dev/null || echo "OFFLINE"); \
	echo "node0: $$result"
	@echo ""

ping:
	@echo "=== Alle Nodes anpingen ==="
	@for node in node0 node1 node2 node3 node4; do \
		if ping -c1 -W1 $$node >/dev/null 2>&1; then \
			echo "$$node: OK"; \
		else \
			echo "$$node: OFFLINE"; \
		fi \
	done

# ============================================
# CLEANUP
# ============================================

clean:
	@echo "=== Temporäre Dateien aufräumen ==="
	rm -rf 01-create-iso/work/
	rm -rf 01-create-iso/output/
	@echo "Fertig."
