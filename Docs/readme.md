# CiS "HOMER"

This repository contains the source code, documentation, and build tools for the **CiS HOMER** project.

---

## 📂 Project Structure

| Directory | Description |
| :--- | :--- |
| **./Docs** | Contains all project documentation. |
| **./Software** | Python implementation of the core system. |
| **./Tests** | All unit tests for the software suite. |
| **./Firmware** | Code and scripts to generate the Raspberry Pi device image. |

---

## 🛠 Setup & Installation

### 0. Build Requirements
Ensure the following are installed on your system:
* **Python**
* **Git**
* **GNU Make**
* **Docker** (for building the firmware image)

### 1. Clone the Repository
Clone the repository including all submodules:
```bash
git clone --recurse-submodules [github.com/PixelcrafterEXE/CiS-HomerPi.git](https://github.com/PixelcrafterEXE/CiS-HomerPi.git)
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
