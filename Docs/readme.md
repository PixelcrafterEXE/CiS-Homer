# CiS "HOMER"

This repository contains the source code, documentation, and build tools for the **CiS HOMER** project.

---

## Project Structure

| Directory | Description |
| :--- | :--- |
| **./Docs** | Contains all project documentation. |
| **./Software** | Python implementation of the core system. |
| **./Tests** | All unit tests for the software suite. |
| **./Firmware** | Code and scripts to generate the Raspberry Pi device image. |

---

## Setup & Installation

### 0A (Linux). Install Requirements
Ensure the following are installed on your system:
* **Python**
* **Git**
* **GNU Make**

### 0B (Windows). Setup WSL and Requirements
Install WSL by running
'''wsl --install -d Ubuntu'''
install Git, GNU Make, Python (for running locally):
'''winget install -e --id Python.Python.3.9;winget install -e --id Git.Git;winget install -e --id GnuWin32.Make'''
Install Dependencies inside WSL:
'''sudo apt update
sudo apt install make python3-venv python3-pip python3-venv quilt parted qemu-user-binfmt debootstrap zerofree dosfstools libarchive-tools xxd file git kmod arch-test -y'''

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
