SHELL        := /bin/bash
SOFTWARE_DIR := Software
FIRMWARE_DIR := Firmware
VENV_DIR     := $(SOFTWARE_DIR)/venv
PYTHON       := $(VENV_DIR)/bin/python3
PIP          := $(VENV_DIR)/bin/pip
PYPROJECT    := $(SOFTWARE_DIR)/pyproject.toml

.PHONY: all run build deps clean help

all: help

run: $(VENV_DIR)/.installed  ## Run the software locally (creates / updates venv as needed)
	$(PYTHON) $(SOFTWARE_DIR)/main.py

build:  ## Build the Raspberry Pi OS firmware image
	cd $(FIRMWARE_DIR) && sudo ./build.sh

deps:  ## Sync installed venv packages → Software/pyproject.toml [project.dependencies]
	@if [ ! -x "$(PYTHON)" ] || ! "$(PYTHON)" --version >/dev/null 2>&1; then \
		echo "Error: no valid venv found – run 'make run' first."; \
		exit 1; \
	fi
	@$(PYTHON) -c "\
import subprocess, re; \
raw = open('$(PYPROJECT)').read(); \
out = subprocess.check_output(['$(PIP)', 'freeze'], text=True); \
skip = {'pip', 'pip-tools', 'setuptools', 'wheel', 'homerpi', 'software'}; \
lines = [l for l in out.splitlines() \
         if l.strip() \
         and not l.startswith('#') \
         and not l.startswith('-e') \
         and l.split('==')[0].split('@')[0].strip().lower() not in skip]; \
q = chr(34); \
items = [q + l + q for l in lines]; \
sep = ',\n    '; \
block = 'dependencies = [\n    ' + sep.join(items) + '\n]' if items else 'dependencies = []'; \
new = re.sub(r'dependencies\s*=\s*\[[^\]]*\]', block, raw, flags=re.DOTALL); \
open('$(PYPROJECT)', 'w').write(new); \
print('Updated $(PYPROJECT) with {} package(s).'.format(len(items)))"

clean:  ## Remove the virtual environment
	rm -rf $(VENV_DIR)

help:  ## Show this help message
	@echo "Usage: make <target>"
	@echo ""
	@echo "  run    Run the software locally (manages venv automatically)"
	@echo "  build  Build the Raspberry Pi OS firmware image"
	@echo "  deps   Sync installed venv packages -> $(PYPROJECT)"
	@echo "  clean  Remove build output and the virtual environment ($(VENV_DIR))"

$(VENV_DIR)/.installed: $(PYPROJECT)
	@if [ ! -x "$(PYTHON)" ] || ! "$(PYTHON)" --version >/dev/null 2>&1; then \
		echo "-> Creating virtual environment in $(VENV_DIR) ..."; \
		rm -rf "$(VENV_DIR)"; \
		python3 -m venv "$(VENV_DIR)"; \
	fi
	@echo "-> Updating pip / setuptools / wheel ..."
	@$(PIP) install --quiet --upgrade pip setuptools wheel
	@echo "-> Installing project dependencies ..."
	@$(PIP) install --editable --quiet "$(SOFTWARE_DIR)"
	@touch $@
