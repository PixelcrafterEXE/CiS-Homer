# PyInstaller runtime hook — runs before any app code.
#
# 1. Change cwd to sys._MEIPASS so relative resource paths
#    (res/colors.json, res/OrientHint.png) resolve without source changes.
# 2. Point TCL_LIBRARY / TK_LIBRARY at the bundled Tcl/Tk directories so
#    that `package require msgcat` (used by ttkbootstrap) succeeds.
# 3. Monkey-patch ttkbootstrap's MessageCatalog.set_many:
#    The method calls ::msgcat::mcmset, which requires the Tcl msgcat package.
#    In some PyInstaller bundles the package isn't auto-loaded, so the command
#    doesn't exist.  The patch forces `package require msgcat` before the call
#    and falls back to individual ::msgcat::mcset calls via tk.call() (which
#    handles Tcl quoting automatically) if mcmset is still not available.
import os
import sys

if hasattr(sys, "_MEIPASS"):
    os.chdir(sys._MEIPASS)

    for _entry in os.listdir(sys._MEIPASS):
        _full = os.path.join(sys._MEIPASS, _entry)
        if not os.path.isdir(_full):
            continue
        _low = _entry.lower()
        if _low.startswith("tcl") and "TCL_LIBRARY" not in os.environ:
            os.environ["TCL_LIBRARY"] = _full
        elif _low.startswith("tk") and "TK_LIBRARY" not in os.environ:
            os.environ["TK_LIBRARY"] = _full


def _patch_msgcat():
    try:
        from ttkbootstrap.localization import msgcat as _mc
        import _tkinter as _tki

        _orig = _mc.MessageCatalog.set_many

        @staticmethod
        def _safe_set_many(locale, *args):
            from ttkbootstrap.window import get_default_root
            _root = get_default_root()
            if _root is not None:
                try:
                    _root.tk.eval("package require msgcat")
                except _tki.TclError:
                    pass
            try:
                return _orig(locale, *args)
            except _tki.TclError:
                # ::msgcat::mcmset not available; use mcset per message pair.
                # tk.call() handles Tcl quoting automatically.
                if _root is None:
                    return 0
                n = 0
                for src, dst in zip(args[::2], args[1::2]):
                    try:
                        _root.tk.call("::msgcat::mcset", locale, src, dst)
                        n += 1
                    except Exception:
                        pass
                return n

        _mc.MessageCatalog.set_many = _safe_set_many
    except Exception:
        pass


_patch_msgcat()
