This is the  CiS' "HOMER".

./Docs contains documentation
./Software contains the python implementation
./Tests contains all unit tests
./Firmware contains the code to generate the Pi image for the device

Setup:
    0. Build Requirements:
        - python
        - git
        - gnu make
    1. clone repo using
        'git clone --recurse-submodules github.com/PixelcrafterEXE/CiS-HomerPi.git'
    2. run firmware localy by running 'make run'
    3. run 'make build' in the root of the repo to build the image
    4. flash the generated image to an SD card (e.g. using RPI-Imager)

