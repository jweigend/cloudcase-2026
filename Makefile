# Cloudkoffer - Multi-Showcase Cluster
#
# Verwendung:
#   make base                          Basis-Installation (alle Nodes)
#   make deploy                        Showcase deployen (Default: solr-spark-taxi)
#   make teardown                      Showcase entfernen
#   make switch FROM=old TO=new        Showcase wechseln
#   make smoke-tests                   Showcase-Tests ausfuehren
#

.PHONY: help base deploy teardown switch smoke-tests status ping shutdown reboot iso configs usb clean

# ============================================
# Konfiguration
# ============================================
ENV       ?= baremetal
SHOWCASE  ?= solr-spark-taxi
ANSIBLE   := ansible-playbook
ANSIBLE_CMD := ansible

BASE_INV  := -i inventory/$(ENV)/hosts.yml

# ============================================
# Default: Hilfe anzeigen
# ============================================
help:
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════════════╗"
	@echo "║                   CLOUDKOFFER - Multi-Showcase Cluster                   ║"
	@echo "╠══════════════════════════════════════════════════════════════════════════╣"
	@echo "║                                                                          ║"
	@echo "║  PHASE 1 - INFRASTRUKTUR (einmalig):                                     ║"
	@echo "║  ─────────────────────────────────────────────────────────────────────── ║"
	@echo "║  make iso                 Ubuntu Autoinstall ISO erstellen               ║"
	@echo "║  make usb DEVICE=/dev/sdX ISO auf USB-Stick schreiben                    ║"
	@echo "║                                                                          ║"
	@echo "║  PHASE 2 - BASIS (einmalig pro Umgebung):                                ║"
	@echo "║  ─────────────────────────────────────────────────────────────────────── ║"
	@echo "║  make base                Basis-Installation (OS, DNS, Java, Monitoring) ║"
	@echo "║                                                                          ║"
	@echo "║  PHASE 3 - SHOWCASE (austauschbar):                                      ║"
	@echo "║  ─────────────────────────────────────────────────────────────────────── ║"
	@echo "║  make deploy              Showcase deployen                              ║"
	@echo "║  make teardown            Showcase sauber entfernen                      ║"
	@echo "║  make switch FROM=x TO=y  Showcase wechseln                              ║"
	@echo "║  make smoke-tests         Showcase-Tests ausfuehren                      ║"
	@echo "║                                                                          ║"
	@echo "║  CLUSTER-STEUERUNG:                                                      ║"
	@echo "║  ─────────────────────────────────────────────────────────────────────── ║"
	@echo "║  make status              Cluster-Status anzeigen                        ║"
	@echo "║  make ping                Alle Nodes anpingen                            ║"
	@echo "║  make shutdown            Alle Nodes herunterfahren                      ║"
	@echo "║  make reboot              Alle Nodes neu starten                         ║"
	@echo "║                                                                          ║"
	@echo "║  VARIABLEN:                                                              ║"
	@echo "║  ─────────────────────────────────────────────────────────────────────── ║"
	@printf "║  %-72s║\n" "ENV=$(ENV)               Umgebung (baremetal, local)"
	@printf "║  %-72s║\n" "SHOWCASE=$(SHOWCASE)     Aktiver Showcase"
	@echo "║                                                                          ║"
	@echo "║  VERFUEGBARE SHOWCASES:                                                  ║"
	@echo "║  ─────────────────────────────────────────────────────────────────────── ║"
	@echo "║  solr-spark-taxi          NYC-Taxi Explorer (Solr + Spark + Vue.js)      ║"
	@echo "║  clickhouse-taxi          NYC-Taxi Analysis (ClickHouse OLAP)            ║"
	@echo "║                                                                          ║"
	@echo "║  Showcase-spezifische Befehle:                                           ║"
	@printf "║  %-72s║\n" "  cd showcases/$(SHOWCASE) && make help"
	@echo "║                                                                          ║"
	@echo "╚══════════════════════════════════════════════════════════════════════════╝"
	@echo ""

# ============================================
# PHASE 1: Infrastruktur
# ============================================
iso:
	@echo "=== Ubuntu Autoinstall ISO erstellen ==="
	cd infrastructure/baremetal/02-create-iso && ./create-iso.sh

configs:
	@echo "=== Autoinstall Konfigurationen generieren ==="
	cd infrastructure/baremetal/01-generate-configs && ./generate-all.sh

usb:
ifndef DEVICE
	@echo "FEHLER: USB-Geraet angeben mit DEVICE=/dev/sdX"
	@exit 1
endif
	@echo "=== ISO auf USB-Stick schreiben ($(DEVICE)) ==="
	cd infrastructure/baremetal/03-write-usb && ./write-usb.sh $(DEVICE)

# ============================================
# PHASE 2: Basis-Installation
# ============================================
base:
	@echo "=== Basis-Installation (ENV=$(ENV)) ==="
	$(ANSIBLE) $(BASE_INV) base.yml

# ============================================
# PHASE 3: Showcase (delegiert an Showcase-Makefile)
# ============================================
deploy:
	$(MAKE) -C showcases/$(SHOWCASE) deploy ENV=$(ENV)

teardown:
	$(MAKE) -C showcases/$(SHOWCASE) teardown ENV=$(ENV)

switch:
ifndef FROM
	@echo "FEHLER: FROM und TO angeben"
	@echo "Beispiel: make switch FROM=solr-spark-taxi TO=cloud-native-k8s"
	@exit 1
endif
ifndef TO
	@echo "FEHLER: FROM und TO angeben"
	@exit 1
endif
	@echo "=== Wechsel: $(FROM) -> $(TO) ==="
	$(MAKE) -C showcases/$(FROM) teardown ENV=$(ENV)
	$(MAKE) -C showcases/$(TO) deploy ENV=$(ENV)

smoke-tests:
	$(MAKE) -C showcases/$(SHOWCASE) smoke-tests

# ============================================
# Cluster-Steuerung
# ============================================
status:
	@echo ""
	@echo "=== CLUSTER STATUS (ENV=$(ENV)) ==="
	@echo ""
	@echo "--- Ping ---"
	@for node in node0 node1 node2 node3 node4; do \
		if ping -c1 -W1 $$node >/dev/null 2>&1; then \
			echo "  $$node: OK"; \
		else \
			echo "  $$node: OFFLINE"; \
		fi \
	done
	@echo ""

ping:
	@echo "=== Alle Nodes anpingen ==="
	$(ANSIBLE_CMD) $(BASE_INV) all -m ping

shutdown:
	@echo "=== Alle Nodes herunterfahren ==="
	@for node in node4 node3 node2 node1 node0; do \
		echo "Fahre $$node herunter..."; \
		ssh -o ConnectTimeout=2 cloudadmin@$$node "sudo shutdown -h now" 2>/dev/null || true; \
	done

reboot:
	@echo "=== Alle Nodes neu starten ==="
	@for node in node4 node3 node2 node1 node0; do \
		echo "Starte $$node neu..."; \
		ssh -o ConnectTimeout=2 cloudadmin@$$node "sudo reboot" 2>/dev/null || true; \
	done

# ============================================
# Cleanup
# ============================================
clean:
	@echo "=== Temporaere Dateien aufraeumen ==="
	rm -rf infrastructure/baremetal/02-create-iso/work/
	rm -rf infrastructure/baremetal/02-create-iso/output/
