# PyInstaller runtime hook — runs before any app code.
#
# 1. Change cwd to sys._MEIPASS so relative resource paths
#    (res/colors.json, res/OrientHint.png) resolve without source changes.
# 2. Point TCL_LIBRARY / TK_LIBRARY at the bundled Tcl/Tk directories so
#    that `package require msgcat` (used by ttkbootstrap) succeeds on Windows.
import os
import sys

if hasattr(sys, "_MEIPASS"):
    os.chdir(sys._MEIPASS)

    # Find the first directory whose name starts with "tcl" or "tk" inside
    # the bundle and set the corresponding environment variable.
    for entry in os.listdir(sys._MEIPASS):
        full = os.path.join(sys._MEIPASS, entry)
        if not os.path.isdir(full):
            continue
        low = entry.lower()
        if low.startswith("tcl") and "TCL_LIBRARY" not in os.environ:
            os.environ["TCL_LIBRARY"] = full
        elif low.startswith("tk") and "TK_LIBRARY" not in os.environ:
            os.environ["TK_LIBRARY"] = full
