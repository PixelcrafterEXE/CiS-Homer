# CiS "HOMER"

This repository contains the source code, documentation, and build tools for the **CiS HOMER** project.

---

## Project Structure

| Directory | Description |
| :--- | :--- |
| **./Docs** | Contains all project documentation. |
| **./Software** | Python implementation of the core system. |
| **./Firmware** | Code and scripts to generate the Raspberry Pi device image. |

---

## Setup & Installation

### 0.A (Linux): Install Requirements
Ensure the following are installed on your system:
* **Python**
* **Git**
* **GNU Make**

### 0.B (Windows): Setup WSL and Requirements
Install WSL by running
```bash
wsl --install --no-distribution
wsl --install -d Ubuntu
```
install Git, GNU Make, Python (for running locally):
```powershell
winget install -e --id Python.Python.3.9;winget install -e --id Git.Git;winget install -e --id GnuWin32.Make
```
Install Dependencies inside WSL:
```bash
sudo apt update
sudo apt install make python3-venv python3-pip python3 quilt parted qemu-user-binfmt debootstrap zerofree dosfstools libarchive-tools xxd file git kmod arch-test bc pigz -y
```

### 1. Clone the Repository
Clone the repository including all submodules:
```bash
git clone --recurse-submodules https://github.com/PixelcrafterEXE/CiS-Homer.git
```
### 2. Run Software Locally
To run the Software locally, execute:
```bash
make run
```
This will create or update a virtual environment as needed.
### 3. Build the Firmware Image 
To build the Raspberry Pi OS firmware image, run:
```bash
make build
```
### 4. Flash the Image to an SD Card
Use a tool like [RPI-Imager](https://www.raspberrypi.com/software/) to flash the generated image to an SD card.

---

## Standalone Executables

Every release includes self-contained executables built with PyInstaller

| File | Platform | Notes |
| :--- | :--- | :--- |
| `homer-linux-x86_64` | Linux x86-64 | `chmod +x homer-linux-x86_64 && ./homer-linux-x86_64` |
| `homer-windows.exe` | Windows 10/11 x64 | Double-click or run from a terminal |
| `homer.flatpak` | Linux (any distro) | install with flatpak install homer.flatpak |
| `image_*-homerpi-homer.img.xz` | Raspberry Pi | Flash with RPI-Imager |

### Building locally
```bash
make dist
```
The binary is written to `dist/homer` (or `dist/homer.exe` on Windows).

### Feature matrix

| Feature | HomerPi (RPi) | Linux desktop | Windows | Flatpak |
| :--- | :---: | :---: | :---: | :---: |
| Sensor readout (serial/USB) | ✓ | ✓ | ✓ | ✓ |
| Calibration & visualisation | ✓ | ✓ | ✓ | ✓ |
| USB CSV export | ✓ | ✓ | — | limited** |
| System time sync from sensor | ✓ | ✓* | — | — |
| On-screen keyboard | ✓ | ✓* | — | — |

*-Requires `timedatectl` / `onboard` to be present on the host (standard on
  the HomerPi firmware; most desktop distributions include both).


**-The Flatpak sandbox calls `udisksctl` via D-Bus (`org.freedesktop.UDisks2`).
  This works if the host system's udisks2 daemon is running and the Flatpak
  finish-arg `--system-talk-name=org.freedesktop.UDisks2` is honoured.
  Use the plain Linux binary for guaranteed USB export functionality.


