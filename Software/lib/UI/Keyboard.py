"""
On-screen keyboard (onboard) show/hide via D-Bus.

Shows onboard whenever an editable widget (Entry, Combobox, Spinbox, Text)
gains focus; hides it after a short delay when focus leaves.

The delay on hide is long enough to survive the brief focus round-trip that
occurs when the user taps a key on the onboard window itself (X focus leaves
tkinter momentarily then returns), preventing a hide+show flicker.

Requires onboard to be running with auto-show DISABLED in dconf, so that
this code has sole control over show/hide.
"""

from __future__ import annotations

import subprocess
import threading
import tkinter as tk
from typing import Optional

_EDITABLE_TYPES: frozenset[str] = frozenset({"Entry", "Combobox", "Spinbox", "Text"})

_HIDE_DELAY = 0.4  # seconds – must outlast the focus round-trip during a key tap


def _is_editable(widget: tk.Widget) -> bool:
    wtype = type(widget).__name__
    if not any(t in wtype for t in _EDITABLE_TYPES):
        return False
    if "Combobox" in wtype:
        try:
            return str(widget.cget("state")) != "readonly"
        except Exception:
            pass
    return True


def _dbus(method: str) -> None:
    """Fire-and-forget D-Bus call to onboard. Silently ignored if unavailable."""
    try:
        subprocess.Popen(
            [
                "dbus-send", "--session",
                "--dest=org.onboard.Onboard",
                "--type=method_call",
                "/org/onboard/Onboard/Keyboard",
                f"org.onboard.Onboard.Keyboard.{method}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        pass


class KeyboardMixin:
    """
    Mixin for the root tkinter.Tk window.
    Call _setup_keyboard() once after the UI is fully built.
    """

    def _setup_keyboard(self) -> None:
        self._kb_hide_timer: Optional[threading.Timer] = None
        self.bind_all("<FocusIn>",  self._kb_focus_in,  add="+")  # type: ignore[attr-defined]
        self.bind_all("<FocusOut>", self._kb_focus_out, add="+")  # type: ignore[attr-defined]
        self.bind_all("<Button-1>", self._kb_button1,   add="+")  # type: ignore[attr-defined]

    def _kb_focus_in(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        if not isinstance(event.widget, tk.Widget):
            return
        if _is_editable(event.widget):
            # Cancel any pending hide and show immediately
            if self._kb_hide_timer is not None:
                self._kb_hide_timer.cancel()
                self._kb_hide_timer = None
            _dbus("Show")

    def _kb_focus_out(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        if not isinstance(event.widget, tk.Widget):
            return
        if _is_editable(event.widget):
            # Delayed hide – cancelled if focus returns to an editable widget
            if self._kb_hide_timer is not None:
                self._kb_hide_timer.cancel()
            t = threading.Timer(_HIDE_DELAY, _dbus, args=("Hide",))
            t.daemon = True
            t.start()
            self._kb_hide_timer = t

    def _kb_button1(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        if not isinstance(event.widget, tk.Widget):
            return
        if not _is_editable(event.widget):
            # Clicked outside any editable widget – cancel pending show and hide immediately
            if self._kb_hide_timer is not None:
                self._kb_hide_timer.cancel()
                self._kb_hide_timer = None
            _dbus("Hide")
