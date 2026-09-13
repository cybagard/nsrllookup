# Turnkey Provisioner entry points (ticket 03).
#
# `make provision` drives the full out-of-band flow into ./data and `make
# verify` re-checks that volume -- the one command that brings a fresh box to a
# verified `ready` state. The multi-gigabyte Release fetch is the operator's
# step and is never a build or CI step (ADR-0003); a default `make` target does
# not fetch, so nothing in CI or a build pulls the dataset. The driver lives in
# api/driver.py (Seam 3); the API boundary (Seam 1) and lookup module (Seam 2)
# are untouched.

RELEASE ?= 2026.09.1
DELTAS  ?= 2026.06.1 2026.03.1
DATADIR ?= ./data
WORKDIR ?= /tmp/nsrl_provision
SETNAME ?= modern
FAMILY  ?= modern_minimal

PYTHON ?= python

.DEFAULT_GOAL := help

.PHONY: help provision verify

help:
	@echo "make provision  fetch + verify 3 layers + apply deltas + write ./data"
	@echo "make verify     re-check a provisioned volume in ./data"
	@echo "RELEASE, DELTAS, DATADIR, SETNAME, FAMILY are overridable variables"

provision:
	$(PYTHON) api/driver.py provision \
		--release $(RELEASE) --deltas $(DELTAS) \
		--data-dir $(DATADIR) --work-dir $(WORKDIR) \
		--set-name $(SETNAME) --family $(FAMILY)

verify:
	$(PYTHON) api/driver.py verify --data-dir $(DATADIR)
