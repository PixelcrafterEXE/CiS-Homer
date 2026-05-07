# PyInstaller runtime hook.
# When the app runs from a one-file bundle, extracted files land in
# sys._MEIPASS.  Changing cwd there makes relative resource paths
# (res/colors.json, res/OrientHint.png) work without touching source code.
import os
import sys

if hasattr(sys, "_MEIPASS"):
    os.chdir(sys._MEIPASS)
