VENV_DIR     := Software/venv

ifeq ($(OS),Windows_NT)
PYTHON       := $(VENV_DIR)/Scripts/python.exe
PIP          := $(VENV_DIR)/Scripts/pip.exe
RM_DIR       := rmdir /s /q
VENV_PATH_CL := Software\venv
BUILD_PATH_CL:= Firmware\build
BUILD_CMD    := wsl bash -c "cd Firmware && sudo ./build-docker.sh"
else
PYTHON       := $(VENV_DIR)/bin/python3
PIP          := $(VENV_DIR)/bin/pip
RM_DIR       := rm -rf
VENV_PATH_CL := $(VENV_DIR)
BUILD_PATH_CL:= Firmware/build
BUILD_CMD    := cd Firmware && sudo ./build-docker.sh
endif

.PHONY: all run build deps clean help

all: help

run: $(VENV_DIR)/.installed  ## Run the software locally (creates / updates venv as needed)
	$(PYTHON) Software/main.py

build:  clean ## Build the Raspberry Pi OS firmware image
	@$(BUILD_CMD)

deps:  ## Sync installed venv packages → Software/pyproject.toml [project.dependencies]
	@if [ ! -x "$(PYTHON)" ] || ! "$(PYTHON)" --version >/dev/null 2>&1; then \
		echo "Error: no valid venv found – run 'make run' first."; \
		exit 1; \
	fi
	@$(PYTHON) -c "\
import subprocess, re; \
raw = open('Software/pyproject.toml').read(); \
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
open('Software/pyproject.toml', 'w').write(new); \
print('Updated Software/pyproject.toml with {} package(s).'.format(len(items)))"

clean:  ## Remove the virtual environment
	-$(RM_DIR) $(VENV_PATH_CL) 2> /dev/null || true
	-$(RM_DIR) $(BUILD_PATH_CL) 2> /dev/null || true

help:  ## Show this help message
	@echo "Usage: make <target>"
	@echo ""
	@echo "  run    Run the software locally (manages venv automatically)"
	@echo "  build  Build the Raspberry Pi OS firmware image"
	@echo "  deps   Sync installed venv packages -> Software/pyproject.toml"
	@echo "  clean  Remove build output and the virtual environment ($(VENV_DIR))"

$(VENV_DIR)/.installed: Software/pyproject.toml
	@if [ ! -x "$(PYTHON)" ] || ! "$(PYTHON)" --version >/dev/null 2>&1; then \
		echo "-> Creating virtual environment in $(VENV_DIR) ..."; \
		rm -rf "$(VENV_DIR)"; \
		python3 -m venv "$(VENV_DIR)"; \
	fi
	@echo "-> Updating pip / setuptools / wheel ..."
	@$(PIP) install --quiet --upgrade pip setuptools wheel
	@echo "-> Installing project dependencies ..."
	@$(PIP) install --quiet --editable "Software"
	@touch $@
