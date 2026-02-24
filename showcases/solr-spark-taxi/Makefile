# Showcase: NYC-Taxi Explorer (Solr + Spark + Vue.js)
#
# Verwendung:
#   make deploy              Showcase deployen
#   make teardown            Showcase entfernen
#   make smoke-tests         Smoke Tests ausfuehren
#   make collection          Solr Demo-Collection erstellen
#   make run-notebooks       Jupyter Notebooks als Tests ausfuehren
#

.PHONY: help deploy teardown smoke-tests collection run-notebooks

# ============================================
# Konfiguration
# ============================================
ROOT      := ../..
ENV       ?= baremetal
ANSIBLE   := ANSIBLE_CONFIG=$(ROOT)/ansible.cfg ansible-playbook
INV       := -i $(ROOT)/inventory/$(ENV)/hosts.yml -i inventory.yml

# ============================================
# Default: Hilfe anzeigen
# ============================================
help:
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════════════════╗"
	@echo "║           SHOWCASE: NYC-Taxi Explorer (Solr + Spark + Vue.js)            ║"
	@echo "╠══════════════════════════════════════════════════════════════════════════╣"
	@echo "║                                                                          ║"
	@echo "║  DEPLOYMENT:                                                             ║"
	@echo "║  ─────────────────────────────────────────────────────────────────────── ║"
	@echo "║  make deploy              Showcase deployen                              ║"
	@echo "║  make teardown            Showcase sauber entfernen                      ║"
	@echo "║                                                                          ║"
	@echo "║  TESTS:                                                                  ║"
	@echo "║  ─────────────────────────────────────────────────────────────────────── ║"
	@echo "║  make smoke-tests         Smoke Tests ausfuehren                         ║"
	@echo "║  make run-notebooks       Jupyter Notebooks als Tests ausfuehren         ║"
	@echo "║                                                                          ║"
	@echo "║  UTILITIES:                                                              ║"
	@echo "║  ─────────────────────────────────────────────────────────────────────── ║"
	@echo "║  make collection          Solr Demo-Collection erstellen                 ║"
	@echo "║                                                                          ║"
	@echo "║  VARIABLEN:                                                              ║"
	@echo "║  ─────────────────────────────────────────────────────────────────────── ║"
	@printf "║  %-72s║\n" "ENV=$(ENV)               Umgebung (baremetal, local)"
	@echo "║                                                                          ║"
	@echo "╚══════════════════════════════════════════════════════════════════════════╝"
	@echo ""

# ============================================
# Deployment
# ============================================
deploy:
	@echo "=== Showcase 'solr-spark-taxi' deployen (ENV=$(ENV)) ==="
	$(ANSIBLE) $(INV) deploy.yml

teardown:
	@echo "=== Showcase 'solr-spark-taxi' entfernen (ENV=$(ENV)) ==="
	$(ANSIBLE) $(INV) teardown.yml

# ============================================
# Tests
# ============================================
smoke-tests:
	@echo "=== Smoke Tests (solr-spark-taxi) ==="
	bash smoke-tests/smoke-tests.sh

run-notebooks:
	@echo "=== Notebook Integration Tests ==="
	ssh cloudadmin@node0 /data/jupyter/scripts/run-notebooks.sh

# ============================================
# Utilities
# ============================================
collection:
	@echo "=== Solr Demo-Collection erstellen ==="
	bash scripts/create-collection.sh
