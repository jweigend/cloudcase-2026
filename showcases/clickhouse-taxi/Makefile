# Showcase: NYC-Taxi Analysis (ClickHouse OLAP)
#
# Verwendung:
#   make deploy              Showcase deployen
#   make teardown            Showcase entfernen
#   make smoke-tests         Smoke Tests ausfuehren
#   make run-notebooks       Jupyter Notebooks als Tests ausfuehren
#

.PHONY: help deploy teardown smoke-tests run-notebooks

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
	@echo "║              SHOWCASE: NYC-Taxi Analysis (ClickHouse OLAP)               ║"
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
	@echo "=== Showcase 'clickhouse-taxi' deployen (ENV=$(ENV)) ==="
	$(ANSIBLE) $(INV) deploy.yml

teardown:
	@echo "=== Showcase 'clickhouse-taxi' entfernen (ENV=$(ENV)) ==="
	$(ANSIBLE) $(INV) teardown.yml

# ============================================
# Tests
# ============================================
smoke-tests:
	@echo "=== Smoke Tests (clickhouse-taxi) ==="
	bash smoke-tests/smoke-tests.sh

run-notebooks:
	@echo "=== Notebook Integration Tests ==="
	ssh cloudadmin@node0 /data/jupyter/scripts/run-notebooks.sh
