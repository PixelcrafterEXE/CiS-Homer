VENV_DIR     := Software/venv

ifeq ($(OS),Windows_NT) ### Windows
SYS_PYTHON   := python
PYTHON       := $(VENV_DIR)/Scripts/python.exe
PIP          := $(VENV_DIR)/Scripts/pip.exe
RM_DIR       := rmdir /s /q
VENV_PATH_CL := Software\venv
BUILD_PATH_CL:= Firmware\build
WORK_PATH_CL := Firmware\work
BUILD_CMD    := wsl bash -c "cd Firmware && sudo ./build-docker.sh"

else ### Linux

SYS_PYTHON   := python3
PYTHON       := $(VENV_DIR)/bin/python3
PIP          := $(VENV_DIR)/bin/pip
RM_DIR       := rm -rf
VENV_PATH_CL := $(VENV_DIR)
BUILD_CMD    := cd Firmware && sudo ./build.sh
BUILD_PATH_CL:= Firmware/build
WORK_PATH_CL := Firmware/work
endif


.PHONY: all run build clean help

all: help

run: $(VENV_DIR)/.installed  ## Run the software locally (creates / updates venv as needed)
	"$(PYTHON)" Software/main.py

build:  ## Build the Raspberry Pi OS firmware image
	@$(BUILD_CMD)

clean:  ## Remove the virtual environment
	-$(RM_DIR) $(VENV_PATH_CL) 2> /dev/null || true
	-$(RM_DIR) $(BUILD_PATH_CL) 2> /dev/null || true
	-$(RM_DIR) $(WORK_PATH_CL) 2> /dev/null || true

help:  ## Show this help message
	@echo "Usage: make <target>"
	@echo ""
	@echo "  run    Run the software locally (manages venv automatically)"
	@echo "  build  Build the Raspberry Pi OS firmware image"
	@echo "  clean  Remove build output and the virtual environment ($(VENV_DIR))"

$(VENV_DIR)/.installed: Software/pyproject.toml
	@$(SYS_PYTHON) -c "import os, sys, subprocess; subprocess.run([sys.executable, '-m', 'venv', r'$(VENV_DIR)']) if not os.path.exists(r'$(PYTHON)') else None"
	@echo "-> Updating pip / setuptools / wheel ..."
	@"$(PYTHON)" -m pip install --quiet --upgrade pip setuptools wheel
	@echo "-> Installing project dependencies ..."
	@"$(PYTHON)" -m pip install --quiet --editable "Software"
	@$(SYS_PYTHON) -c "with open(r'$@', 'w'): pass"
